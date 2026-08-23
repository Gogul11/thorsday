from langgraph.graph import StateGraph, START, END
from Agents.agent_registry import AgentRegistry
from .states.main_agent_state import MainAgentState, ExecutionPlan
from logger import logger

class MainAgentGraph:
    def __init__(self, llm, registry : AgentRegistry):
        self.llm = llm
        self.registry = registry

        graph = StateGraph(MainAgentState)

        graph.add_node(
            "planner",
            self.planner_node
        )

        graph.add_node(
            "executor",
            self.execute_agent
        )

        graph.add_edge(
            START,
            "planner"
        )

        graph.add_edge(
            "planner",
            "executor"
        )

        graph.add_conditional_edges(
            "executor",
            self.should_continue,
            {
                "execute" : "executor",
                "end" : END
            }
        )

        self.graph = graph.compile()
        
    async def planner_node(self, state):
        task = state["task"]
        descriptions = self.registry.get_descriptions()
        prompt = f"""
You are the Main Agent of AgentOS.

Your responsibility is to decide which agents
should execute the user's task and in what order.

Available agents:

{descriptions}

User task:

{task}

Rules:

- Select only necessary agents.
- Determine the correct execution order.
- An agent may depend on the result of a previous agent.
- Do not perform the task yourself.
        """

        planner = self.llm.model.with_structured_output(
            ExecutionPlan
        )

        plan : ExecutionPlan = await planner.ainvoke(prompt)

        return {
            "plan" : plan.agents,
            "agents" : 0,
        }

    async def execute_agent(self, state):
        plan = state["plan"]
        index = state["current_agent"]

        agent_name = plan[index]

        agent = self.registry.get(agent_name)

        if agent is None:
            logger.exception("Unknown agent %s", agent_name)
            raise ValueError(
                f"Unknown agent: {agent_name}"
            )

        results = state["results"]

        result = await agent.run(
            task=state["task"],
            context=str(results)
        )

        updated_results = dict(results)
        
        updated_results[agent_name] = result

        return {
            "results": updated_results,
            "current_agent": index + 1
        }

    def should_continue(self, state):
    
        if state["current_agent"] < len(state["plan"]):
            return "execute"

        return "end"
