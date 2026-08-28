"""Context — function-based conversation context helpers.

Each task has its own persistent context stored in MongoDB.
Use task_id as the single key (no more req_id split).
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from repository.task_repo import DB_add_task_message, DB_get_task_messages

SYSTEM_MESSAGE = SystemMessage(
    content="""You are the Main Agent of AgentOS.

Understand the user's intent, use the provided context, reason about tasks,
and use available tools when necessary.

Rules:
- Use context to maintain conversation continuity.
- Use tools when required; never fabricate tool results.
- If you cannot perform an action, state the limitation.
- For complex tasks, break them into logical steps.
- Give concise, accurate responses.
- Never claim an action was completed unless it actually was.
"""
)

# Keep only the most recent N turns to avoid unbounded context growth
_CONTEXT_WINDOW = 20


async def get_context(task_id: str) -> list[BaseMessage]:
    """Load message history for task_id and return it as LangChain messages.

    Always prepends the system message. Returns the last _CONTEXT_WINDOW entries.
    Returns just [SYSTEM_MESSAGE] when the task is brand-new.
    """
    messages = await DB_get_task_messages(task_id)

    context: list[BaseMessage] = [SYSTEM_MESSAGE]

    if messages:
        for msg in messages:
            if msg["role"] == "human":
                context.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                context.append(AIMessage(content=msg["content"]))

    return context[-_CONTEXT_WINDOW:]


async def add_user_message(task_id: str, content: str) -> None:
    """Persist a human message for task_id."""
    await DB_add_task_message(task_id, "human", content)


async def add_ai_message(task_id: str, content: str) -> None:
    """Persist an AI (assistant) message for task_id."""
    await DB_add_task_message(task_id, "ai", content)
