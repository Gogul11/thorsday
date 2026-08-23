from typing import TypedDict, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

class MainAgentState(TypedDict):
    messages : Annotated[list[BaseMessage],add_messages]
    task : str
    plan : list[str]
    current_agent : int
    results : dict[str, str]

class ExecutionPlan(BaseModel):
    agents : list[str] = Field(
        description="Agents that should execute the task in order"
    )