from langgraph.graph import StateGraph, START, END
from Agents.agent_manager import AgentManager
from .states.main_agent_state import MainAgentState, ExecutionPlan
from logger import logger
import uuid

class MainAgentGraph:
    def __init__(self, llm, manager : AgentManager):
        self.llm = llm
        self.agent_manager = manager

        graph = StateGraph(MainAgentState)

        graph.add_node(
            "task_creation",
            self.create_task
        )
        
        graph.add_node(
            "planner",
            self.planner_node
        )

        graph.add_node(
            "executor",
            self.execute_agent
        )

        graph.add_node(
            "response_node",
            self.response_node
        )

        graph.add_edge(
            START,
            "task_creation"
        )

        graph.add_edge(
            "task_creation",
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
                "end" : "response_node"
            }
        )

        graph.add_edge(
            "response_node",
            END
        )

        self.graph = graph.compile()

    def create_task(self, state):
        return {
            "task_id" : str(uuid.uuid4())
        }
        
    async def planner_node(self, state):
        task = state["task"]
        descriptions = self.agent_manager.get_agent_descriptions()
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
        }

    async def execute_agent(self, state):
        plan = state["plan"]
        index = state["current_agent"]

        agent_name = plan[index]
        task_id = state.get('task_id', 'default-task')
        agent_id = f'{task_id}-{agent_name}'

        runtime = self.agent_manager.create_agent(
            agent_id=agent_id,
            agent_type=agent_name,
            task_id=task_id
        )
        agent = runtime['agent']
        self.agent_manager.set_status(agent_id, "RUNNING")

        try:
            results = state["results"]
    
            result = await agent.run(
                task=state["task"],
                context=str(results)
            )
    
            updated_results = dict(results)
            updated_results[agent_name] = result

            self.agent_manager.set_status(agent_id, "COMPLETED")

            return {
                "results": updated_results,
                "current_agent": index + 1
            }
            
        except Exception:
            self.agent_manager.set_status(agent_id, "FAILED")
            raise
        finally:
            self.agent_manager.destroy_agent(agent_id)

    async def response_node(self, state):
    
        results = state["results"]
    
        prompt = f"""
    You are the final response generator.
    
    Answer the user's original request using the results
    provided by the agents.
    
    User request:
    {state["task"]}
    
    Agent results:
    {results}
    
    Rules:
    - Do not mention agents.
    - Do not mention the orchestration process.
    - Do not return a dictionary.
    - Do not explain how the task was executed.
    - Give the user a natural, concise answer.
    """
    
        result = await self.llm.model.ainvoke(prompt)
    
        return {
            "response": result.content
        }
    
    def should_continue(self, state):
    
        if state["current_agent"] < len(state["plan"]):
            return "execute"

        return "end"
