"""Classify planner-empty prompts as conversation or unsupported tasks."""

from pydantic import BaseModel, Field


class PromptType(BaseModel):
    """Prompt type returned when the planner selects no existing agents."""

    kind: str = Field(description="Either 'conversational' or 'new_task'")
    rationale: str = Field(description="Short reason for the classification")


async def Prompt_type(task: str, model) -> PromptType:
    """Distinguish direct conversation from a task needing a new capability."""
    classifier = model.with_structured_output(PromptType, method="json_mode")
    prompt = f"""Classify this user prompt as exactly one of these types:
- conversational: greeting, casual conversation, a simple question, or a statement that needs a direct conversational answer and no specialized capability.
- new_task: a concrete task or set of tasks that needs work, but cannot be handled by any of the existing agents considered by the planner.

The planner has already checked whether existing agents can perform the requested work. If the request contains multiple tasks, classify it as conversational only when all parts are conversational; otherwise classify it as new_task.
Return the type and a brief rationale.

User prompt:
{task}

Return a valid json object matching the PromptType schema. Output json only.
"""
    result: PromptType = await classifier.ainvoke(prompt)
    if result.kind not in {"conversational", "new_task"}:
        raise ValueError(f"Unsupported prompt type: {result.kind}")
    return result
