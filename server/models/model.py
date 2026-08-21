
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os

from tools.tool_registry import TOOLS
from logger import logger

load_dotenv()

QWEN : str | None = os.getenv("QWEN")
LLAMA : str | None = os.getenv("LLAMA")

class Models:
    def __init__(self):
        QWEN : str | None = os.getenv("QWEN")
        LLAMA : str | None = os.getenv("LLAMA")

        if not QWEN or not LLAMA:
            logger.exception("Model is not Configured")
            raise ValueError("Model is not configured")

        self.current_model = LLAMA

        llm = ChatOllama(
            model=self.current_model,
            temperature=0.2
        )

        logger.info("%s is successfully configured!", self.current_model)
        self.model = llm.bind_tools(TOOLS) if len(TOOLS) > 0 else llm

    async def chat(self, context):
        response = await self.model.ainvoke(context)
        return response

        
        