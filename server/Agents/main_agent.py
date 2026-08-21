from models.model import Models
from services.context import Context
from logger import logger

class Main_Agent:
    def __init__(self, llm : Models):
        logger.info("Main Agent is successfully instantiated!")

        self.llm = llm
        self.model  = llm.model
        self.context = Context()

    #Chat member function for the main agent
    async def chat(self, message):
        logger.info("Main agent chat is called!")
        logger.info("Current context %s: ", self.context.get_context())
        
        self.context.add_user_message(message)

        response = await self.llm.chat(
            self.context.get_context()
        )

        self.context.add_system_message(response.content)

        logger.info("Returned response : %s", response)
        return response.content