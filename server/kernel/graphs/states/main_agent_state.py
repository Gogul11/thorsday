"""LangGraph state type for the main agent pipeline."""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing import TypedDict


class MainAgentState(TypedDict):
    req_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    task: str
    plan: list[str]
    current_agent: int
    results: dict[str, str]
    response: str
