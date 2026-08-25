from collections.abc import Callable

from Agents.agent_manager import AgentManager
from Agents.agent_registry import AgentRegistry
from Redis.redis_connection import RedisPubSub
from graphs.main_agent_graph import MainAgentGraph
from models.model import Models
from services.context import Context
from logger import logger
import uuid

class Main_Agent:
    def __init__(self, llm : Models, redis_client : RedisPubSub):
        logger.info("Main Agent is successfully instantiated!")

        self.llm = llm
        self.model  = llm.model
        self.context = Context()

        self.registry = AgentRegistry(self.model)

        self.agent_manager = AgentManager(self.registry)

        self.graph = MainAgentGraph(
            self.llm,
            self.agent_manager,
            redis_client
        )

    #Chat member function for the main agent
    async def chat(
        self,
        message: str,
        req_id
    ):

        logger.info("Main agent chat started: %s")
        logger.info("Current context %s: ", self.context.get_context())
        
        self.context.add_user_message(message)
        logger.info("Main agent : %s", self.context.get_context())
        
        result = await self.graph.run(
            {
            "req_id" : str(req_id),
            "messages" : self.context.get_context(),
            "task_id" : "",
            "task" : message,
            "plan" : [],
            "current_agent" : 0,
            "results" : {},
            "response" : ""
            },
        )
        
        logger.info(
            "Task %s execution plan: %s",
            result['task_id'],
            result["plan"]
        )

        logger.info(
            "Task %s agent results: %s",
            result['task_id'],
            result["response"]
        )
        self.context.add_system_message(result["response"])

        # logger.info("Returned response : %s", plan)
        return result["response"]
