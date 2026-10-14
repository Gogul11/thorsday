"""Context — function-based conversation context helpers.

Each task has its own persistent context stored in MongoDB.
Use task_id as the single key (no more req_id split).
"""

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from repository.task_repo import DB_add_task_message, DB_get_task_messages
from logger import logger
from services.context_pager import ACTIVE_RAM_WINDOW, context_pager

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

# Keep only the most recent N messages in active context. Older messages are
# stored in the vector-backed swap partition and recalled when relevant.
_CONTEXT_WINDOW = ACTIVE_RAM_WINDOW


async def get_context(
    task_id: str,
    query: str = "",
    req_id: str = "",
) -> list[BaseMessage]:
    """Load message history for task_id and return it as LangChain messages.

    Always prepends the system message. Older messages are paged out to ChromaDB,
    and relevant paged messages are added back as a separate system block.
    Returns just [SYSTEM_MESSAGE] when the task is brand-new.
    """
    # Request-time reads are bounded to the active tail. Older messages are
    # indexed by the pager's background worker and recalled from ChromaDB.
    messages = await DB_get_task_messages(task_id, limit=_CONTEXT_WINDOW)

    if not messages:
        logger.info("Context loaded | task=%s | stored=0 | active=0", task_id)
        return [SYSTEM_MESSAGE]

    # Keep the background index current after restarts and after requests that
    # predate the worker. This is fire-and-forget with task-level deduplication;
    # it is intentionally not awaited for page-out completion.
    await context_pager.enqueue_page_out(task_id, req_id=req_id)

    paged_in = context_pager.page_in_relevant_context(
        task_id=task_id,
        query=query,
        req_id=req_id,
    )

    context: list[BaseMessage] = [SYSTEM_MESSAGE]

    if paged_in:
        context.append(
            SystemMessage(content=context_pager.format_page_in_block(paged_in))
        )

    for msg in messages[-_CONTEXT_WINDOW:]:
        if msg["role"] == "human":
            context.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "ai":
            context.append(AIMessage(content=msg["content"]))

    logger.info(
        "Context loaded | task=%s | query_chars=%d | active=%d | paged_in=%d",
        task_id,
        len(query),
        len(messages),
        len(paged_in),
    )

    return context


async def add_user_message(task_id: str, content: str) -> None:
    """Persist a human message for task_id."""
    await DB_add_task_message(task_id, "human", content)
    await context_pager.enqueue_page_out(task_id)


async def add_ai_message(task_id: str, content: str) -> None:
    """Persist an AI (assistant) message for task_id."""
    await DB_add_task_message(task_id, "ai", content)
    await context_pager.enqueue_page_out(task_id)
