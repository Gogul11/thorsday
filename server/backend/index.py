"""AgentOS Backend — application entry point.

Creates and configures the FastAPI app. No class instantiation required;
all state lives in module-level stores inside each subpackage.

Run with:
    uvicorn backend.index:app --reload
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.task_routes import router as task_router
from svc.redis_service import lifespan


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentOS API",
        description="Asynchronous API for running AgentOS tasks.",
        lifespan=lifespan,
    )

    allowed_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(task_router)

    return app


app = create_app()
