"""
API Routers for the CMBAgent backend.

Each router module handles a specific domain of functionality.
"""

from fastapi import APIRouter

from routers.health import router as health_router
from routers.files import router as files_router
from routers.credentials import router as credentials_router
from routers.arxiv import router as arxiv_router
from routers.enhance import router as enhance_router
from routers.branching import router as branching_router
from routers.runs import router as runs_router
from routers.nodes import router as nodes_router
from routers.tasks import router as tasks_router
from routers.phases import router as phases_router
from routers.copilot import router as copilot_router
from routers.sessions import router as sessions_router
from routers.pda import router as pda_router


def register_routers(app):
    """Register all routers with the FastAPI application."""
    app.include_router(health_router)
    app.include_router(tasks_router)
    app.include_router(phases_router)  # Phase-based workflows
    app.include_router(copilot_router)  # Copilot mode
    app.include_router(sessions_router)  # Session management (Stage 10)
    app.include_router(files_router)
    app.include_router(credentials_router)
    app.include_router(arxiv_router)
    app.include_router(enhance_router)
    app.include_router(branching_router)
    app.include_router(runs_router)
    app.include_router(nodes_router)
    app.include_router(pda_router)  # Product Discovery Assistant


__all__ = [
    "register_routers",
    "health_router",
    "files_router",
    "credentials_router",
    "arxiv_router",
    "enhance_router",
    "branching_router",
    "runs_router",
    "nodes_router",
    "tasks_router",
    "phases_router",
    "copilot_router",
    "sessions_router",
    "pda_router",
]
