"""
Delete confirmation service.

The frontend never supplies the filesystem path for deletion.
The path comes only from the pending Redis confirmation record.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import redis


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

REDIS_HOST = "localhost"
REDIS_PORT = 6379

CONFIRMATION_TTL = 300
CONFIRMATION_KEY_PREFIX = "agentos:delete_confirmation:"

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
)


def _confirmation_key(
    confirmation_id: str,
) -> str:
    return (
        f"{CONFIRMATION_KEY_PREFIX}"
        f"{confirmation_id}"
    )


# ---------------------------------------------------------------------------
# Confirmation record
# ---------------------------------------------------------------------------

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


def _save_confirmation_record(
    confirmation_id: str,
    record: dict[str, Any],
) -> None:
    key = _confirmation_key(confirmation_id)

    # Preserve the remaining TTL.
    ttl = redis_client.ttl(key)

    if ttl <= 0:
        ttl = CONFIRMATION_TTL

    redis_client.set(
        key,
        json.dumps(record),
        ex=ttl,
    )


# ---------------------------------------------------------------------------
# Fingerprint
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_confirmation(
    *,
    req_id: str,
    task_id: str,
    confirmation_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:

    if not confirmation_id:
        return None, {
            "success": False,
            "status": "error",
            "message": "confirmation_id is required.",
        }

    record = _get_confirmation_record(
        confirmation_id
    )

    if record is None:
        return None, {
            "success": False,
            "status": "expired",
            "message": (
                "Delete confirmation expired "
                "or does not exist."
            ),
        }

    # ---------------------------------------------------------------
    # Validate request identity
    # ---------------------------------------------------------------

    if record.get("req_id") != req_id:
        return None, {
            "success": False,
            "status": "error",
            "message": (
                "Request ID does not match confirmation."
            ),
        }

    if record.get("task_id") != task_id:
        return None, {
            "success": False,
            "status": "error",
            "message": (
                "Task ID does not match confirmation."
            ),
        }

    # ---------------------------------------------------------------
    # Prevent replay
    # ---------------------------------------------------------------

    if record.get("status") != "pending":
        return None, {
            "success": False,
            "status": record.get("status", "unknown"),
            "message": (
                "This delete confirmation has already "
                "been resolved."
            ),
        }

    return record, None


# ---------------------------------------------------------------------------
# Cancel deletion
# ---------------------------------------------------------------------------

async def cancel_delete(
    *,
    confirmation_id: str,
    req_id: str,
    task_id: str,
) -> dict[str, Any]:

    record, error = _validate_confirmation(
        confirmation_id=confirmation_id,
        req_id=req_id,
        task_id=task_id,
    )

    if error is not None:
        return error

    assert record is not None

    record["status"] = "cancelled"

    _save_confirmation_record(
        confirmation_id,
        record,
    )

    path = record.get("path")

    return {
        "success": True,
        "status": "cancelled",
        "path": path,
        "message": (
            f"Deletion cancelled: {path}"
        ),
    }


# ---------------------------------------------------------------------------
# Confirm deletion
# ---------------------------------------------------------------------------

async def confirm_delete(
    *,
    confirmation_id: str,
    req_id: str,
    task_id: str,
) -> dict[str, Any]:

    record, error = _validate_confirmation(
        confirmation_id=confirmation_id,
        req_id=req_id,
        task_id=task_id,
    )

    if error is not None:
        return error

    assert record is not None

    # ---------------------------------------------------------------
    # Get path ONLY from Redis
    # ---------------------------------------------------------------

    path_string = record.get("path")

    if not path_string:
        record["status"] = "failed"
        record["error"] = (
            "Confirmation contains no path."
        )

        _save_confirmation_record(
            confirmation_id,
            record,
        )

        return {
            "success": False,
            "status": "failed",
            "message": (
                "Confirmation contains no path."
            ),
        }

    path = Path(path_string)

    # ---------------------------------------------------------------
    # Verify that the object still exists
    # ---------------------------------------------------------------

    if not path.exists() and not path.is_symlink():
        record["status"] = "failed"
        record["error"] = (
            f"Path no longer exists: {path}"
        )

        _save_confirmation_record(
            confirmation_id,
            record,
        )

        return {
            "success": False,
            "status": "failed",
            "path": str(path),
            "message": (
                f"Path no longer exists: {path}"
            ),
        }

    # ---------------------------------------------------------------
    # Verify filesystem fingerprint
    #
    # The object must still be the same object that was
    # presented when the confirmation was requested.
    # ---------------------------------------------------------------

    try:
        current_fingerprint = _fingerprint(path)

    except Exception as exc:
        record["status"] = "failed"
        record["error"] = (
            f"Could not inspect path: "
            f"{type(exc).__name__}: {exc}"
        )

        _save_confirmation_record(
            confirmation_id,
            record,
        )

        return {
            "success": False,
            "status": "failed",
            "path": str(path),
            "message": record["error"],
        }

    original_fingerprint = record.get(
        "fingerprint"
    )

    if (
        original_fingerprint is not None
        and current_fingerprint != original_fingerprint
    ):
        record["status"] = "failed"
        record["error"] = (
            "The file or directory changed after "
            "the confirmation dialog was shown. "
            "Nothing was deleted."
        )

        _save_confirmation_record(
            confirmation_id,
            record,
        )

        return {
            "success": False,
            "status": "failed",
            "path": str(path),
            "message": record["error"],
        }

    # ---------------------------------------------------------------
    # Perform deletion
    # ---------------------------------------------------------------

    try:
        # Directories must explicitly request recursive deletion.
        if path.is_dir() and not path.is_symlink():

            if not record.get("recursive", False):
                record["status"] = "failed"
                record["error"] = (
                    "The requested directory deletion "
                    "is not recursive."
                )

                _save_confirmation_record(
                    confirmation_id,
                    record,
                )

                return {
                    "success": False,
                    "status": "failed",
                    "path": str(path),
                    "message": record["error"],
                }

            shutil.rmtree(path)

        else:
            # Files and symlinks are removed as a single filesystem entry.
            path.unlink()

    except Exception as exc:
        record["status"] = "failed"
        record["error"] = (
            f"Deletion failed: "
            f"{type(exc).__name__}: {exc}"
        )

        _save_confirmation_record(
            confirmation_id,
            record,
        )

        return {
            "success": False,
            "status": "failed",
            "path": str(path),
            "message": record["error"],
        }

    # ---------------------------------------------------------------
    # Success
    # ---------------------------------------------------------------

    record["status"] = "deleted"

    _save_confirmation_record(
        confirmation_id,
        record,
    )

    return {
        "success": True,
        "status": "deleted",
        "path": str(path),
        "message": f"Deleted: {path}",
    }


# ---------------------------------------------------------------------------
# Backward-compatible resolver
# ---------------------------------------------------------------------------

def resolve_delete_confirmation(
    *,
    req_id: str,
    task_id: str,
    confirmation_id: str,
    confirmed: bool,
) -> dict[str, Any]:
    """
    Backward-compatible synchronous resolver.

    New backend code should use:
        confirm_delete()
        cancel_delete()

    This function is kept so existing code importing
    resolve_delete_confirmation does not break.
    """

    import asyncio

    if confirmed:
        return asyncio.run(
            confirm_delete(
                confirmation_id=confirmation_id,
                req_id=req_id,
                task_id=task_id,
            )
        )

    return asyncio.run(
        cancel_delete(
            confirmation_id=confirmation_id,
            req_id=req_id,
            task_id=task_id,
        )
    )