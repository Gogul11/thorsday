from fastapi import FastAPI

from Agents.main_agent import Main_Agent
from backend.controller.task_controller import TaskController
from backend.repo.task_repo import TaskRepository
from backend.routes.task_routes import create_task_router
from backend.svc.task_service import TaskService
from models.model import Models


def create_app() -> FastAPI:
    models = Models()
    agent = Main_Agent(models)
    repository = TaskRepository()
    service = TaskService(agent, repository)
    controller = TaskController(service)

    app = FastAPI(
        title="AgentOS API",
        description="Asynchronous API for running AgentOS tasks.",
    )
    app.include_router(create_task_router(controller))
    return app


app = create_app()
