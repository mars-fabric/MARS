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


# WebSocket endpoint for RFP stage execution
@app.websocket("/ws/rfp/{task_id}/{stage_num}")
async def rfp_websocket_endpoint(websocket: WebSocket, task_id: str, stage_num: int):
    """WebSocket endpoint for streaming RFP stage execution output."""
    import asyncio
    from routers.rfp import _get_console_lines, _clear_console_buffer

    await websocket.accept()

    buf_key = f"{task_id}:{stage_num}"
    line_index = 0

    try:
        await send_ws_event(websocket, "status", {
            "message": f"Connected to RFP stage {stage_num}",
            "stage_num": stage_num,
        }, run_id=task_id)

        while True:
            await asyncio.sleep(1)

            new_lines = _get_console_lines(buf_key, since_index=line_index)
            for line in new_lines:
                await send_ws_event(websocket, "console_output", {
                    "text": line,
                    "stage_num": stage_num,
                }, run_id=task_id)
            line_index += len(new_lines)

            try:
                from cmbagent.database.base import get_db_session
                db = get_db_session()
                try:
                    from routers.rfp import _get_session_id_for_task, _get_stage_repo
                    session_id = _get_session_id_for_task(task_id, db)
                    repo = _get_stage_repo(db, session_id=session_id)
                    stages = repo.list_stages(parent_run_id=task_id)
                    stage = next((s for s in stages if s.stage_number == stage_num), None)
                    if stage:
                        if stage.status == "completed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_completed", {
                                "stage_num": stage_num,
                                "stage_name": stage.stage_name,
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                        elif stage.status == "failed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_failed", {
                                "stage_num": stage_num,
                                "error": stage.error_message or "Stage failed",
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                finally:
                    db.close()
            except Exception:
                pass
    except Exception:
        pass


# WebSocket endpoint for Deepresearch stage execution
@app.websocket("/ws/deepresearch/{task_id}/{stage_num}")
async def deepresearch_websocket_endpoint(websocket: WebSocket, task_id: str, stage_num: int):
    """WebSocket endpoint for streaming Deepresearch stage execution output.

    Streams console output from the shared buffer in real-time and sends
    stage_completed/stage_failed events when the phase finishes.
    """
    import asyncio
    from routers.deepresearch import _get_console_lines, _clear_console_buffer

    await websocket.accept()

    buf_key = f"{task_id}:{stage_num}"
    line_index = 0

    try:
        await send_ws_event(websocket, "status", {
            "message": f"Connected to stage {stage_num}",
            "stage_num": stage_num,
        }, run_id=task_id)

        while True:
            await asyncio.sleep(1)

            # Stream new console output lines
            new_lines = _get_console_lines(buf_key, since_index=line_index)
            for line in new_lines:
                await send_ws_event(websocket, "console_output", {
                    "text": line,
                    "stage_num": stage_num,
                }, run_id=task_id)
            line_index += len(new_lines)

            # Check DB for stage completion (every cycle)
            try:
                from cmbagent.database.base import get_db_session
                db = get_db_session()
                try:
                    from routers.deepresearch import _get_session_id_for_task, _get_stage_repo
                    session_id = _get_session_id_for_task(task_id, db)
                    repo = _get_stage_repo(db, session_id=session_id)
                    stages = repo.list_stages(parent_run_id=task_id)
                    stage = next((s for s in stages if s.stage_number == stage_num), None)
                    if stage:
                        if stage.status == "completed":
                            # Flush remaining console lines
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_completed", {
                                "stage_num": stage_num,
                                "stage_name": stage.stage_name,
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                        elif stage.status == "failed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_failed", {
                                "stage_num": stage_num,
                                "error": stage.error_message or "Stage failed",
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                finally:
                    db.close()
            except Exception:
                pass
    except Exception:
        pass


# WebSocket endpoint for News Pulse stage execution
@app.websocket("/ws/newspulse/{task_id}/{stage_num}")
async def newspulse_websocket_endpoint(websocket: WebSocket, task_id: str, stage_num: int):
    """WebSocket endpoint for streaming News Pulse stage execution output."""
    import asyncio
    from routers.newspulse import _get_console_lines, _clear_console_buffer

    await websocket.accept()

    buf_key = f"np:{task_id}:{stage_num}"
    line_index = 0

    try:
        await send_ws_event(websocket, "status", {
            "message": f"Connected to stage {stage_num}",
            "stage_num": stage_num,
        }, run_id=task_id)

        while True:
            await asyncio.sleep(1)

            new_lines = _get_console_lines(buf_key, since_index=line_index)
            for line in new_lines:
                await send_ws_event(websocket, "console_output", {
                    "text": line,
                    "stage_num": stage_num,
                }, run_id=task_id)
            line_index += len(new_lines)

            try:
                from cmbagent.database.base import get_db_session
                db = get_db_session()
                try:
                    from routers.newspulse import _get_session_id_for_task, _get_stage_repo
                    session_id = _get_session_id_for_task(task_id, db)
                    repo = _get_stage_repo(db, session_id=session_id)
                    stages = repo.list_stages(parent_run_id=task_id)
                    stage = next((s for s in stages if s.stage_number == stage_num), None)
                    if stage:
                        if stage.status == "completed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_completed", {
                                "stage_num": stage_num,
                                "stage_name": stage.stage_name,
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                        elif stage.status == "failed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_failed", {
                                "stage_num": stage_num,
                                "error": stage.error_message or "Stage failed",
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                finally:
                    db.close()
            except Exception:
                pass
    except Exception:
        pass


# WebSocket endpoint for PDA stage execution
@app.websocket("/ws/pda/{task_id}/{stage_num}")
async def pda_websocket_endpoint(websocket: WebSocket, task_id: str, stage_num: int):
    """WebSocket endpoint for streaming PDA stage execution output."""
    import asyncio
    from routers.pda import _get_console_lines, _clear_console_buffer

    await websocket.accept()

    buf_key = f"pda:{task_id}:{stage_num}"
    line_index = 0

    try:
        await send_ws_event(websocket, "status", {
            "message": f"Connected to PDA stage {stage_num}",
            "stage_num": stage_num,
        }, run_id=task_id)

        while True:
            await asyncio.sleep(1)

            new_lines = _get_console_lines(buf_key, since_index=line_index)
            for line in new_lines:
                await send_ws_event(websocket, "console_output", {
                    "text": line,
                    "stage_num": stage_num,
                }, run_id=task_id)
            line_index += len(new_lines)

            try:
                from cmbagent.database.base import get_db_session
                db = get_db_session()
                try:
                    from routers.pda import _get_session_id_for_task, _get_stage_repo
                    session_id = _get_session_id_for_task(task_id, db)
                    repo = _get_stage_repo(db, session_id=session_id)
                    stages = repo.list_stages(parent_run_id=task_id)
                    stage = next((s for s in stages if s.stage_number == stage_num), None)
                    if stage:
                        if stage.status == "completed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_completed", {
                                "stage_num": stage_num,
                                "stage_name": stage.stage_name,
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                        elif stage.status == "failed":
                            remaining = _get_console_lines(buf_key, since_index=line_index)
                            for line in remaining:
                                await send_ws_event(websocket, "console_output", {
                                    "text": line,
                                    "stage_num": stage_num,
                                }, run_id=task_id)
                            await send_ws_event(websocket, "stage_failed", {
                                "stage_num": stage_num,
                                "error": stage.error_message or "Stage failed",
                            }, run_id=task_id)
                            _clear_console_buffer(buf_key)
                            break
                finally:
                    db.close()
            except Exception:
                pass
    except Exception:
        pass


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
