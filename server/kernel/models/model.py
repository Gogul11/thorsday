"""Model factory — returns a configured LLM instance."""

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from logger import logger

load_dotenv()

_model = None


def get_model():
    """Return the shared LLM instance (lazy singleton)."""
    global _model
    if _model is not None:
        return _model

    current_model = "openai/gpt-oss-120b"
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment")

    _model = ChatGroq(
        model=current_model,
        temperature=0.2,
    )

    logger.info("%s is successfully configured!", current_model)
    return _model
