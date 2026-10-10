"""Main agent graph — builds and returns a compiled LangGraph.

All graph nodes are plain async functions. build_graph() wires them together
and returns the compiled graph ready for ainvoke().
"""

import asyncio
import uuid
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from Agents.agent_manager import (
    create_agent,
    destroy_agent,
    set_agent_status,
)
from Agents.agent_registry import list_agent_types
from graphs.states.main_agent_state import MainAgentState
from logger import logger
from Redis.redis_connection import publish
from repository.task_repo import DB_add_task_event, DB_create_task, DB_update_task
from services.context import get_context
from services.agent_scheduler import SchedulerJob, get_scheduler
from graphs.constant import build_planner_context, get_explicit_agent_hints
from planning.diagram import chain_steps, to_mermaid, validate_steps
from planning.agent_type_checker import check_agent_type

# ---------------------------------------------------------------------------
# Structured output schema for the planner
# ---------------------------------------------------------------------------


class ExecutionPlan(BaseModel):
    agents: list[str] = Field(
        description="Agents that should execute the task in order"
    )
    steps: list[dict] = Field(default_factory=list, description="DAG steps with id, agent, depends_on, and purpose")
    uncovered_tasks: list[str] = Field(
        default_factory=list,
        description="Meaningful actionable parts of the user's request that none of the candidate agents can perform.",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = Field(default="")


# ---------------------------------------------------------------------------
# Tool-event callback (thread-safe bridge from sync LangChain → async loop)
# ---------------------------------------------------------------------------


class ToolEventCallback(BaseCallbackHandler):
    """Bridges synchronous LangChain tool callbacks into the async event loop."""

    def __init__(self, emit_fn, state: dict, agent_name: str, agent_id: str, loop):
        self.emit_fn = emit_fn
        self.state = state
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.loop = loop
        self.current_tool = "tool"
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._usage_sources: set[int] = set()

    def _record_usage(self, usage: dict, source: object) -> None:
        if not usage or id(source) in self._usage_sources:
            return
        self._usage_sources.add(id(source))
        def value(*keys):
            return next((int(usage[key]) for key in keys if usage.get(key) is not None), 0)

        prompt = value("prompt_tokens", "input_tokens")
        completion = value("completion_tokens", "output_tokens")
        total = value("total_tokens") or prompt + completion
        self.token_usage["prompt_tokens"] += prompt
        self.token_usage["completion_tokens"] += completion
        self.token_usage["total_tokens"] += total

    def on_llm_end(self, response, **kwargs):
        """Collect usage from classic LangChain LLM callback responses."""
        usage = getattr(response, "llm_output", None) or {}
        usage = usage.get("token_usage") or usage.get("usage") or {}
        if not usage:
            for generation_group in getattr(response, "generations", []) or []:
                for generation in generation_group or []:
                    message = getattr(generation, "message", None)
                    usage = getattr(message, "usage_metadata", None) or {}
                    if usage:
                        break
                if usage:
                    break
        self._record_usage(usage, response)

    def on_chat_model_end(self, response, **kwargs):
        """Collect usage from chat-model callback responses."""
        self.on_llm_end(response, **kwargs)

    def on_chain_end(self, outputs, **kwargs):
        """Fallback for agent runtimes exposing usage on returned messages."""
        messages = outputs.get("messages", []) if isinstance(outputs, dict) else []
        for message in messages:
            usage = getattr(message, "usage_metadata", None) or {}
            if not usage:
                metadata = getattr(message, "response_metadata", None) or {}
                usage = metadata.get("token_usage", {}) if isinstance(metadata, dict) else {}
            if isinstance(message, dict):
                response_metadata = message.get("response_metadata") or {}
                usage = message.get("usage_metadata") or response_metadata.get("token_usage", {})
            self._record_usage(usage, message)

    def _fire(self, coro):
        if not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs):
        tool_name = serialized.get("name") or kwargs.get("name") or self.current_tool
        self.current_tool = tool_name
        self._fire(
            self.emit_fn(
                "tool.STARTED",
                self.state,
                agent_name=self.agent_name,
                agent_id=self.agent_id,
                tool_name=tool_name,
                tool_input=str(kwargs.get("inputs") or input_str),
            )
        )

    def on_tool_end(self, output: Any, **kwargs):
        tool_name = (
            getattr(output, "name", None) or kwargs.get("name") or self.current_tool
        )
        self._fire(
            self.emit_fn(
                "tool.COMPLETED",
                self.state,
                agent_name=self.agent_name,
                agent_id=self.agent_id,
                tool_name=tool_name,
            )
        )

    def on_tool_error(self, error: BaseException, **kwargs):
        self._fire(
            self.emit_fn(
                "tool.FAILED",
                self.state,
                agent_name=self.agent_name,
                agent_id=self.agent_id,
                tool_name=self.current_tool,
                error=str(error),
            )
        )


# ---------------------------------------------------------------------------
# Emit helper — publish to Redis and persist to MongoDB
# ---------------------------------------------------------------------------


async def _emit(event: str, state: dict, **data) -> None:
    payload = {
        "event": event,
        "req_id": state["req_id"],
        "task_id": state["task_id"],
        **data,
    }
    await publish("kernel_events", payload)
    await DB_add_task_event(state["task_id"], payload)


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------


async def _node_create_task(state: dict) -> dict:
    """Create a new task document in MongoDB (only for brand-new tasks)."""
    task_id = state["task_id"]

    # If task_id was provided it's a follow-up — skip creation
    if not task_id:
        task_id = str(uuid.uuid4())
        await DB_create_task(task_id=task_id, prompt=state["task"])

    new_state = {**state, "task_id": task_id}
    await _emit("task.CREATED", new_state)
    return {"task_id": task_id}


async def _node_planner(state: dict, model) -> dict:
    """Plan which agents should run for this task."""
    await _emit("task.PLANNING", state)

    candidate_names: list[str] = []
    try:
        valid_types = set(list_agent_types())
        prompt, candidate_names = build_planner_context(state["task"])
        no_retrieved_candidates = not candidate_names
        if not candidate_names:
            try:
                decision = await check_agent_type(model, state["task"])
            except Exception as exc:
                # If classification is unavailable, avoid creating an agent
                # without a positive new-task decision.
                logger.warning("Agent type check failed: %s. Using direct response.", exc)
                decision = None

            if decision is not None and decision.kind == "new_task":
                if "agent_creator" in valid_types:
                    candidate_names = ["agent_creator"]
                    prompt = f"Create an agent to complete this actionable task:\n{state['task']}"
                    plan = ExecutionPlan(
                        agents=["agent_creator"], confidence=0.9,
                        rationale="The type checker identified a meaningful new task requiring a new capability.",
                    )
                else:
                    plan = ExecutionPlan(agents=[], rationale="No matching agent is available.")
            else:
                rationale = (
                    "Agent type check was unavailable; responding directly."
                    if decision is None
                    else "Unmatched prompt classified as conversational."
                )
                plan = ExecutionPlan(agents=[], confidence=0.9, rationale=rationale)
        else:
            planner = model.with_structured_output(ExecutionPlan, method="json_mode")
            plan = await planner.ainvoke(prompt)
        plan_agents = []
        for agent_name in plan.agents:
            if (
                agent_name in valid_types
                and agent_name in candidate_names
                and agent_name not in plan_agents
            ):
                plan_agents.append(agent_name)
        plan_steps = validate_steps(plan.steps, valid_types, set(candidate_names))
        if not plan_steps:
            plan_steps = chain_steps(plan_agents)
        plan_agents = [step["agent"] for step in plan_steps]

        # Preserve every capability explicitly requested by a compound task.
        # The LLM still performs the primary planning; this guard prevents a
        # valid but overly-minimal response from silently dropping later work.
        explicit_hints = get_explicit_agent_hints(state["task"])
        missing_hints = [
            agent for agent in explicit_hints
            if agent in candidate_names and agent not in plan_agents
        ]
        if missing_hints:
            ordered_agents = [
                agent for agent in explicit_hints
                if agent in candidate_names and agent in (plan_agents + missing_hints)
            ]
            ordered_agents.extend(agent for agent in plan_agents if agent not in ordered_agents)
            plan_agents = ordered_agents
            plan_steps = chain_steps(plan_agents)

        # Candidate agents can cover only part of a compound request. Check
        # each remaining actionable part and add creator steps only when the
        # checker identifies a meaningful new capability.
        if not no_retrieved_candidates and plan.uncovered_tasks:
            creator_tasks: list[str] = []
            for uncovered_task in dict.fromkeys(
                " ".join(item.split()) for item in plan.uncovered_tasks if item.strip()
            ):
                try:
                    decision = await check_agent_type(model, uncovered_task)
                except Exception as exc:
                    logger.warning("Agent type check failed for uncovered task: %s", exc)
                    continue
                if decision.kind == "new_task":
                    creator_tasks.append(uncovered_task)

            if creator_tasks and "agent_creator" in valid_types:
                # If the planner itself selected the creator from its
                # candidates, scope those steps to uncovered work instead of
                # scheduling a duplicate creator call.
                creator_steps = [
                    step for step in plan_steps
                    if step["agent"] == "agent_creator"
                ]
                tasks_to_add = []
                for index, creator_task in enumerate(creator_tasks):
                    if index < len(creator_steps):
                        creator_steps[index]["task"] = creator_task
                    else:
                        tasks_to_add.append(creator_task)

                # Wait until all planned existing-agent branches complete so
                # their results are available as context for the new agent.
                depended_on = {
                    dependency
                    for step in plan_steps
                    for dependency in step.get("depends_on", [])
                }
                creator_dependencies = [
                    step["id"] for step in plan_steps if step["id"] not in depended_on
                ]
                used_ids = {step["id"] for step in plan_steps}
                for index, creator_task in enumerate(tasks_to_add, start=1):
                    step_id = f"new_capability_{index}"
                    while step_id in used_ids:
                        step_id = f"_{step_id}"
                    used_ids.add(step_id)
                    plan_steps.append({
                        "id": step_id,
                        "agent": "agent_creator",
                        "depends_on": creator_dependencies,
                        "purpose": "Create and run an agent for the uncovered task.",
                        "task": creator_task,
                    })
                    creator_dependencies = [step_id]
                if "agent_creator" not in candidate_names:
                    candidate_names.append("agent_creator")
                plan_agents = [step["agent"] for step in plan_steps]
                plan.rationale = (
                    f"{plan.rationale} Added agent creator for meaningful uncovered work."
                ).strip()
    except Exception as exc:
        # Preserve useful semantic routing when the LLM is unavailable, for
        # example during a provider rate limit. The top retrieved candidate is
        # safer than silently converting the task into a direct response.
        logger.warning("Planner failed: %s. Using semantic fallback.", exc)
        explicit_hints = get_explicit_agent_hints(state["task"])
        plan_agents = [agent for agent in explicit_hints if agent in candidate_names]
        if not plan_agents:
            plan_agents = candidate_names[:1]
        plan_steps = chain_steps(plan_agents)
        plan = ExecutionPlan(
            agents=plan_agents,
            confidence=0.25 if plan_agents else 0.0,
            rationale="LLM planner unavailable; selected the top semantic candidate.",
        )

    mermaid = to_mermaid(plan_steps)

    await _emit(
        "task.PLANNED",
        state,
        plan=plan_agents,
        confidence=plan.confidence,
        rationale=plan.rationale,
        candidates=candidate_names,
        plan_graph=plan_steps,
        mermaid=mermaid,
    )
    await DB_update_task(state["task_id"], plan=plan_agents, plan_graph=plan_steps, plan_mermaid=mermaid)

    return {"plan": plan_agents, "plan_steps": plan_steps, "completed_steps": []}


async def _node_executor(state: dict, model) -> dict:
    """Submit the next dependency-ready agent to the global scheduler."""
    plan_steps = state.get("plan_steps") or chain_steps(state["plan"])
    completed = set(state.get("completed_steps", []))
    ready_step = next(
        step for step in plan_steps
        if step["id"] not in completed and set(step.get("depends_on", [])) <= completed
    )
    agent_name = ready_step["agent"]
    task_id = state["task_id"]
    agent_id = f"{task_id}-{ready_step['id']}-{agent_name}"

    async def run_scheduled_step():
        await _emit("agent.STARTED", state, agent_id=agent_id, agent_name=agent_name)
        runtime = create_agent(agent_id=agent_id, agent_type=agent_name, task_id=task_id)
        set_agent_status(agent_id, "RUNNING")
        loop = asyncio.get_running_loop()
        callback = ToolEventCallback(_emit, state, agent_name, agent_id, loop)
        run_fn = runtime["run"]
        try:
            agent_task = (
                ready_step.get("task", state["task"])
                if agent_name == "agent_creator"
                else state["task"]
            )
            result = await run_fn(
                model=model,
                task=agent_task,
                context="\n".join(f"{msg.type}: {msg.content}" for msg in state["messages"])
                + "\n"
                + f"Current DAG step: {ready_step['purpose']}\nPrevious Results :"
                + str(state["results"]),
                callbacks=[callback],
                req_id=state["req_id"],
                task_id=state["task_id"],
            )
            # Pass provider usage back to the scheduler without changing the
            # agent's public result shape.
            scheduled_job.token_usage = dict(callback.token_usage)
            if not scheduled_job.token_usage["total_tokens"]:
                logger.warning(
                    "No provider token usage received | task=%s | agent=%s | model usage metadata unavailable",
                    task_id,
                    agent_name,
                )
            set_agent_status(agent_id, "COMPLETED")
            await _emit("agent.COMPLETED", state, agent_id=agent_id, agent_name=agent_name, result=result)
            return result
        except Exception as exc:
            error_text = str(exc).lower()
            retryable = any(token in error_text for token in ("rate limit", "quota", "429", "tokens per day"))
            await _emit(
                "agent.WAITING" if retryable else "agent.FAILED",
                state,
                agent_id=agent_id,
                agent_name=agent_name,
                error=str(exc),
                reason="provider_quota_or_rate_limit" if retryable else None,
            )
            set_agent_status(agent_id, "WAITING" if retryable else "FAILED")
            raise
        finally:
            await _emit("agent.DESTROYED", state, agent_id=agent_id, agent_name=agent_name)
            destroy_agent(agent_id)

    scheduled_job = SchedulerJob(
            task_id=task_id,
            req_id=state["req_id"],
            step_id=ready_step["id"],
            agent_name=agent_name,
            runner=run_scheduled_step,
            base_priority=float(ready_step.get("priority", 5)),
            estimated_tokens=int(ready_step.get("estimated_tokens", 4000)),
        )
    result = await get_scheduler().submit(scheduled_job)
    updated_results = {**state["results"], ready_step["id"]: result}
    return {"results": updated_results, "completed_steps": [*state.get("completed_steps", []), ready_step["id"]]}


async def _node_response(state: dict, model) -> dict:
    """Generate and persist the final response for the user while preserving full conversation history."""
    results = state.get("results", {})

    # Build full message list: prior conversation history + current turn
    messages_for_llm = list(state.get("messages", []))

    current_task = state.get("task", "")
    if results:
        user_turn_content = (
            f"{current_task}\n\n"
            f"[Agent Execution Results: {results}\n"
            f"Instruction: Use the agent execution results above to answer the user clearly in Markdown without exposing raw JSON structures.]"
        )
    else:
        user_turn_content = current_task

    messages_for_llm.append(HumanMessage(content=user_turn_content))

    result = await model.ainvoke(messages_for_llm)
    response = result.content

    await _emit("task.COMPLETED", state, response=response)
    await DB_update_task(
        state["task_id"],
        status="completed",
        response=response,
        completed_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )

    return {"response": response}


def _should_continue(state: dict) -> str:
    if len(state.get("completed_steps", [])) < len(state.get("plan_steps", [])):
        return "execute"
    return "end"


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_graph(model):
    """Build and return a compiled LangGraph for the main agent pipeline.

    Nodes are closures that capture `model`, keeping the graph stateless
    with respect to the LLM instance.
    """

    async def node_planner(state):
        return await _node_planner(state, model)

    async def node_executor(state):
        return await _node_executor(state, model)

    async def node_response(state):
        return await _node_response(state, model)

    g = StateGraph(MainAgentState)

    g.add_node("task_creation", _node_create_task)
    g.add_node("planner", node_planner)
    g.add_node("executor", node_executor)
    g.add_node("response_node", node_response)

    g.add_edge(START, "task_creation")
    g.add_edge("task_creation", "planner")

    g.add_conditional_edges(
        "planner",
        _should_continue,
        {"execute": "executor", "end": "response_node"},
    )
    g.add_conditional_edges(
        "executor",
        _should_continue,
        {"execute": "executor", "end": "response_node"},
    )
    g.add_edge("response_node", END)

    return g.compile()
