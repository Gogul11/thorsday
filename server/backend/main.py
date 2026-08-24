import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Agents.main_agent import Main_Agent
from backend.controller.task_controller import TaskController
from backend.repo.task_repo import TaskRepository
from backend.routes.task_routes import create_task_router
from backend.svc.task_service import TaskService
from models.model import Models


def create_app() -> FastAPI:
    models = Models()
    repository = TaskRepository()
    service = TaskService(lambda: Main_Agent(models), repository)
    controller = TaskController(service)

    app = FastAPI(
        title="AgentOS API",
        description="Asynchronous API for running AgentOS tasks.",
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
    app.include_router(create_task_router(controller))
    return app


app = create_app()
