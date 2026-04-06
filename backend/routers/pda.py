"""
PDA (Product Discovery Assistant) staged router.

Architecture mirrors NewsPulse / DeepResearch:
  • Session + WorkflowRun + TaskStage DB records
  • Background asyncio execution per stage
  • Thread-safe console buffer + WebSocket streaming
  • HITL content save/refine between stages
  • Cost tracking via CostCollector

Stage 0 (client-details) is the only direct-LLM endpoint — no session.
All other stages: POST /api/pda/create → POST /api/pda/{id}/stages/{n}/execute
"""

import asyncio
import io
import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.pda_schemas import (
    PdaCreateRequest,
    PdaCreateResponse,
    PdaExecuteRequest,
    PdaStageResponse,
    PdaStageContentResponse,
    PdaContentUpdateRequest,
    PdaRefineRequest,
    PdaRefineResponse,
    PdaTaskStateResponse,
    PdaRecentTaskResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/pda", tags=["PDA"])

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
STAGE_DEFS = [
    {"number": 1, "name": "research_summary",    "shared_key": "research_summary",    "file": "research_summary.md"},
    {"number": 2, "name": "problem_definition",  "shared_key": "problem_definition",  "file": "problem_definition.md"},
    {"number": 3, "name": "opportunities",       "shared_key": "opportunities",       "file": "opportunities.md"},
    {"number": 4, "name": "solution_archetypes", "shared_key": "solution_archetypes", "file": "solution_archetypes.md"},
    {"number": 5, "name": "features",            "shared_key": "features",            "file": "features.md"},
    {"number": 6, "name": "prompts",             "shared_key": "prompts",             "file": "prompts.md"},
    {"number": 7, "name": "slide_content",       "shared_key": "slide_content",       "file": "slide_content.md"},
]

# In-flight asyncio tasks
_running_tasks: Dict[str, asyncio.Task] = {}

# Thread-safe console buffers
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()

# DB lazy-init flag
_db_initialized = False


# =============================================================================
# Internal helpers (mirrors newspulse.py helpers)
# =============================================================================

def _get_db():
    global _db_initialized
    if not _db_initialized:
        from cmbagent.database.base import init_database
        init_database()
        _db_initialized = True
    from cmbagent.database.base import get_db_session
    return get_db_session()


def _get_stage_repo(db, session_id: str = "pda"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_work_dir(task_id: str, session_id: str = None, base_work_dir: str = None) -> str:
    from core.config import settings
    base = os.path.expanduser(base_work_dir or settings.default_work_dir)
    if session_id:
        return os.path.join(base, "sessions", session_id, "tasks", task_id)
    return os.path.join(base, "pda_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run:
        return run.session_id
    return "pda"


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "pda") -> Dict[str, Any]:
    """Accumulate completed stage outputs into shared_state (mirrors NewsPulse)."""
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> PdaStageResponse:
    return PdaStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


class _ConsoleCapture:
    """Thread-safe stdout/stderr → console buffer (mirrors NewsPulse)."""

    def __init__(self, buf_key: str, original_stream):
        self._buf_key = buf_key
        self._original = original_stream

    def write(self, text: str):
        if self._original:
            self._original.write(text)
        if text and text.strip():
            with _console_lock:
                if self._buf_key not in _console_buffers:
                    _console_buffers[self._buf_key] = []
                _console_buffers[self._buf_key].append(text.rstrip())

    def flush(self):
        if self._original:
            self._original.flush()

    def fileno(self):
        if self._original:
            return self._original.fileno()
        raise io.UnsupportedOperation("fileno")

    def isatty(self):
        return False


def _get_console_lines(buf_key: str, since_index: int = 0) -> List[str]:
    with _console_lock:
        return _console_buffers.get(buf_key, [])[since_index:]


def _clear_console_buffer(buf_key: str):
    with _console_lock:
        _console_buffers.pop(buf_key, None)


# =============================================================================
# Stage 0 — Client Details  (direct LLM, NO session — backward compatible)
# =============================================================================

class _ClientDetailsRequest(BaseModel):
    clientName: str


class _ClientDetailsResponse(BaseModel):
    industry: str
    subIndustry: str
    clientContext: str = ""
    businessFunctions: List[str] = []
    suggestedDiscoveryTypes: List[str] = []
    problemKeywords: str = ""
    suggestedBusinessFunctions: List[str] = []


@router.post("/client-details", response_model=_ClientDetailsResponse)
async def api_client_details(request: _ClientDetailsRequest):
    """Stage 0: Auto-detect client info — direct LLM, no session created."""
    try:
        from services.pda_service import get_client_details
        result = await get_client_details(request.clientName)
        if isinstance(result.get("problemKeywords"), list):
            result["problemKeywords"] = ", ".join(str(x) for x in result["problemKeywords"])
        for list_field in ("businessFunctions", "suggestedDiscoveryTypes", "suggestedBusinessFunctions"):
            if isinstance(result.get(list_field), str):
                result[list_field] = [x.strip() for x in result[list_field].split(",") if x.strip()]
        return _ClientDetailsResponse(**result)
    except Exception as e:
        logger.error("pda_client_details_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"Failed to detect client details: {e}")


# =============================================================================
# GET /api/pda/health
# =============================================================================

@router.get("/health")
async def pda_health():
    try:
        from cmbagent.llm_provider import get_provider_config
        cfg = get_provider_config()
        return {"status": "ok", "provider": cfg.active_provider, "is_azure": cfg.is_azure}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


# =============================================================================
# GET /api/pda/recent
# =============================================================================

@router.get("/recent", response_model=List[PdaRecentTaskResponse])
async def get_recent_pda_tasks(limit: int = 10):
    """Return recent PDA tasks ordered by creation time."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.mode == "pda",
                WorkflowRun.parent_run_id.is_(None),
                WorkflowRun.status.in_(["executing", "draft", "planning", "failed"]),
            )
            .order_by(WorkflowRun.started_at.desc())
            .limit(limit)
            .all()
        )
        result = []
        for run in runs:
            meta = run.meta or {}
            session_id = run.session_id or "pda"
            repo = _get_stage_repo(db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=run.id)
            completed = sum(1 for s in stages if s.status == "completed")
            total = len(stages) or 7
            progress = (completed / total * 100)
            # Current = first non-completed stage (running > failed > pending)
            current = next(
                (s.stage_number for s in stages if s.status == "running"), None
            ) or next(
                (s.stage_number for s in stages if s.status == "failed"), None
            ) or next(
                (s.stage_number for s in stages if s.status == "pending"), None
            )
            result.append(PdaRecentTaskResponse(
                task_id=run.id,
                task=run.task_description or "",
                status=run.status or "",
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current,
                progress_percent=progress,
                client_name=meta.get("client_name"),
                industry=meta.get("industry"),
            ))
        return result
    finally:
        db.close()


# =============================================================================
# POST /api/pda/create
# =============================================================================

@router.post("/create", response_model=PdaCreateResponse)
async def create_pda_task(request: PdaCreateRequest):
    """Create a new PDA task with 7 pending stages + session + DB records."""
    task_id = str(uuid.uuid4())

    from services.session_manager import get_session_manager
    from core.config import settings
    sm = get_session_manager()

    base_work_dir = request.work_dir or settings.default_work_dir
    base_work_dir = os.path.expanduser(base_work_dir)

    task_label = request.client_name or request.industry or "Product Discovery"

    session_id = sm.create_session(
        mode="pda",
        config={"task_id": task_id, "base_work_dir": base_work_dir},
        name=f"PDA: {task_label[:60]}",
    )

    work_dir = _get_work_dir(task_id, session_id=session_id, base_work_dir=base_work_dir)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "input_files"), exist_ok=True)
    os.makedirs(os.path.join(work_dir, "output"), exist_ok=True)

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun

        parent_run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="pda",
            agent="planner",
            model="gpt-4o",
            status="executing",
            task_description=f"PDA: {task_label}",
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "base_work_dir": base_work_dir,
                "client_name": request.client_name,
                "industry": request.industry,
                "sub_industry": request.sub_industry,
                "client_context": request.client_context,
                "business_function": request.business_function,
                "discovery_type": request.discovery_type,
                "process_type": request.process_type,
                "existing_functionality": request.existing_functionality,
                "problem_keywords": request.problem_keywords,
                "expected_output": request.expected_output,
                "research_mode": request.research_mode,
                "config": request.config or {},
                "session_id": session_id,
            },
        )
        db.add(parent_run)
        db.flush()

        repo = _get_stage_repo(db, session_id=session_id)
        stage_responses = []
        for sdef in STAGE_DEFS:
            stage = repo.create_stage(
                parent_run_id=task_id,
                stage_number=sdef["number"],
                stage_name=sdef["name"],
                status="pending",
                input_data={
                    "client_name": request.client_name,
                    "industry": request.industry,
                    "business_function": request.business_function,
                    "discovery_type": request.discovery_type,
                    "problem_keywords": request.problem_keywords,
                },
            )
            stage_responses.append(_stage_to_response(stage))

        db.commit()
        logger.info("pda_task_created task_id=%s session_id=%s", task_id, session_id)
        return PdaCreateResponse(task_id=task_id, work_dir=work_dir, stages=stage_responses)
    except Exception as e:
        db.rollback()
        logger.error("pda_create_failed error=%s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/pda/{task_id}/stages/{stage_num}/execute
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_pda_stage(
    task_id: str,
    stage_num: int,
    request: PdaExecuteRequest = None,
):
    """Trigger background execution of a PDA stage."""
    if stage_num < 1 or stage_num > 7:
        raise HTTPException(status_code=400, detail="stage_num must be 1-7")

    bg_key = f"pda:{task_id}:{stage_num}"
    if bg_key in _running_tasks and not _running_tasks[bg_key].done():
        raise HTTPException(status_code=409, detail="Stage is already executing")

    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        if not stages:
            raise HTTPException(status_code=404, detail="Task not found")

        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        if stage.status == "running":
            if bg_key in _running_tasks and not _running_tasks[bg_key].done():
                raise HTTPException(status_code=409, detail="Stage is already running")

        # Check prerequisites — all stages BEFORE this one must be completed.
        # Completed stages may be re-run (user retries a different result).
        # Failed stages may always be re-run.
        if stage_num > 1:
            for s in stages:
                if s.stage_number < stage_num and s.status != "completed":
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Stage {s.stage_number} ({s.stage_name}) must complete before "
                            f"stage {stage_num} can run. "
                            f"Current status: {s.status}."
                        ),
                    )

        # Reset downstream stages when re-running an already-completed stage
        # so the pipeline is always internally consistent.
        if stage.status == "completed":
            for s in stages:
                if s.stage_number > stage_num and s.status in ("completed", "failed"):
                    repo.update_stage_status(s.id, "pending")
            # Revert parent run status back to executing (was completed)
            from cmbagent.database.models import WorkflowRun as _WR2
            _p = db.query(_WR2).filter(_WR2.id == task_id).first()
            if _p and _p.status == "completed":
                _p.status = "executing"
            db.commit()

        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Parent workflow run not found")

        work_dir = parent_run.meta.get("work_dir") if parent_run.meta else _get_work_dir(task_id)
        meta = parent_run.meta or {}

        # Build shared state from all prior completed stages
        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)

        # Inject intake metadata
        for k in [
            "client_name", "industry", "sub_industry", "client_context",
            "business_function", "discovery_type", "process_type",
            "existing_functionality", "problem_keywords", "expected_output",
            "research_mode",
        ]:
            shared_state.setdefault(k, meta.get(k, ""))

        # Merge user-supplied input_data (e.g. selected_opportunity for stage 4)
        input_data = (request.input_data if request else None) or {}
        shared_state.update(input_data)

        repo.update_stage_status(stage.id, "running")
        config_overrides = (request.config_overrides if request else None) or {}

    finally:
        db.close()

    task = asyncio.create_task(
        _run_pda_stage(task_id, stage_num, work_dir, shared_state, config_overrides)
    )
    _running_tasks[bg_key] = task

    return {"status": "executing", "stage_num": stage_num, "task_id": task_id}


# =============================================================================
# Background execution
# =============================================================================

async def _run_pda_stage(
    task_id: str,
    stage_num: int,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Execute a PDA stage in the background.

    Stage 1 (Research Summary) — uses one_shot OR planning_and_control
    depending on research_mode stored in shared_state.

    Stages 2-7 — use direct LLM calls (structured generation).
    All stages use thead-safe console capture + DB persistence (mirrors NewsPulse).
    """
    sdef = STAGE_DEFS[stage_num - 1]
    buf_key = f"pda:{task_id}:{stage_num}"

    with _console_lock:
        _console_buffers[buf_key] = [f"[PDA] Starting stage {stage_num}: {sdef['name']}..."]

    try:
        if stage_num == 1:
            # Research stage — uses one_shot / planning_and_control via helpers
            await _run_research_stage(
                task_id, stage_num, sdef, buf_key, work_dir, shared_state, config_overrides
            )
        else:
            # Stages 2-7 — direct LLM structured generation via helpers
            await _run_structured_stage(
                task_id, stage_num, sdef, buf_key, work_dir, shared_state, config_overrides
            )

    except Exception as e:
        logger.error(
            "pda_stage_exception task=%s stage=%d error=%s", task_id, stage_num, e, exc_info=True
        )
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"[PDA ERROR] {e}")

        err_db = _get_db()
        try:
            sid = _get_session_id_for_task(task_id, err_db)
            repo = _get_stage_repo(err_db, session_id=sid)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "failed", error_message=str(e))
            err_db.commit()
        finally:
            err_db.close()
    finally:
        _running_tasks.pop(f"pda:{task_id}:{stage_num}", None)


def _setup_stage_callbacks(db, session_id: str, task_id: str, stage_num: int, sdef: dict):
    """Set up cost + event tracking callbacks (mirrors NewsPulse)."""
    from cmbagent.callbacks import merge_callbacks, create_print_callbacks, WorkflowCallbacks

    cost_collector = None
    event_repo = None
    try:
        from backend.execution.cost_collector import CostCollector
        cost_collector = CostCollector(db_session=db, session_id=session_id, run_id=task_id)
    except Exception:
        pass
    try:
        from cmbagent.database.repository import EventRepository
        event_repo = EventRepository(db, session_id)
    except Exception:
        pass

    execution_order = [0]

    def on_agent_msg(agent, role, content, metadata):
        if not event_repo:
            return
        try:
            execution_order[0] += 1
            event_repo.create_event(
                run_id=task_id, event_type="agent_call",
                execution_order=execution_order[0], agent_name=agent,
                status="completed",
                inputs={"role": role, "message": (content or "")[:500]},
                outputs={"full_content": (content or "")[:3000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    def on_cost_update(cost_data):
        if cost_collector:
            try:
                cost_collector.collect_from_callback(cost_data)
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

    event_cb = WorkflowCallbacks(on_agent_message=on_agent_msg, on_cost_update=on_cost_update)
    workflow_callbacks = merge_callbacks(create_print_callbacks(), event_cb)
    return workflow_callbacks, cost_collector


def _run_with_capture(buf_key: str, func, *args, **kwargs):
    """Run a blocking function with stdout/stderr capture (mirrors NewsPulse)."""
    import sys

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _ConsoleCapture(buf_key, original_stdout)
    sys.stderr = _ConsoleCapture(buf_key, original_stderr)
    try:
        return func(*args, **kwargs)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


async def _run_research_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Stage 1 — Market Research.

    Supports two modes (taken from shared_state["research_mode"]):
      one_shot              → cmbagent.one_shot(agent='researcher') + direct LLM fallback
      planning_and_control  → planning_and_control_context_carryover() with researcher
    """
    from cmbagent.task_framework import pda_helpers as helpers
    from cmbagent.utils import get_api_keys_from_env

    research_mode = shared_state.get("research_mode", "one_shot")

    db = _get_db()
    session_id = _get_session_id_for_task(task_id, db)
    workflow_callbacks, cost_collector = _setup_stage_callbacks(
        db, session_id, task_id, stage_num, sdef
    )
    api_keys = get_api_keys_from_env()

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"[PDA] Research mode: {research_mode}"
        )

    if research_mode == "planning_and_control":
        from cmbagent.workflows.planning_control import planning_and_control_context_carryover

        kwargs = helpers.build_research_pc_kwargs(
            shared_state=shared_state,
            work_dir=work_dir,
            api_keys=api_keys,
            parent_run_id=task_id,
            config_overrides=config_overrides,
            callbacks=workflow_callbacks,
        )
        task_arg = kwargs.pop("task")

        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                "[PDA] Running planning_and_control_context_carryover for research..."
            )

        results = await asyncio.to_thread(
            _run_with_capture, buf_key,
            planning_and_control_context_carryover, task_arg, **kwargs,
        )

        result_data = helpers.extract_research_from_pc_results(results, shared_state)

    else:
        # one_shot mode (default)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                "[PDA] Running one_shot researcher for market research..."
            )

        result_data = await asyncio.to_thread(
            _run_with_capture, buf_key,
            helpers.run_research_one_shot,
            shared_state, work_dir, api_keys, workflow_callbacks,
        )

    if cost_collector:
        try:
            cost_collector.collect_from_work_dir(work_dir)
        except Exception:
            pass

    try:
        db.close()
    except Exception:
        pass

    await _persist_stage_result(task_id, stage_num, sdef, buf_key, work_dir, result_data,
                                 session_id)


async def _run_structured_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Stages 2-7 — Direct LLM structured generation via helpers."""
    from cmbagent.task_framework import pda_helpers as helpers

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"[PDA] Stage {stage_num} ({sdef['name']}) — running LLM generation..."
        )

    result_data = await asyncio.to_thread(
        _run_stage_with_capture, buf_key, stage_num, shared_state, work_dir, helpers,
    )

    # Resolve session_id up-front so _persist_stage_result doesn't need an extra DB query
    _db = _get_db()
    try:
        _sid = _get_session_id_for_task(task_id, _db)
    finally:
        _db.close()

    await _persist_stage_result(task_id, stage_num, sdef, buf_key, work_dir, result_data,
                                 session_id=_sid)


async def _persist_stage_result(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    result_data: dict,
    session_id: Optional[str] = None,
):
    """Write stage output to disk and DB."""
    content_str = result_data.get("content_str", "")
    file_path = None
    if sdef["file"] and content_str:
        input_files_dir = os.path.join(work_dir, "input_files")
        os.makedirs(input_files_dir, exist_ok=True)
        file_path = os.path.join(input_files_dir, sdef["file"])
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content_str)

    output_data = {
        "shared": {
            sdef["shared_key"]: result_data.get("structured"),
        }
    }

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"[PDA] Stage {stage_num} ({sdef['name']}) completed successfully."
        )

    persist_db = _get_db()
    try:
        if session_id is None:
            session_id = _get_session_id_for_task(task_id, persist_db)
        repo = _get_stage_repo(persist_db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            repo.update_stage_status(
                stage.id, "completed",
                output_data=output_data,
                output_files=[file_path] if file_path else [],
            )

        # Mark parent WorkflowRun completed when all 7 stages are done
        refreshed = repo.list_stages(parent_run_id=task_id)
        if refreshed and all(s.status == "completed" for s in refreshed):
            from cmbagent.database.models import WorkflowRun as _WR
            run = persist_db.query(_WR).filter(_WR.id == task_id).first()
            if run and run.status != "completed":
                run.status = "completed"
                logger.info("pda_task_completed task_id=%s", task_id)

        persist_db.commit()
    finally:
        persist_db.close()


def _run_stage_with_capture(
    buf_key: str,
    stage_num: int,
    shared_state: dict,
    work_dir: str,
    helpers,
) -> dict:
    """Wrap stage execution with stdout/stderr capture to console buffer."""
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _ConsoleCapture(buf_key, original_stdout)
    sys.stderr = _ConsoleCapture(buf_key, original_stderr)
    try:
        return helpers.run_stage(stage_num, shared_state, work_dir)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


# =============================================================================
# GET /api/pda/{task_id}
# =============================================================================

@router.get("/{task_id}", response_model=PdaTaskStateResponse)
async def get_pda_task(task_id: str):
    """Get full task state including all stages."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage_responses = [_stage_to_response(s) for s in stages]

        completed_count = sum(1 for s in stages if s.status == "completed")
        progress = (completed_count / len(stages) * 100) if stages else 0.0

        current_stage = next(
            (s.stage_number for s in stages if s.status in ("running", "pending")), None
        )

        total_cost = 0.0
        try:
            from cmbagent.database.repository import CostRepository
            cost_repo = CostRepository(db, session_id)
            records = cost_repo.get_records_for_run(task_id)
            total_cost = sum(r.cost_usd for r in records if r.cost_usd)
        except Exception:
            pass

        meta = run.meta or {}
        return PdaTaskStateResponse(
            task_id=task_id,
            task=run.task_description or "",
            status=run.status or "executing",
            work_dir=meta.get("work_dir"),
            created_at=run.started_at.isoformat() if run.started_at else None,
            stages=stage_responses,
            current_stage=current_stage,
            progress_percent=progress,
            total_cost_usd=total_cost if total_cost > 0 else None,
            client_name=meta.get("client_name"),
            industry=meta.get("industry"),
        )
    finally:
        db.close()


# =============================================================================
# GET /api/pda/{task_id}/stages/{stage_num}/content
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/content", response_model=PdaStageContentResponse)
async def get_pda_stage_content(task_id: str, stage_num: int):
    """Fetch the generated content for a completed stage."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        sdef = STAGE_DEFS[stage_num - 1]
        content_str = None

        # Try file first
        if stage.output_data:
            from cmbagent.database.models import WorkflowRun
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            if run and run.meta:
                work_dir = run.meta.get("work_dir", "")
                file_path = os.path.join(work_dir, "input_files", sdef["file"])
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content_str = f.read()

        # Fallback: serialize structured data from DB
        if not content_str and stage.output_data and "shared" in stage.output_data:
            raw = stage.output_data["shared"].get(sdef["shared_key"])
            if raw is not None:
                content_str = json.dumps(raw, indent=2) if not isinstance(raw, str) else raw

        return PdaStageContentResponse(
            stage_number=stage_num,
            stage_name=sdef["name"],
            status=stage.status,
            content=content_str,
            shared_state=stage.output_data.get("shared") if stage.output_data else None,
            output_files=stage.output_files,
        )
    finally:
        db.close()


# =============================================================================
# PUT /api/pda/{task_id}/stages/{stage_num}/content          (HITL save)
# =============================================================================

@router.put("/{task_id}/stages/{stage_num}/content")
async def update_pda_stage_content(
    task_id: str, stage_num: int, request: PdaContentUpdateRequest
):
    """HITL: overwrite stage content in DB and on disk."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        sdef = STAGE_DEFS[stage_num - 1]

        output_data = stage.output_data or {"shared": {}}
        if "shared" not in output_data:
            output_data["shared"] = {}
        output_data["shared"][request.field] = request.content
        repo.update_stage_status(stage.id, stage.status, output_data=output_data)

        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if run and run.meta:
            work_dir = run.meta.get("work_dir", "")
            if work_dir and sdef["file"]:
                file_path = os.path.join(work_dir, "input_files", sdef["file"])
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(request.content)

        db.commit()
        return {"status": "saved", "field": request.field}
    finally:
        db.close()


# =============================================================================
# POST /api/pda/{task_id}/stages/{stage_num}/refine          (HITL AI refine)
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/refine", response_model=PdaRefineResponse)
async def refine_pda_stage_content(
    task_id: str, stage_num: int, request: PdaRefineRequest
):
    """HITL: AI-assisted refinement of stage content."""
    try:
        from cmbagent.llm_provider import safe_completion
        sdef = STAGE_DEFS[stage_num - 1]
        system_prompt = (
            "You are a senior Product Discovery strategist. "
            f"You are refining the '{sdef['name'].replace('_', ' ')}' section of a "
            "product discovery report. "
            "Apply the user's instruction to improve the content. "
            "Return only the improved content — no preamble."
        )
        refined = await asyncio.to_thread(
            safe_completion,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Current content:\n\n{request.content}\n\n"
                        f"Instruction: {request.message}"
                    ),
                },
            ],
        )
        return PdaRefineResponse(refined_content=refined)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refinement failed: {e}")


# =============================================================================
# GET /api/pda/{task_id}/stages/{stage_num}/console          (HTTP polling)
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/console")
async def get_pda_console(task_id: str, stage_num: int, since: int = 0):
    """HTTP polling endpoint for console output lines since `since` index."""
    buf_key = f"pda:{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {"lines": lines, "next_index": since + len(lines)}


# =============================================================================
# POST /api/pda/{task_id}/stop
# =============================================================================

@router.post("/{task_id}/stop")
async def stop_pda_task(task_id: str):
    """Cancel in-flight stage tasks and mark them failed."""
    stopped = []
    for stage_num in range(1, 8):
        bg_key = f"pda:{task_id}:{stage_num}"
        if bg_key in _running_tasks and not _running_tasks[bg_key].done():
            _running_tasks[bg_key].cancel()
            stopped.append(stage_num)

    db = _get_db()
    try:
        sid = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=sid)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            if s.status == "running":
                repo.update_stage_status(s.id, "failed", error_message="Stopped by user")
        db.commit()
    finally:
        db.close()

    return {"status": "stopped", "stages": stopped}


# =============================================================================
# DELETE /api/pda/{task_id}
# =============================================================================

@router.delete("/{task_id}")
async def delete_pda_task(task_id: str):
    """Delete task, all stages, and run record from DB."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            db.delete(s)
        db.delete(run)
        db.commit()
        return {"status": "deleted", "task_id": task_id}
    finally:
        db.close()
