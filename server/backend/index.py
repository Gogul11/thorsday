"""AgentOS Backend — application entry point.

Run (from the server/ directory):
    uvicorn backend.index:app --reload

Or run (from the backend/ directory):
    uvicorn index:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Redis.redis_connection import redis_close
from routes.task_routes import router as task_router
from services.kernel_listener import start_kernel_listener


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the kernel-event listener on startup; shut everything down cleanly."""
    listener_task = await start_kernel_listener()

    yield  # application is running

    listener_task.cancel()
    await redis_close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentOS API",
        description=(
            "POST /task — submit a prompt, receive a req_id.\n"
            "WS  /ws/{req_id} — stream live kernel events for that task."
        ),
        version="2.0.0",
        lifespan=lifespan,
    )

    allowed_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(task_router)

    return app


app = create_app()
