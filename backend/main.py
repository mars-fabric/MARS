"""
CMBAgent Backend API - Main Entry Point

This module assembles all components and starts the FastAPI application.
The backend is organized into the following modules:
- core/: App configuration and initialization
- models/: Pydantic schemas for request/response validation
- routers/: API endpoint handlers organized by domain
- websocket/: WebSocket handlers and event utilities
- execution/: CMBAgent task execution, stream capture, DAG tracking
- services/: Workflow, connection, and execution services
"""

import sys
from pathlib import Path

# Add the parent directory to the path to import cmbagent
sys.path.append(str(Path(__file__).parent.parent))
# Add the backend directory to the path to import local modules
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket

# Import core app factory
from core.app import create_app

# Import routers
from routers import register_routers

# Import WebSocket components
from websocket.events import send_ws_event
from websocket.handlers import websocket_endpoint as ws_handler

# Import execution components
from execution.task_executor import execute_cmbagent_task

# Create the FastAPI application
app = create_app()

# Register all REST API routers
register_routers(app)


# WebSocket endpoint
@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time task execution updates."""
    await ws_handler(websocket, task_id, execute_cmbagent_task)


# For backward compatibility - expose some common utilities
def resolve_run_id(run_id: str) -> str:
    """Resolve task_id to database run_id if available."""
    try:
        from services import workflow_service
        run_info = workflow_service.get_run_info(run_id)
        if run_info and run_info.get("db_run_id"):
            return run_info["db_run_id"]
    except ImportError:
        pass
    return run_id


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
