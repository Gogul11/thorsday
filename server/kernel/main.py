"""Kernel entry point — startup and connection checks only.

Responsibilities
----------------
1. Verify MongoDB and Redis connections are alive.
2. Warm up the LangGraph (build it before the first request arrives).
3. Subscribe to the 'backend_tasks' Redis channel and hand every message
   to the dispatcher.

Nothing else lives here. Business logic belongs in:
  services/task_runner.py  — graph execution and context management
  services/dispatcher.py   — Redis event routing
  graphs/main_agent_graph.py — the LangGraph pipeline
"""

import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from DB.mongodb import mongo_client
from logger import logger
from Redis.redis_connection import redis_client, subscribe
from services.dispatcher import handle_backend_task
from services.task_runner import warmup


async def main() -> None:
    # ------------------------------------------------------------------
    # 1. Verify connections
    # ------------------------------------------------------------------
    try:
        await mongo_client.admin.command("ping")
        logger.info("MongoDB connection established")
    except Exception as exc:
        logger.exception("MongoDB connection failed: %s", exc)
        raise

    try:
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.exception("Redis connection failed: %s", exc)
        raise

    # ------------------------------------------------------------------
    # 2. Pre-build the graph so the first request isn't slow
    # ------------------------------------------------------------------
    warmup()
    logger.info("Kernel ready — listening on 'backend_tasks'")

    # ------------------------------------------------------------------
    # 3. Block forever, dispatching every incoming Redis message
    # ------------------------------------------------------------------
    await subscribe("backend_tasks", handle_backend_task)


if __name__ == "__main__":
    asyncio.run(main())
