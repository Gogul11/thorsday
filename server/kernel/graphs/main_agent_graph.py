import uuid
import asyncio
from typing import Any
from langgraph.graph import StateGraph, START, END
from langchain_core.callbacks import BaseCallbackHandler
from Agents.agent_manager import AgentManager
from Redis.redis_connection import RedisPubSub
from .states.main_agent_state import MainAgentState, ExecutionPlan
from logger import logger


class ToolEventCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
        emit_fn,
        state: dict,
        agent_name: str,
        agent_id: str,
        main_loop: asyncio.AbstractEventLoop,
    ):
        self.emit_fn = emit_fn
        self.state = state
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.main_loop = main_loop
        self.current_tool = "tool"

    def _schedule_emit(self, coro):
        if not self.main_loop.is_closed():
            asyncio.run_coroutine_threadsafe(coro, self.main_loop)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs):
        tool_name = serialized.get("name") or kwargs.get("name") or self.current_tool
        self.current_tool = tool_name
        tool_inputs = kwargs.get("inputs") or input_str
        self._schedule_emit(
            self.emit_fn(
                "tool.STARTED",
                self.state,
                agent_name=self.agent_name,
                agent_id=self.agent_id,
                tool_name=tool_name,
                tool_input=str(tool_inputs),
            )
        )

    def on_tool_end(self, output: Any, **kwargs):
        tool_name = (
            getattr(output, "name", None)
            or kwargs.get("name")
            or self.current_tool
            or "tool"
        )
        self._schedule_emit(
            self.emit_fn(
                "tool.COMPLETED",
                self.state,
                agent_name=self.agent_name,
                agent_id=self.agent_id,
                tool_name=tool_name,
            )
        )

    def on_tool_error(self, error: BaseException, **kwargs):
        self._schedule_emit(
            self.emit_fn(
                "tool.FAILED",
                self.state,
                agent_name=self.agent_name,
                agent_id=self.agent_id,
                tool_name=self.current_tool,
                error=str(error),
            )
        )


class MainAgentGraph:
    def __init__(self, llm, manager: AgentManager, redis_client: RedisPubSub):
        self.llm = llm
        self.agent_manager = manager
        self.redis_client = redis_client

        graph = StateGraph(MainAgentState)

        graph.add_node("task_creation", self.create_task)
        graph.add_node("planner", self.planner_node)
        graph.add_node("executor", self.execute_agent)
        graph.add_node("response_node", self.response_node)

        graph.add_edge(START, "task_creation")
        graph.add_edge("task_creation", "planner")

        graph.add_conditional_edges(
            "planner",
            self.should_continue,
            {
                "execute": "executor",
                "end": "response_node",
            },
        )

        graph.add_conditional_edges(
            "executor",
            self.should_continue,
            {
                "execute": "executor",
                "end": "response_node",
            },
        )

        graph.add_edge("response_node", END)

        self.graph = graph.compile()

    async def run(self, state):
        return await self.graph.ainvoke(state)

    async def create_task(self, state):
        task_id = str(uuid.uuid4())
        new_state = {**state, "task_id": task_id}
        await self.emit("task.CREATED", new_state)
        return new_state

    async def planner_node(self, state):
        await self.emit("task.PLANNING", state)
        task = state["task"]
        descriptions = self.agent_manager.get_agent_descriptions()
        prompt = f"""
You are the Main Agent and task planner of AgentOS.

Your responsibility is to decide which specialized agents should execute the user's task and in what order.

Available agents:
{descriptions}

User task:
{task}

Rules:
- You MUST respond by providing the ExecutionPlan.
- Select only the necessary agents by their exact identifier (e.g., 'a1', 'a2', 'a3') that are required to fulfill the user's request.
- Order the agents logically according to dependencies (e.g. ['a3']).
- If no specialized agent from the available list is suitable for the task, or if the user is asking a general question/conversation, return an empty list: agents = [].
- Do not perform the task yourself; delegate to the specialized agents if available.
"""

        planner = self.llm.model.with_structured_output(ExecutionPlan)

        try:
            plan: ExecutionPlan = await planner.ainvoke(prompt)
            valid_agents = set(self.agent_manager.registry.agents.keys())
            plan_agents = [a for a in plan.agents if a in valid_agents]
        except Exception as e:
            logger.warning(
                "Planner failed to generate structured plan: %s. Defaulting to empty plan.",
                e,
            )
            plan_agents = []

        await self.emit("task.PLANNED", state, plan=plan_agents)
        return {
            "plan": plan_agents,
        }

    async def execute_agent(self, state):
        plan = state["plan"]
        index = state["current_agent"]

        agent_name = plan[index]
        task_id = state.get("task_id", "default-task")
        agent_id = f"{task_id}-{agent_name}"

        await self.emit(
            "agent.STARTED",
            state,
            agent_id=agent_id,
            agent_name=agent_name,
        )

        runtime = self.agent_manager.create_agent(
            agent_id=agent_id,
            agent_type=agent_name,
            task_id=task_id,
        )
        agent = runtime["agent"]
        self.agent_manager.set_status(agent_id, "RUNNING")
        main_loop = asyncio.get_running_loop()
        tool_callback = ToolEventCallbackHandler(
            self.emit,
            state,
            agent_name,
            agent_id,
            main_loop,
        )

        try:
            results = state["results"]

            result = await agent.run(
                task=state["task"],
                context=str(results),
                callbacks=[tool_callback],
            )

            updated_results = dict(results)
            updated_results[agent_name] = result

            self.agent_manager.set_status(agent_id, "COMPLETED")

            await self.emit(
                "agent.COMPLETED",
                state,
                agent_id=agent_id,
                agent_name=agent_name,
                result=result,
            )

            return {
                "results": updated_results,
                "current_agent": index + 1,
            }

        except Exception as e:
            await self.emit(
                "agent.FAILED",
                state,
                agent_id=agent_id,
                agent_name=agent_name,
                error=str(e),
            )
            self.agent_manager.set_status(agent_id, "FAILED")
            raise
        finally:
            await self.emit(
                "agent.DESTROYED",
                state,
                agent_id=agent_id,
                agent_name=agent_name,
            )
            self.agent_manager.destroy_agent(agent_id)

    async def response_node(self, state):
        results = state.get("results", {})
        agent_context = (
            results
            if results
            else "No specialized agent tools were needed. Answer the user request directly."
        )

        prompt = f"""
You are the final response generator of AgentOS.

Answer the user's original request directly and clearly using the results provided by the agents (if any).

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

        result = await self.llm.model.ainvoke(prompt)

        await self.emit("task.COMPLETED", state, response=result.content)

        return {"response": result.content}

    def should_continue(self, state):
        if state["current_agent"] < len(state["plan"]):
            return "execute"
        return "end"

    async def emit(self, event: str, state, **data):
        await self.redis_client.publish(
            "kernel_events",
            {
                "event": event,
                "req_id": state["req_id"],
                "task_id": state["task_id"],
                **data,
            },
        )
