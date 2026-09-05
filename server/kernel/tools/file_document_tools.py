"""
File and Document tools for Agent A4.

Supported capabilities:
- file search
- document reading
- text file creation
- DOCX creation
- append
- replace
- folder creation
- rename
- move
- delete confirmation
- metadata
- directory listing
- document comparison
- document classification

Destructive operations:
    A4 NEVER directly deletes a file.

    A4 calls request_delete_confirmation(), which:
      1. Creates a pending confirmation in Redis.
      2. Sends DELETE_CONFIRMATION_REQUIRED to the frontend.
      3. Waits for the backend/user decision.
      4. Returns only after the backend has deleted/cancelled the object.
"""

from __future__ import annotations

import contextvars
import difflib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import redis

from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

REDIS_HOST = "localhost"
REDIS_PORT = 6379

CONFIRMATION_TTL = 300

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
)

CONFIRMATION_KEY_PREFIX = "agentos:delete_confirmation:"


def _confirmation_key(
    confirmation_id: str,
) -> str:
    return (
        f"{CONFIRMATION_KEY_PREFIX}"
        f"{confirmation_id}"
    )


# ---------------------------------------------------------------------------
# Request context
# ---------------------------------------------------------------------------

_delete_context: contextvars.ContextVar[
    tuple[str, str] | None
] = contextvars.ContextVar(
    "a4_delete_context",
    default=None,
)

_pending_confirmation: contextvars.ContextVar[
    str | None
] = contextvars.ContextVar(
    "a4_pending_confirmation",
    default=None,
)


def set_delete_context(
    req_id: str,
    task_id: str,
):
    return _delete_context.set(
        (req_id, task_id)
    )


def reset_delete_context(token):
    _delete_context.reset(token)


def get_pending_confirmation_id() -> str | None:
    return _pending_confirmation.get()


def clear_pending_confirmation():
    _pending_confirmation.set(None)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@tool
def search_files(
    location: str,
    pattern: str = "*",
    keyword: str = "",
    recursive: bool = True,
    limit: int = 100,
    sort_by: str = "name",
    sort_order: str = "asc",
) -> str:
    """
    Search for files in a directory.

    pattern examples:
        *.pdf
        *.docx
        *.txt
        report*.pdf
        *

    keyword optionally searches the filename.
    """

    try:
        root = _resolve_path(location)

        if not root.exists():
            return f"Location does not exist: {root}"

        if not root.is_dir():
            return f"Location is not a directory: {root}"

        limit = max(1, min(limit, 500))

        iterator = (
            root.rglob(pattern)
            if recursive
            else root.glob(pattern)
        )

        results: list[dict[str, Any]] = []

        keyword_lower = keyword.lower().strip()

        for path in iterator:
            try:
                if not path.is_file():
                    continue

                if keyword_lower and keyword_lower not in path.name.lower():
                    continue

                stat = path.stat()

                results.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "type": path.suffix.lower().lstrip(".")
                        or "no_extension",
                        "size": stat.st_size,
                        "created": (
                            __import__("datetime")
                            .datetime
                            .fromtimestamp(stat.st_ctime)
                            .isoformat()
                        ),
                        "modified": (
                            __import__("datetime")
                            .datetime
                            .fromtimestamp(stat.st_mtime)
                            .isoformat()
                        ),
                    }
                )

            except (PermissionError, OSError):
                continue

        sort_by = sort_by.lower()

        if sort_by == "size":
            key_fn = lambda x: x["size"]
        elif sort_by == "created":
            key_fn = lambda x: x["created"]
        elif sort_by == "modified":
            key_fn = lambda x: x["modified"]
        else:
            key_fn = lambda x: x["name"].lower()

        reverse = sort_order.lower() == "desc"

        results.sort(
            key=key_fn,
            reverse=reverse,
        )

        results = results[:limit]

        return json.dumps(
            {
                "location": str(root),
                "pattern": pattern,
                "keyword": keyword,
                "recursive": recursive,
                "count": len(results),
                "files": results,
            },
            indent=2,
        )

    except Exception as exc:
        return f"File search failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Document reading
# ---------------------------------------------------------------------------


def _read_text_file(
    path: Path,
) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _read_pdf(
    path: Path,
) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))

    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return "\n\n".join(pages)


def _read_docx(
    path: Path,
) -> str:
    from docx import Document

    document = Document(str(path))

    paragraphs = [
        p.text
        for p in document.paragraphs
        if p.text.strip()
    ]

    return "\n".join(paragraphs)


@tool
def read_document(
    path: str,
    start_keyword: str = "",
    end_keyword: str = "",
    max_chars: int = 30000,
) -> str:
    """
    Read a supported document.

    Supports:
        TXT
        MD
        CSV
        JSON
        XML
        HTML
        LOG
        PDF
        DOCX
        source/config text files
    """

    try:
        resolved = _resolve_path(path)

        if not resolved.exists():
            return f"File does not exist: {resolved}"

        if not resolved.is_file():
            return f"Not a file: {resolved}"

        suffix = resolved.suffix.lower()

        if suffix == ".pdf":
            content = _read_pdf(resolved)

        elif suffix == ".docx":
            content = _read_docx(resolved)

        else:
            content = _read_text_file(resolved)

        # ---------------------------------------------------------------
        # Optional bounded section
        # ---------------------------------------------------------------

        if start_keyword:
            start_index = content.lower().find(
                start_keyword.lower()
            )

            if start_index == -1:
                return (
                    f"Start keyword not found: "
                    f"{start_keyword}"
                )

            content = content[start_index:]

        if end_keyword:
            end_index = content.lower().find(
                end_keyword.lower()
            )

            if end_index != -1:
                content = content[:end_index + len(end_keyword)]

        content = content[:max_chars]

        return content

    except Exception as exc:
        return f"Document read failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------


@tool
def create_text_file(
    path: str,
    content: str,
    overwrite: bool = False,
) -> str:
    """Create a text/Markdown/JSON/CSV file."""

    try:
        resolved = _resolve_path(path)

        if resolved.exists() and not overwrite:
            return (
                f"File already exists: {resolved}. "
                f"Use overwrite=true if replacement is intended."
            )

        resolved.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        resolved.write_text(
            content,
            encoding="utf-8",
        )

        return f"Created file: {resolved}"

    except Exception as exc:
        return f"File creation failed: {_safe_error(exc)}"


@tool
def create_docx_file(
    path: str,
    content: str,
    overwrite: bool = False,
) -> str:
    """Create a DOCX document."""

    try:
        from docx import Document

        resolved = _resolve_path(path)

        if resolved.exists() and not overwrite:
            return (
                f"File already exists: {resolved}. "
                f"Use overwrite=true if replacement is intended."
            )

        resolved.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        document = Document()

        for paragraph in content.splitlines():
            document.add_paragraph(paragraph)

        document.save(str(resolved))

        return f"Created DOCX: {resolved}"

    except Exception as exc:
        return f"DOCX creation failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# File modification
# ---------------------------------------------------------------------------


@tool
def append_to_file(
    path: str,
    content: str,
) -> str:
    """Append text to an existing text file."""

    try:
        resolved = _resolve_path(path)

        if not resolved.exists():
            return f"File does not exist: {resolved}"

        if not resolved.is_file():
            return f"Not a file: {resolved}"

        with resolved.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(content)

        return f"Appended content to: {resolved}"

    except Exception as exc:
        return f"Append failed: {_safe_error(exc)}"


@tool
def replace_in_file(
    path: str,
    old_text: str,
    new_text: str,
) -> str:
    """Replace exact text inside an existing text file."""

    try:
        resolved = _resolve_path(path)

        if not resolved.exists():
            return f"File does not exist: {resolved}"

        content = _read_text_file(resolved)

        if old_text not in content:
            return "The requested text was not found."

        updated = content.replace(
            old_text,
            new_text,
        )

        resolved.write_text(
            updated,
            encoding="utf-8",
        )

        return f"Updated file: {resolved}"

    except Exception as exc:
        return f"File modification failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Folder
# ---------------------------------------------------------------------------


@tool
def create_folder(
    path: str,
) -> str:
    """Create a directory."""

    try:
        resolved = _resolve_path(path)

        resolved.mkdir(
            parents=True,
            exist_ok=True,
        )

        return f"Created folder: {resolved}"

    except Exception as exc:
        return f"Folder creation failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------


@tool
def rename_file(
    path: str,
    new_name: str,
) -> str:
    """Rename a file or directory."""

    try:
        resolved = _resolve_path(path)

        if not resolved.exists():
            return f"Path does not exist: {resolved}"

        if Path(new_name).name != new_name:
            return (
                "new_name must contain only the new "
                "file or folder name."
            )

        destination = resolved.parent / new_name

        if destination.exists():
            return f"Destination already exists: {destination}"

        resolved.rename(destination)

        return (
            f"Renamed:\n"
            f"  From: {resolved}\n"
            f"  To:   {destination}"
        )

    except Exception as exc:
        return f"Rename failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Move
# ---------------------------------------------------------------------------


@tool
def move_file(
    path: str,
    destination_directory: str,
) -> str:
    """Move a file or directory."""

    try:
        source = _resolve_path(path)
        destination = _resolve_path(
            destination_directory
        )

        if not source.exists():
            return f"Source does not exist: {source}"

        if not destination.exists():
            return (
                f"Destination directory does not exist: "
                f"{destination}"
            )

        if not destination.is_dir():
            return (
                f"Destination is not a directory: "
                f"{destination}"
            )

        final_path = destination / source.name

        if final_path.exists():
            return (
                f"Destination already exists: "
                f"{final_path}"
            )

        source.rename(final_path)

        return (
            f"Moved:\n"
            f"  From: {source}\n"
            f"  To:   {final_path}"
        )

    except Exception as exc:
        return f"Move failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# DELETE CONFIRMATION
# ---------------------------------------------------------------------------


def _fingerprint(
    path: Path,
) -> dict[str, Any]:
    stat = path.stat()

    return {
        "is_dir": path.is_dir(),
        "is_symlink": path.is_symlink(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "inode": getattr(stat, "st_ino", 0),
    }


@tool
def request_delete_confirmation(
    path: str,
    recursive: bool = False,
) -> str:
    """
    Request human confirmation before deletion.

    IMPORTANT:
        This function NEVER deletes the path.

    It creates a Redis pending confirmation and emits
    DELETE_CONFIRMATION_REQUIRED to the frontend.
    """

    context = _delete_context.get()

    if context is None:
        return (
            "ERROR: delete confirmation context is unavailable. "
            "Deletion was not performed."
        )

    req_id, task_id = context

    try:
        resolved = _resolve_path(path)

        if not resolved.exists() and not resolved.is_symlink():
            return f"Path does not exist: {resolved}"

        fingerprint = _fingerprint(resolved)

        confirmation_id = os.urandom(16).hex()

        record = {
            "confirmation_id": confirmation_id,
            "req_id": req_id,
            "task_id": task_id,
            "path": str(resolved),
            "recursive": bool(recursive),
            "status": "pending",
            "fingerprint": fingerprint,
        }

        redis_client.set(
            _confirmation_key(confirmation_id),
            json.dumps(record),
            ex=CONFIRMATION_TTL,
        )

        _pending_confirmation.set(
            confirmation_id
        )

        # ---------------------------------------------------------------
        # Send confirmation request to frontend.
        # ---------------------------------------------------------------

        redis_client.publish(
            "kernel_events",
            json.dumps(
                {
                    "event": "DELETE_CONFIRMATION_REQUIRED",
                    "req_id": req_id,
                    "task_id": task_id,
                    "confirmation_id": confirmation_id,
                    "path": str(resolved),
                    "recursive": bool(recursive),
                }
            ),
        )

        object_type = (
            "folder"
            if fingerprint["is_dir"]
            else "file"
        )

        return (
            f"DELETE CONFIRMATION REQUIRED.\n"
            f"Object: {object_type}\n"
            f"Path: {resolved}\n"
            f"Confirmation ID: {confirmation_id}\n"
            f"WAIT for the user's Delete or Cancel decision.\n"
            f"Do not claim that deletion has occurred."
        )

    except Exception as exc:
        return (
            "Could not create delete confirmation: "
            f"{_safe_error(exc)}"
        )


def _get_confirmation_record(
    confirmation_id: str,
) -> dict[str, Any] | None:
    raw = redis_client.get(
        _confirmation_key(confirmation_id)
    )

    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def wait_for_delete_confirmation(
    confirmation_id: str,
) -> dict[str, Any]:
    """
    Wait until the backend processes the user's decision.

    The backend is responsible for the actual filesystem deletion.
    """

    deadline = time.monotonic() + CONFIRMATION_TTL

    while time.monotonic() < deadline:

        record = _get_confirmation_record(
            confirmation_id
        )

        if record is None:
            return {
                "status": "expired",
                "message": (
                    "Delete confirmation expired. "
                    "Nothing was deleted."
                ),
            }

        status = record.get("status")

        if status == "deleted":
            return {
                "status": "deleted",
                "path": record.get("path"),
                "message": (
                    f"Deleted: {record.get('path')}"
                ),
            }

        if status == "cancelled":
            return {
                "status": "cancelled",
                "path": record.get("path"),
                "message": (
                    f"Deletion cancelled: "
                    f"{record.get('path')}"
                ),
            }

        if status == "failed":
            return {
                "status": "failed",
                "path": record.get("path"),
                "message": record.get(
                    "error",
                    "Deletion failed.",
                ),
            }

        time.sleep(0.5)

    return {
        "status": "expired",
        "message": (
            "Delete confirmation expired. "
            "Nothing was deleted."
        ),
    }


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@tool
def get_file_metadata(
    path: str,
) -> str:
    """Return metadata for a file or directory."""

    try:
        resolved = _resolve_path(path)

        if not resolved.exists() and not resolved.is_symlink():
            return f"Path does not exist: {resolved}"

        stat = resolved.stat()

        return json.dumps(
            {
                "name": resolved.name,
                "path": str(resolved),
                "type": (
                    "directory"
                    if resolved.is_dir()
                    else resolved.suffix.lower().lstrip(".")
                    or "file"
                ),
                "size": stat.st_size,
                "created": (
                    __import__("datetime")
                    .datetime
                    .fromtimestamp(stat.st_ctime)
                    .isoformat()
                ),
                "modified": (
                    __import__("datetime")
                    .datetime
                    .fromtimestamp(stat.st_mtime)
                    .isoformat()
                ),
                "is_directory": resolved.is_dir(),
                "is_symlink": resolved.is_symlink(),
            },
            indent=2,
        )

    except Exception as exc:
        return f"Metadata lookup failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Directory listing
# ---------------------------------------------------------------------------


@tool
def list_directory(
    path: str,
) -> str:
    """List files and directories."""

    try:
        resolved = _resolve_path(path)

        if not resolved.exists():
            return f"Directory does not exist: {resolved}"

        if not resolved.is_dir():
            return f"Not a directory: {resolved}"

        entries = []

        for item in sorted(
            resolved.iterdir(),
            key=lambda p: p.name.lower(),
        ):
            entries.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "type": (
                        "directory"
                        if item.is_dir()
                        else "file"
                    ),
                }
            )

        return json.dumps(
            {
                "directory": str(resolved),
                "count": len(entries),
                "entries": entries,
            },
            indent=2,
        )

    except Exception as exc:
        return f"Directory listing failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Document comparison
# ---------------------------------------------------------------------------


@tool
def compare_documents(
    first_path: str,
    second_path: str,
) -> str:
    """Compare two text-readable documents."""

    try:
        first = _resolve_path(first_path)
        second = _resolve_path(second_path)

        if first.suffix.lower() == ".pdf":
            first_text = _read_pdf(first)
        elif first.suffix.lower() == ".docx":
            first_text = _read_docx(first)
        else:
            first_text = _read_text_file(first)

        if second.suffix.lower() == ".pdf":
            second_text = _read_pdf(second)
        elif second.suffix.lower() == ".docx":
            second_text = _read_docx(second)
        else:
            second_text = _read_text_file(second)

        diff = difflib.unified_diff(
            first_text.splitlines(),
            second_text.splitlines(),
            fromfile=str(first),
            tofile=str(second),
            lineterm="",
        )

        output = "\n".join(diff)

        if not output:
            return "The two documents are identical."

        return output

    except Exception as exc:
        return f"Document comparison failed: {_safe_error(exc)}"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


@tool
def classify_document(
    path: str,
) -> str:
    """
    Classify a document using filename/content heuristics.
    """

    try:
        resolved = _resolve_path(path)

        name = resolved.name.lower()

        try:
            if resolved.suffix.lower() == ".pdf":
                content = _read_pdf(resolved)
            elif resolved.suffix.lower() == ".docx":
                content = _read_docx(resolved)
            else:
                content = _read_text_file(resolved)
        except Exception:
            content = ""

        sample = (
            name + "\n" + content[:10000]
        ).lower()

        if any(
            word in sample
            for word in [
                "resume",
                "curriculum vitae",
                "experience",
                "skills",
                "education",
            ]
        ):
            category = "resume"

        elif any(
            word in sample
            for word in [
                "invoice",
                "invoice number",
                "amount due",
                "billing",
            ]
        ):
            category = "invoice"

        elif any(
            word in sample
            for word in [
                "assignment",
                "question",
                "student",
                "submission",
            ]
        ):
            category = "assignment"

        elif any(
            word in sample
            for word in [
                "certificate",
                "certification",
                "awarded",
            ]
        ):
            category = "certificate"

        elif any(
            word in sample
            for word in [
                "report",
                "executive summary",
                "findings",
                "conclusion",
            ]
        ):
            category = "report"

        else:
            category = "general_document"

        return json.dumps(
            {
                "path": str(resolved),
                "classification": category,
            },
            indent=2,
        )

    except Exception as exc:
        return f"Classification failed: {_safe_error(exc)}"