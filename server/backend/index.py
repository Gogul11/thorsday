import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Redis.redis_connection import RedisPubSub
from controller.task_controller import TaskController
from repo.task_repo import TaskRepository
from routes.task_routes import create_task_router
from svc.redis_service import create_lifespan
from svc.task_service import TaskService


redis_client = RedisPubSub()


def create_app() -> FastAPI:

    repository = TaskRepository()

    service = TaskService(
        redis_client,
        repository
    )

    controller = TaskController(service)

    app = FastAPI(
        title="AgentOS API",
        description="Asynchronous API for running AgentOS tasks.",
        lifespan=create_lifespan(redis_client)
    )

    allowed_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in allowed_origins
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        create_task_router(controller)
    )

    return app


app = create_app()