"""Main agent graph — builds and returns a compiled LangGraph.

All graph nodes are plain async functions. build_graph() wires them together
and returns the compiled graph ready for ainvoke().
"""

import asyncio
import uuid
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from Agents.agent_manager import (
    create_agent,
    destroy_agent,
    set_agent_status,
)
from Agents.agent_registry import get_agent_descriptions, list_agent_types
from graphs.states.main_agent_state import MainAgentState
from logger import logger
from Redis.redis_connection import publish
from repository.task_repo import DB_add_task_event, DB_create_task, DB_update_task


# ---------------------------------------------------------------------------
# Structured output schema for the planner
# ---------------------------------------------------------------------------

class ExecutionPlan(BaseModel):
    agents: list[str] = Field(
        description="Agents that should execute the task in order"
    )


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

    descriptions = get_agent_descriptions()
    valid_types = set(list_agent_types())

    prompt = f"""
You are the Main Agent and task planner of AgentOS.

Your responsibility is to decide which specialized agents should execute
the user's task and in what order.

Available agents:
{descriptions}

User task:
{state["task"]}

Agent selection rules:

- a1 = system information, hardware, software, processes, services,
  system configuration and system status.

- a2 = date, time, timezone and calendar/date-related questions.

- a3 = research, web search, Wikipedia, academic, scientific,
  technical and factual information gathering.

- a4 = FILE AND DOCUMENT OPERATIONS on the user's local computer.
  This includes:
  - finding/searching files
  - searching by extension such as PDF, DOCX, TXT, etc.
  - searching directories
  - listing directory contents
  - reading documents
  - creating files
  - modifying files
  - appending to files
  - renaming files
  - moving files
  - creating folders
  - deleting files
  - comparing documents
  - extracting information from documents
  - summarizing documents
  - classifying documents
  - retrieving file metadata.

IMPORTANT:
If the user asks to interact with files or directories on their
computer, ALWAYS select a4.

Examples:
- "find my PDFs" -> ["a4"]
- "list files in Downloads" -> ["a4"]
- "show the 5 newest PDFs" -> ["a4"]
- "read this PDF" -> ["a4"]
- "summarize this document" -> ["a4"]
- "create a text file" -> ["a4"]
- "rename this file" -> ["a4"]
- "move this file" -> ["a4"]
- "delete this file" -> ["a4"]
- "compare these two documents" -> ["a4"]
- "what is the current time?" -> ["a2"]
- "what processes are running?" -> ["a1"]
- "research operating system scheduling algorithms" -> ["a3"]

Rules:
- Respond by providing an ExecutionPlan.
- Select only agents by their exact identifiers: a1, a2, a3, a4.
- Select a4 whenever filesystem or document operations are requested.
- Order agents logically according to dependencies.
- If no specialized agent is suitable, return an empty list: agents = [].
- Do not perform the task yourself; delegate to the appropriate agent.
"""

    planner = model.with_structured_output(ExecutionPlan)

    try:
        plan: ExecutionPlan = await planner.ainvoke(prompt)
        plan_agents = [a for a in plan.agents if a in valid_types]

        # Deterministic routing safeguard for filesystem/document tasks.
        #
        # This prevents the planner LLM from accidentally answering a
        # filesystem request itself instead of delegating it to A4.
        task_lower = state["task"].lower()

        file_keywords = (
            "file",
            "files",
            "folder",
            "folders",
            "directory",
            "directories",
            "pdf",
            "docx",
            "document",
            "documents",
            "download",
            "downloads",
            "rename",
            "move",
            "delete",
            "create a file",
            "create file",
            "read file",
            "read document",
            "write file",
            "modify file",
            "edit file",
            "append to",
            "metadata",
        )

        is_file_task = any(
            keyword in task_lower
            for keyword in file_keywords
        )

        if is_file_task and "a4" in valid_types:
            plan_agents = ["a4"]

    except Exception as exc:
        logger.warning("Planner failed: %s. Defaulting to empty plan.", exc)
        plan_agents = []

    await _emit("task.PLANNED", state, plan=plan_agents)
    await DB_update_task(state["task_id"], plan=plan_agents)

    return {"plan": plan_agents}


async def _node_executor(state: dict, model) -> dict:
    """Run the next agent in the plan."""
    plan = state["plan"]
    index = state["current_agent"]
    agent_name = plan[index]
    task_id = state["task_id"]
    agent_id = f"{task_id}-{agent_name}"

    await _emit("agent.STARTED", state, agent_id=agent_id, agent_name=agent_name)

    runtime = create_agent(agent_id=agent_id, agent_type=agent_name, task_id=task_id)
    set_agent_status(agent_id, "RUNNING")

    loop = asyncio.get_running_loop()
    callback = ToolEventCallback(_emit, state, agent_name, agent_id, loop)

    try:
        run_fn = runtime["run"]
        result = await run_fn(
            model=model,
            task=state["task"],
            context="\n".join(
                f"{msg.type}: {msg.content}"
                for msg in state["messages"]
            ) + "\n" + "Previous Results :" + str(state["results"]),
            callbacks=[callback],
            req_id=state["req_id"],
            task_id=state["task_id"],
        )

        updated_results = {**state["results"], agent_name: result}
        set_agent_status(agent_id, "COMPLETED")

        await _emit(
            "agent.COMPLETED",
            state,
            agent_id=agent_id,
            agent_name=agent_name,
            result=result,
        )

        return {"results": updated_results, "current_agent": index + 1}

    except Exception as exc:
        await _emit(
            "agent.FAILED",
            state,
            agent_id=agent_id,
            agent_name=agent_name,
            error=str(exc),
        )
        set_agent_status(agent_id, "FAILED")
        raise

    finally:
        await _emit("agent.DESTROYED", state, agent_id=agent_id, agent_name=agent_name)
        destroy_agent(agent_id)


async def _node_response(state: dict, model) -> dict:
    """Generate and persist the final response for the user."""
    results = state.get("results", {})
    agent_context = (
        results
        if results
        else "No specialized agent tools were needed. Answer the user request directly."
    )

    prompt = f"""
You are the final response generator of AgentOS.

Answer the user's original request directly and clearly using the results
provided by the agents (if any).

User request:
{state["task"]}

Agent results:
{agent_context}

Rules:
- Do not mention agents, agent IDs, or the orchestration process.
- Do not return raw python dictionaries.
- Do not explain how the task was executed internally.
- Give the user a natural, informative, concise answer with clean Markdown formatting.
"""

    result = await model.ainvoke(prompt)
    response = result.content

    await _emit("task.COMPLETED", state, response=response)
    await DB_update_task(
        state["task_id"],
        status="completed",
        response=response,
        completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )

    return {"response": response}


def _should_continue(state: dict) -> str:
    if state["current_agent"] < len(state["plan"]):
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
