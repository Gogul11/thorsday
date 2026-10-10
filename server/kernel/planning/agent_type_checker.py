"""Classify unmatched prompts before deciding whether to create an agent."""

from typing import Literal

from pydantic import BaseModel, Field


class AgentTypeDecision(BaseModel):
    kind: Literal["conversation", "new_task"] = Field(
        description=(
            "conversation for greetings, ordinary questions, simple requests, and prompts "
            "that a normal LLM can answer directly; new_task for a meaningful, actionable "
            "request requiring a capability not found by similarity search"
        )
    )
    rationale: str = Field(description="Brief reason for the classification")


async def check_agent_type(model, prompt: str) -> AgentTypeDecision:
    """Use the configured LLM to classify a prompt with no matching agent."""
    classifier = model.with_structured_output(AgentTypeDecision, method="json_mode")
    return await classifier.ainvoke(
        """Classify the user's latest prompt. Do not solve it.
Choose conversation for greetings, ordinary questions, simple requests, incomplete
prompts, and anything a normal LLM can answer directly. Choose new_task only for a
meaningful, actionable request that requires a capability not found by similarity
search and has enough scope to justify creating an agent. Be conservative about
creating agents for trivial one-off requests.
Return a JSON object with the fields `kind` and `rationale` matching the requested schema.

Prompt:
""" + prompt
    )
