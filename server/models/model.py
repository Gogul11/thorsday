
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import os
from langchain_groq import ChatGroq

from logger import logger

load_dotenv()

QWEN : str | None = os.getenv("QWEN")
LLAMA : str | None = os.getenv("LLAMA")
GROQ_API_KEY : str | None = os.getenv("GROQ_API_KEY")

class Models:
    def __init__(self):
        # QWEN : str | None = os.getenv("QWEN")
        # LLAMA : str | None = os.getenv("LLAMA")

        # if not QWEN or not LLAMA:
        #     logger.exception("Model is not Configured")
        #     raise ValueError("Model is not configured")

        #for ollama based
        # self.current_model = LLAMA

        # self.model = ChatOllama(
        #     model=self.current_model,
        #     temperature=0.2
        # )

        # logger.info("%s is successfully configured!", self.current_model)

        self.current_model = 'openai/gpt-oss-120b'
        self.model = ChatGroq(
            model=self.current_model,
            temperature=0.2
        )

        logger.info("%s is successfully configured!", self.current_model)
        

    async def chat(self, context):
        response = await self.model.ainvoke(context)
        return response

        
        