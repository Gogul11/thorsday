"""
Agent A4 — File & Document Agent.
"""

from langchain.agents import create_agent

from tools.file_document_tools import (
    clear_pending_confirmation,
    get_pending_confirmation_id,
    request_delete_confirmation,
    reset_delete_context,
    set_delete_context,
    wait_for_delete_confirmation,
)
from tools.tool_registry import A4_TOOLS


AGENT_A4_DESCRIPTION = """
A4 is the File & Document Agent.

A4 manages files and documents on the user's local computer.

Use A4 when the user asks to:

- Search for files by name, type, location, or keyword.
- Find documents across directories.
- Read TXT, Markdown, CSV, JSON, PDF, DOCX and other supported files.
- Read relevant sections of documents.
- Create text, Markdown, JSON, CSV and DOCX documents.
- Modify existing text-based files.
- Append information to files.
- Rename files and folders.
- Move files and folders.
- Create directories.
- List directory contents.
- Delete files or directories.
- Compare two documents.
- Extract information from documents.
- Summarize documents.
- Classify documents.
- Retrieve file metadata.

IMPORTANT DELETION RULE:

A4 must NEVER directly delete a file or directory.

When the user requests deletion:

1. Verify the requested path using the available tools.
2. Call request_delete_confirmation.
3. Tell the system that confirmation is required.
4. Wait for the user's Delete/Cancel decision.
5. Never claim deletion before the confirmation result says deleted.
6. Never invent or fabricate a confirmation.
7. Never use a frontend-supplied path for deletion.
"""


_NAME = "Agent A4 (File & Document Agent)"


def _is_delete_request(task: str) -> bool:
    """
    Detect whether the user's request is asking to delete/remove
    a file or directory.

    This is intentionally conservative. We only use this shortcut
    when the request contains both a destructive verb and a
    filesystem object/path indication.
    """

    text = task.lower().strip()

    delete_words = (
        "delete",
        "remove",
        "erase",
        "destroy",
    )

    has_delete_word = any(
        word in text
        for word in delete_words
    )

    if not has_delete_word:
        return False

    path_indicators = (
        "\\",
        "/",
        ".txt",
        ".pdf",
        ".docx",
        ".doc",
        ".csv",
        ".json",
        ".md",
        ".log",
    )

    has_path_indicator = any(
        indicator in text
        for indicator in path_indicators
    )

    return has_path_indicator


def _extract_delete_path(task: str) -> str | None:
    """
    Extract a Windows/Unix filesystem path from a deletion request.

    This is only used to identify the requested path before asking
    for confirmation. The backend remains authoritative for deletion.
    """

    text = task.strip()

    # Windows absolute path:
    # C:\Users\...\file.txt
    windows_match = __import__("re").search(
        r'([A-Za-z]:\\[^"\n\r]+)',
        text,
    )

    if windows_match:
        path = windows_match.group(1).strip()

        # Remove common trailing punctuation.
        path = path.rstrip(".,;:!?")

        return path

    # Quoted path.
    quoted_match = __import__("re").search(
        r'"([^"]+)"',
        text,
    )

    if quoted_match:
        return quoted_match.group(1).strip()

    # Unix-style absolute path.
    unix_match = __import__("re").search(
        r'(/[^\s"\']+)',
        text,
    )

    if unix_match:
        path = unix_match.group(1).strip()
        return path.rstrip(".,;:!?")

    return None


async def run_agent_a4(
    model,
    task: str,
    context: str = "",
    callbacks: list | None = None,
    **kwargs
) -> str:
    """
    Run the A4 File & Document Agent.

    Deletion requests are handled explicitly before invoking the LLM.
    This guarantees that deletion always enters the confirmation flow
    instead of allowing the model to merely describe how to delete.
    """
    req_id : str = kwargs.get("req_id", "")
    task_id : str = kwargs.get("task_id", "")
    delete_context_token = set_delete_context(
        req_id,
        task_id,
    )

    clear_pending_confirmation()

    try:
        # ---------------------------------------------------------------
        # DELETION
        #
        # Handle deletion requests deterministically.
        # Do not rely on the LLM deciding to call the confirmation tool.
        # ---------------------------------------------------------------

        if _is_delete_request(task):

            delete_path = _extract_delete_path(task)

            if not delete_path:
                return (
                    "I detected a deletion request, but I could not "
                    "identify the exact file or directory path. "
                    "Please provide the full path."
                )

            confirmation_response = request_delete_confirmation.invoke(
                {
                    "path": delete_path,
                    "recursive": False,
                }
            )

            confirmation_id = (
                get_pending_confirmation_id()
            )

            # The confirmation tool should have created a pending
            # confirmation. If it did not, do not continue.
            if not confirmation_id:
                return confirmation_response

            # -----------------------------------------------------------
            # Wait for the frontend/backend confirmation.
            # -----------------------------------------------------------

            confirmation_result = (
                await wait_for_delete_confirmation(
                    confirmation_id
                )
            )

            clear_pending_confirmation()

            status = confirmation_result.get(
                "status"
            )

            if status == "deleted":
                return (
                    "Deletion completed successfully.\n"
                    f"Deleted path: "
                    f"{confirmation_result.get('path')}"
                )

            if status == "cancelled":
                return (
                    "Deletion cancelled by the user.\n"
                    f"Path: "
                    f"{confirmation_result.get('path')}"
                )

            if status == "expired":
                return (
                    "Deletion was not performed.\n"
                    "The confirmation request expired."
                )

            return (
                "Deletion was not performed.\n"
                f"{confirmation_result.get('message', 'Unknown result.')}"
            )

        # ---------------------------------------------------------------
        # NORMAL A4 OPERATIONS
        # ---------------------------------------------------------------

        agent = create_agent(
            model=model,
            tools=A4_TOOLS,
        )

        prompt = f"""
You are {_NAME}.

Your responsibility:

{AGENT_A4_DESCRIPTION}

User task:
{task}

Results from previous agents:
{context}

Execution rules:

- Determine the user's requested filesystem/document operation.
- Always use your tools instead of guessing.
- Never invent file paths.
- When searching, search the requested directory when useful.
- When reading documents, return relevant information.
- When creating files, use the requested location.
- When modifying files, preserve unrelated content.
- Verify sources before rename/move operations.
- Never report an operation as completed unless a tool confirms success.

IMPORTANT:

Deletion requests are handled by the system before reaching this
agent prompt. Do not provide manual deletion instructions.

Perform the task now.
"""

        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            },
            config={
                "callbacks": callbacks,
            }
            if callbacks
            else None,
        )

        return result["messages"][-1].content

    finally:
        reset_delete_context(
            delete_context_token
        )