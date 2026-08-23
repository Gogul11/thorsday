from Agents.agent_registry import AgentRegistry
from graphs.main_agent_graph import MainAgentGraph
from models.model import Models
from services.context import Context
from logger import logger

class Main_Agent:
    def __init__(self, llm : Models):
        logger.info("Main Agent is successfully instantiated!")

        self.llm = llm
        self.model  = llm.model
        self.context = Context()

        self.registry = AgentRegistry(
            self.model
        )

        self.graph = MainAgentGraph(
            self.llm,
            self.registry
        )

    #Chat member function for the main agent
    async def chat(self, message : str):
        logger.info("Main agent chat is called!")
        logger.info("Current context %s: ", self.context.get_context())
        
        self.context.add_user_message(message)
        logger.info("Main agent : %s", self.context.get_context())
        
        result = await self.graph.graph.ainvoke({
            "messages" : self.context.get_context(),
            "task" : message,
            "plan" : [],
            "current_agent" : 0,
            "results" : {}
        })
        
        logger.info(
            "Execution plan: %s",
            result["plan"]
        )

        logger.info(
            "Agent results: %s",
            result["results"]
        )
        # self.context.add_system_message(result["results"])

        # logger.info("Returned response : %s", plan)
        return result["results"]