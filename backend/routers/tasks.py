"""
Task submission endpoints.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.schemas import TaskType, TaskRequest, TaskResponse, StageInfo, TaskStatusResponse

from core.logging import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# In-memory storage for task statuses and results
# In production, this should use a database
task_storage: Dict[str, Dict[str, Any]] = {}


class AIWeeklyRequest(BaseModel):
    """Request model for AI Weekly task."""
    tool: str
    parameters: Dict[str, Any]


class AIWeeklyResponse(BaseModel):
    """Response model for AI Weekly task creation."""
    task_id: str
    status: str
    message: str


class TaskConfig(BaseModel):
    """Task configuration for execution."""
    description: str
    config: Dict[str, Any]


@router.post("/submit", response_model=TaskResponse)
async def submit_task(request: TaskRequest):
    """Submit a task for execution.

    Returns a task_id that can be used to connect via WebSocket
    for real-time updates.

    Supports task_type="denario-research" for multi-stage research paper workflows.
    """
    task_id = str(uuid.uuid4())

    if request.task_type == TaskType.DENARIO_RESEARCH:
        # Store denario task with mode set for WebSocket handler
        config = {
            **request.config,
            "mode": "denario-research",
            "data_description": request.data_description,
        }
        task_storage[task_id] = {
            'task_id': task_id,
            'task_type': TaskType.DENARIO_RESEARCH.value,
            'status': 'submitted',
            'created_at': datetime.now().isoformat(),
            'description': request.task,
            'config': config,
        }
        logger.info("denario_task_submitted", task_id=task_id)
    else:
        # Standard task - store minimal info
        task_storage[task_id] = {
            'task_id': task_id,
            'task_type': TaskType.STANDARD.value,
            'status': 'submitted',
            'created_at': datetime.now().isoformat(),
            'description': request.task,
            'config': request.config,
        }

    return TaskResponse(
        task_id=task_id,
        status="submitted",
        message="Task submitted successfully. Connect to WebSocket for real-time updates."
    )


@router.post("/ai-weekly/execute", response_model=AIWeeklyResponse)
async def execute_ai_weekly(request: AIWeeklyRequest):
    """Create and prepare an AI Weekly report task.

    This endpoint creates a task configuration that can be executed
    via WebSocket connection.
    """
    task_id = f"ai-weekly_{uuid.uuid4()}"

    params = request.parameters
    date_from = params.get('dateFrom', '')
    date_to = params.get('dateTo', '')
    topics = params.get('topics', [])
    sources = params.get('sources', [])
    style = params.get('style', 'concise')

    # Create task description
    description = (
        f"Generate an AI Weekly report for {date_from} to {date_to}. "
        f"Topics: {', '.join(topics)}. Sources: {', '.join(sources)}. "
        f"Style: {style}."
    )

    # Store task information
    task_storage[task_id] = {
        'task_id': task_id,
        'tool': 'ai-weekly',
        'task_type': TaskType.STANDARD.value,
        'status': 'created',
        'created_at': datetime.now().isoformat(),
        'parameters': params,
        'description': description,
        'config': {
            'mode': 'planning-control',
            'model': params.get('model', 'gpt-5'),
            'plannerModel': params.get('plannerModel', 'gpt-5'),
            'researcherModel': params.get('researcherModel', 'gpt-5'),
            'engineerModel': params.get('engineerModel', 'gpt-5'),
            'planReviewerModel': params.get('planReviewerModel', 'gpt-5'),
            'defaultModel': params.get('defaultModel', 'gpt-5'),
            'defaultFormatterModel': params.get('defaultFormatterModel', 'gpt-5'),
            'maxRounds': 25,
            'maxAttempts': 6,
            'maxPlanSteps': params.get('maxPlanSteps', 3),
            'nPlanReviews': params.get('nPlanReviews', 1),
            'planInstructions': params.get('planInstructions', 'Use researcher to gather information from specified sources, then use engineer to analyze and write the report.'),
            'agent': 'planner',
            'workDir': params.get('workDir') or '~/cmbagent_workdir'
        }
    }

    return AIWeeklyResponse(
        task_id=task_id,
        status='created',
        message=f'AI Weekly task created successfully. Use task_id {task_id} to connect via WebSocket.'
    )


@router.get("/tasks/{task_id}/config")
async def get_task_config(task_id: str):
    """Get the configuration for a specific task."""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_storage[task_id]
    config = task['config']

    # Debug logging
    logger.debug("task_config_requested", task_id=task_id, mode=config.get('mode'), config_keys=list(config.keys()))

    return {
        'task_id': task_id,
        'description': task['description'],
        'config': config
    }


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status and results of a task.

    For denario-research tasks, includes stage progress information
    from the database when available.
    """
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")

    task = task_storage[task_id]
    task_type = task.get('task_type', TaskType.STANDARD.value)

    response = TaskStatusResponse(
        task_id=task_id,
        status=task.get('status', 'unknown'),
        task_type=task_type,
        mode=task.get('config', {}).get('mode'),
        created_at=task.get('created_at'),
        result=task.get('result'),
        error=task.get('error'),
        updated_at=task.get('updated_at'),
    )

    # For denario tasks, try to enrich with stage data from database
    if task_type == TaskType.DENARIO_RESEARCH.value:
        try:
            from cmbagent.database import get_db_session
            db = get_db_session()
            try:
                from cmbagent.database.repository import TaskStageRepository, CostRepository
                stage_repo = TaskStageRepository(db, session_id=task_id)
                stages = stage_repo.list_stages(parent_run_id=task_id)
                if stages:
                    response.stages = [
                        StageInfo(
                            stage_number=s.stage_number,
                            stage_name=s.stage_name,
                            status=s.status,
                            started_at=s.started_at.isoformat() if s.started_at else None,
                            completed_at=s.completed_at.isoformat() if s.completed_at else None,
                        )
                        for s in stages
                    ]
                    progress = stage_repo.get_task_progress(parent_run_id=task_id)
                    response.current_stage = next(
                        (s.stage_number for s in stages if s.status == "running"), None
                    )
                    response.progress_percent = progress.get("progress_percent", 0.0)

                    cost_repo = CostRepository(db, session_id=task_id)
                    cost_info = cost_repo.get_task_total_cost(parent_run_id=task_id)
                    response.total_cost_usd = cost_info.get("total_cost_usd", 0.0)
            finally:
                db.close()
        except Exception as e:
            # Database not available or no stages yet - return without stage data
            logger.debug("stage_data_unavailable", task_id=task_id, error=str(e))

    return response


@router.get("/{task_id}/stages")
async def list_stages(task_id: str):
    """List all stages for a task workflow.

    Returns stage information from the database for multi-stage (denario) tasks.
    """
    try:
        from cmbagent.database import get_db_session
        db = get_db_session()
        try:
            from cmbagent.database.repository import TaskStageRepository
            stage_repo = TaskStageRepository(db, session_id=task_id)
            stages = stage_repo.list_stages(parent_run_id=task_id)
            return [
                {
                    "stage_number": s.stage_number,
                    "stage_name": s.stage_name,
                    "status": s.status,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "output_files": s.output_files,
                }
                for s in stages
            ]
        finally:
            db.close()
    except Exception as e:
        logger.error("list_stages_failed", task_id=task_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stages: {str(e)}")


@router.get("/{task_id}/stages/{stage_number}")
async def get_stage_detail(task_id: str, stage_number: int):
    """Get detailed information for a specific stage."""
    try:
        from cmbagent.database import get_db_session
        db = get_db_session()
        try:
            from cmbagent.database.repository import TaskStageRepository
            stage_repo = TaskStageRepository(db, session_id=task_id)
            stages = stage_repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_number), None)
            if not stage:
                raise HTTPException(status_code=404, detail=f"Stage {stage_number} not found")
            return {
                "stage_id": stage.id,
                "stage_number": stage.stage_number,
                "stage_name": stage.stage_name,
                "status": stage.status,
                "input_data": stage.input_data,
                "output_data": stage.output_data,
                "output_files": stage.output_files,
                "error_message": stage.error_message,
                "started_at": stage.started_at.isoformat() if stage.started_at else None,
                "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                "child_run_id": stage.child_run_id,
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_stage_detail_failed", task_id=task_id, stage_number=stage_number, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stage detail: {str(e)}")


@router.post("/tasks/{task_id}/result")
async def update_task_result(task_id: str, result: Dict[str, Any]):
    """Update the result for a completed task."""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")

    task_storage[task_id]['result'] = result
    task_storage[task_id]['status'] = 'completed'
    task_storage[task_id]['updated_at'] = datetime.now().isoformat()

    return {'success': True, 'message': 'Task result updated'}
