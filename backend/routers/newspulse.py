"""
Industry News & Sentiment Pulse wizard endpoints.

Provides staged execution of the 4-phase News Pulse workflow:
  Stage 1  Setup & Config        — captures industry, companies, region, model config
  Stage 2  News Discovery        — AI research via DDGS (headlines, raw data collection)
  Stage 3  Deep Analysis         — AI research via DDGS (sentiment, trends, risks)
  Stage 4  Final Report + PDF    — AI compilation into 12-section report + PDF

Each AI stage (2, 3, 4) supports HITL review between stages.
Model configuration follows the Deep Research pattern.
"""

import asyncio
import io
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from models.newspulse_schemas import (
    NewsPulseCreateRequest,
    NewsPulseCreateResponse,
    NewsPulseExecuteRequest,
    NewsPulseStageResponse,
    NewsPulseStageContentResponse,
    NewsPulseContentUpdateRequest,
    NewsPulseRefineRequest,
    NewsPulseRefineResponse,
    NewsPulseTaskStateResponse,
    NewsPulseRecentTaskResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/newspulse", tags=["NewsPulse"])


# Stage definitions — 4 stages (all AI stages, no standalone HITL stage)
STAGE_DEFS = [
    {"number": 1, "name": "setup_config", "shared_key": "user_input_summary", "file": None},
    {"number": 2, "name": "news_discovery", "shared_key": "news_collection", "file": "news_collection.md"},
    {"number": 3, "name": "deep_analysis", "shared_key": "deep_analysis", "file": "deep_analysis.md"},
    {"number": 4, "name": "final_report", "shared_key": "final_report", "file": "final_report.md"},
]


# Track running background tasks
_running_tasks: Dict[str, asyncio.Task] = {}

# Shared console buffers (thread-safe)
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()


# =============================================================================
# Helpers  (mirror deepresearch patterns)
# =============================================================================

_db_initialized = False


def _get_db():
    global _db_initialized
    if not _db_initialized:
        from cmbagent.database.base import init_database
        init_database()
        _db_initialized = True
    from cmbagent.database.base import get_db_session
    return get_db_session()


def _get_stage_repo(db, session_id: str = "newspulse"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_cost_repo(db, session_id: str = "newspulse"):
    from cmbagent.database.repository import CostRepository
    return CostRepository(db, session_id=session_id)


def _get_work_dir(task_id: str, session_id: str = None, base_work_dir: str = None) -> str:
    from core.config import settings
    base = os.path.expanduser(base_work_dir or settings.default_work_dir)
    if session_id:
        return os.path.join(base, "sessions", session_id, "tasks", task_id)
    return os.path.join(base, "newspulse_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run:
        return run.session_id
    return "newspulse"


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "newspulse") -> Dict[str, Any]:
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> NewsPulseStageResponse:
    return NewsPulseStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


class _ConsoleCapture:
    """Thread-safe stdout/stderr capture."""

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
        buf = _console_buffers.get(buf_key, [])
        return buf[since_index:]


def _clear_console_buffer(buf_key: str):
    with _console_lock:
        _console_buffers.pop(buf_key, None)


# =============================================================================
# POST /api/newspulse/create
# =============================================================================

@router.post("/create", response_model=NewsPulseCreateResponse)
async def create_newspulse_task(request: NewsPulseCreateRequest):
    """Create a new News Pulse task with 4 pending stages."""
    task_id = str(uuid.uuid4())

    from services.session_manager import get_session_manager
    from core.config import settings
    sm = get_session_manager()

    base_work_dir = request.work_dir or settings.default_work_dir
    base_work_dir = os.path.expanduser(base_work_dir)

    task_label = f"{request.industry}"
    if request.companies:
        task_label += f" ({request.companies[:40]})"

    session_id = sm.create_session(
        mode="newspulse",
        config={"task_id": task_id, "base_work_dir": base_work_dir},
        name=f"News Pulse: {task_label[:60]}",
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
            mode="newspulse",
            agent="planner",
            model="gpt-4o",
            status="executing",
            task_description=f"News Pulse: {request.industry}",
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "base_work_dir": base_work_dir,
                "industry": request.industry,
                "companies": request.companies or "",
                "region": request.region or "Global",
                "time_window": request.time_window or "7d",
                "config": request.config or {},
                "session_id": session_id,
            },
        )
        db.add(parent_run)
        db.flush()

        # Create 4 pending stages
        repo = _get_stage_repo(db, session_id=session_id)
        stage_responses = []
        for sdef in STAGE_DEFS:
            stage = repo.create_stage(
                parent_run_id=task_id,
                stage_number=sdef["number"],
                stage_name=sdef["name"],
                status="pending",
                input_data={
                    "industry": request.industry,
                    "companies": request.companies,
                    "region": request.region,
                    "time_window": request.time_window,
                },
            )
            stage_responses.append(_stage_to_response(stage))

        db.commit()

        logger.info("newspulse_task_created task_id=%s session_id=%s", task_id, session_id)
        return NewsPulseCreateResponse(
            task_id=task_id,
            work_dir=work_dir,
            stages=stage_responses,
        )
    except Exception as e:
        db.rollback()
        logger.error("newspulse_create_failed error=%s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/newspulse/{task_id}/stages/{num}/execute
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_stage(task_id: str, stage_num: int, request: NewsPulseExecuteRequest = None):
    """Trigger execution of a News Pulse stage."""
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    bg_key = f"np:{task_id}:{stage_num}"
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

        # Allow re-running stages 2 and 3 (HITL loop back)
        if stage.status == "completed" and stage_num not in (2, 3):
            raise HTTPException(status_code=409, detail="Stage is already completed")

        # Check prerequisites
        if stage_num > 1:
            for s in stages:
                if s.stage_number < stage_num and s.status != "completed":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first"
                    )

        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Parent workflow run not found")

        work_dir = parent_run.meta.get("work_dir") if parent_run.meta else _get_work_dir(task_id)
        meta = parent_run.meta or {}

        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)
        # Ensure core fields from meta
        shared_state.setdefault("industry", meta.get("industry", ""))
        shared_state.setdefault("companies", meta.get("companies", ""))
        shared_state.setdefault("region", meta.get("region", "Global"))
        shared_state.setdefault("time_window", meta.get("time_window", "7d"))

        repo.update_stage_status(stage.id, "running")
        config_overrides = (request.config_overrides if request else None) or {}
    finally:
        db.close()

    # Stage 1 completes immediately (no AI)
    if stage_num == 1:
        await _complete_setup_stage(task_id, shared_state)
        return {"status": "completed", "stage_num": stage_num, "task_id": task_id}

    # Stages 2, 3, and 4 run AI in background
    task = asyncio.create_task(
        _run_phase(task_id, stage_num, work_dir, shared_state, config_overrides)
    )
    _running_tasks[bg_key] = task

    return {"status": "executing", "stage_num": stage_num, "task_id": task_id}


async def _complete_setup_stage(task_id: str, shared_state: Dict[str, Any]):
    """Stage 1 completes immediately — stores the user input + config."""
    from cmbagent.task_framework.newspulse_helpers import build_user_input_output

    output_data = build_user_input_output(
        industry=shared_state["industry"],
        companies=shared_state["companies"],
        region=shared_state["region"],
        time_window=shared_state["time_window"],
    )

    db = _get_db()
    try:
        sid = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=sid)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == 1), None)
        if stage:
            repo.update_stage_status(stage.id, "completed", output_data=output_data)
        db.commit()
    finally:
        db.close()


async def _run_phase(
    task_id: str,
    stage_num: int,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Execute News Pulse AI stages (2, 3, or 4) in background."""
    sdef = STAGE_DEFS[stage_num - 1]
    buf_key = f"np:{task_id}:{stage_num}"

    with _console_lock:
        _console_buffers[buf_key] = [f"Starting {sdef['name']}..."]

    try:
        if stage_num == 2:
            await _run_discovery_stage(
                task_id, stage_num, sdef, buf_key,
                work_dir, shared_state, config_overrides,
            )
        elif stage_num == 3:
            await _run_analysis_stage(
                task_id, stage_num, sdef, buf_key,
                work_dir, shared_state, config_overrides,
            )
        elif stage_num == 4:
            await _run_final_report_stage(
                task_id, stage_num, sdef, buf_key,
                work_dir, shared_state, config_overrides,
            )
    except Exception as e:
        logger.error("newspulse_phase_exception task=%s stage=%d error=%s",
                      task_id, stage_num, e, exc_info=True)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"Error: {e}")
        db = _get_db()
        try:
            sid = _get_session_id_for_task(task_id, db)
            repo = _get_stage_repo(db, session_id=sid)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "failed", error_message=str(e))
            db.commit()
        finally:
            db.close()
    finally:
        bg_key = f"np:{task_id}:{stage_num}"
        _running_tasks.pop(bg_key, None)


def _setup_stage_callbacks(db, session_id, task_id, stage_num, sdef):
    """Set up cost + event tracking callbacks for AI stages."""
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

    event_cb = WorkflowCallbacks(
        on_agent_message=on_agent_msg,
        on_cost_update=on_cost_update,
    )
    workflow_callbacks = merge_callbacks(create_print_callbacks(), event_cb)
    return workflow_callbacks, cost_collector


def _run_with_capture(buf_key, func, *args, **kwargs):
    """Run a blocking function with stdout/stderr capture."""
    import asyncio

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    capture_out = _ConsoleCapture(buf_key, original_stdout)
    capture_err = _ConsoleCapture(buf_key, original_stderr)

    try:
        sys.stdout = capture_out
        sys.stderr = capture_err
        return func(*args, **kwargs)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


async def _run_discovery_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stage 2 — News Discovery & Collection via DDGS."""
    from cmbagent.workflows.planning_control import planning_and_control_context_carryover
    from cmbagent.task_framework import newspulse_helpers as helpers

    db = _get_db()
    session_id = _get_session_id_for_task(task_id, db)
    workflow_callbacks, cost_collector = _setup_stage_callbacks(
        db, session_id, task_id, stage_num, sdef
    )

    kwargs = helpers.build_discovery_kwargs(
        industry=shared_state["industry"],
        companies=shared_state["companies"],
        region=shared_state["region"],
        time_window=shared_state["time_window"],
        work_dir=work_dir,
        parent_run_id=task_id,
        config_overrides=config_overrides,
    )
    kwargs["callbacks"] = workflow_callbacks
    task_arg = kwargs.pop("task")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Stage {stage_num} ({sdef['name']}) initialized, searching for news..."
        )

    results = await asyncio.to_thread(
        _run_with_capture, buf_key,
        planning_and_control_context_carryover, task_arg, **kwargs,
    )

    # Extract & save
    news_collection = helpers.extract_stage_result(results)
    file_path = helpers.save_stage_file(news_collection, work_dir, "news_collection.md")
    output_data = helpers.build_discovery_output(
        industry=shared_state["industry"],
        companies=shared_state["companies"],
        region=shared_state["region"],
        time_window=shared_state["time_window"],
        news_collection=news_collection,
        file_path=file_path,
        chat_history=results["chat_history"],
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

    # Persist
    persist_db = _get_db()
    try:
        repo = _get_stage_repo(persist_db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            repo.update_stage_status(
                stage.id, "completed",
                output_data=output_data,
                output_files=[file_path],
            )
            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Stage {stage_num} ({sdef['name']}) completed successfully."
                )
        persist_db.commit()
    finally:
        persist_db.close()


async def _run_analysis_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stage 3 — Deep Sentiment & Analysis via DDGS."""
    from cmbagent.workflows.planning_control import planning_and_control_context_carryover
    from cmbagent.task_framework import newspulse_helpers as helpers

    db = _get_db()
    session_id = _get_session_id_for_task(task_id, db)
    workflow_callbacks, cost_collector = _setup_stage_callbacks(
        db, session_id, task_id, stage_num, sdef
    )

    news_collection = shared_state.get("news_collection", "")

    kwargs = helpers.build_analysis_kwargs(
        industry=shared_state["industry"],
        companies=shared_state["companies"],
        region=shared_state["region"],
        time_window=shared_state["time_window"],
        news_collection=news_collection,
        work_dir=work_dir,
        parent_run_id=task_id,
        config_overrides=config_overrides,
    )
    kwargs["callbacks"] = workflow_callbacks
    task_arg = kwargs.pop("task")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Stage {stage_num} ({sdef['name']}) initialized, performing deep analysis..."
        )

    results = await asyncio.to_thread(
        _run_with_capture, buf_key,
        planning_and_control_context_carryover, task_arg, **kwargs,
    )

    # Extract & save
    deep_analysis = helpers.extract_stage_result(results)
    file_path = helpers.save_stage_file(deep_analysis, work_dir, "deep_analysis.md")
    output_data = helpers.build_analysis_output(
        shared_state=shared_state,
        deep_analysis=deep_analysis,
        file_path=file_path,
        chat_history=results["chat_history"],
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

    persist_db = _get_db()
    try:
        repo = _get_stage_repo(persist_db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            repo.update_stage_status(
                stage.id, "completed",
                output_data=output_data,
                output_files=[file_path],
            )
            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Stage {stage_num} ({sdef['name']}) completed successfully."
                )
        persist_db.commit()
    finally:
        persist_db.close()


async def _run_final_report_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stage 4 — Final Report + PDF via LangGraph pipeline.

    Uses NewsPulseReportPhase which generates each report section
    independently (bounded LLM calls) then assembles markdown + PDF.
    This replaces the old planning_and_control_context_carryover approach
    which blew up to 2.5M+ tokens of context.
    """
    from cmbagent.task_framework.phases.newspulse_report import (
        NewsPulseReportPhase,
        NewsPulseReportPhaseConfig,
    )
    from cmbagent.phases.base import PhaseContext, PhaseStatus

    db = _get_db()
    session_id = _get_session_id_for_task(task_id, db)

    cfg = {**config_overrides}
    phase_config = NewsPulseReportPhaseConfig(
        parent_run_id=task_id,
        llm_model=cfg.pop("researcher_model", "gpt-4o"),
        llm_temperature=float(cfg.pop("llm_temperature", 0.7)),
    )
    phase = NewsPulseReportPhase(phase_config)

    context = PhaseContext(
        workflow_id=f"newspulse-{task_id}",
        run_id=task_id,
        phase_id=f"stage-{stage_num}",
        task=f"Generate final report for {shared_state.get('industry', '')}",
        work_dir=work_dir,
        shared_state=shared_state,
        api_keys={},
        callbacks=None,
    )

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            "Stage 4 (Final Report + PDF) initialized — LangGraph pipeline starting..."
        )

    # Run the LangGraph phase with stdout/stderr capture
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    capture_out = _ConsoleCapture(buf_key, original_stdout)
    capture_err = _ConsoleCapture(buf_key, original_stderr)

    try:
        sys.stdout = capture_out
        sys.stderr = capture_err
        result = await phase.execute(context)
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    try:
        db.close()
    except Exception:
        pass

    # Persist result to DB
    persist_db = _get_db()
    try:
        repo = _get_stage_repo(persist_db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            if result.status == PhaseStatus.COMPLETED:
                output_data = result.context.output_data or {}
                output_files = list((output_data.get("artifacts", {})).values())
                repo.update_stage_status(
                    stage.id, "completed",
                    output_data=output_data,
                    output_files=output_files,
                )
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} ({sdef['name']}) completed successfully."
                    )
                # Report PDF status
                pdf_path = output_data.get("artifacts", {}).get("report.pdf")
                if pdf_path:
                    with _console_lock:
                        _console_buffers.setdefault(buf_key, []).append(
                            f"PDF generated: {os.path.basename(pdf_path)}"
                        )
                else:
                    with _console_lock:
                        _console_buffers.setdefault(buf_key, []).append(
                            "PDF generation skipped (install weasyprint or fpdf2)"
                        )
            else:
                repo.update_stage_status(
                    stage.id, "failed",
                    error_message=result.error or "Report generation failed",
                )
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} failed: {result.error}"
                    )
        persist_db.commit()
    finally:
        persist_db.close()


# =============================================================================
# GET /api/newspulse/{task_id}/stages/{num}/content
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/content", response_model=NewsPulseStageContentResponse)
async def get_stage_content(task_id: str, stage_num: int):
    """Get stage output content."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        content = None
        shared = None
        if stage.output_data:
            shared = stage.output_data.get("shared")
            sdef = STAGE_DEFS[stage_num - 1]
            if sdef["shared_key"] and shared:
                content = shared.get(sdef["shared_key"])

            # Fallback: read from file
            if not content and sdef["file"]:
                from cmbagent.database.models import WorkflowRun
                parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
                file_path = os.path.join(wd, "input_files", sdef["file"])
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        content = f.read()

        raw_files = stage.output_files or []
        sanitized_files = []
        for f in raw_files:
            if f and os.path.isfile(f):
                sanitized_files.append(f)

        return NewsPulseStageContentResponse(
            stage_number=stage.stage_number,
            stage_name=stage.stage_name,
            status=stage.status,
            content=content,
            shared_state=shared,
            output_files=sanitized_files,
        )
    finally:
        db.close()


# =============================================================================
# PUT /api/newspulse/{task_id}/stages/{num}/content
# =============================================================================

@router.put("/{task_id}/stages/{stage_num}/content")
async def update_stage_content(task_id: str, stage_num: int, request: NewsPulseContentUpdateRequest):
    """Save user edits to stage content (HITL)."""
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    sdef = STAGE_DEFS[stage_num - 1]
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        if stage.status not in ("completed", "failed"):
            raise HTTPException(status_code=400, detail="Can only edit completed or recovered stages")

        new_status = "completed" if stage.status == "failed" else stage.status

        output_data = stage.output_data or {}
        shared = output_data.get("shared", {})
        shared[request.field] = request.content
        output_data["shared"] = shared

        repo.update_stage_status(stage.id, new_status, output_data=output_data)

        # Write to disk
        if sdef["file"]:
            from cmbagent.database.models import WorkflowRun
            parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
            file_path = os.path.join(wd, "input_files", sdef["file"])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(request.content)

        db.commit()
        return {"status": "saved", "field": request.field}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/newspulse/{task_id}/stages/{num}/refine
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/refine", response_model=NewsPulseRefineResponse)
async def refine_stage_content(task_id: str, stage_num: int, request: NewsPulseRefineRequest):
    """LLM refine for stage content."""
    import concurrent.futures

    prompt = (
        "You are an expert industry analyst helping refine a news & sentiment report. "
        "Below is the current content, followed by the user's edit request.\n\n"
        f"--- CURRENT CONTENT ---\n{request.content}\n\n"
        f"--- USER REQUEST ---\n{request.message}\n\n"
        "Provide the refined version. Return ONLY the refined content, no explanations."
    )

    try:
        def _call_llm():
            from cmbagent.llm_provider import safe_completion
            return safe_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4o",
                temperature=0.7,
                max_tokens=4096,
            )

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            refined = await loop.run_in_executor(executor, _call_llm)

        return NewsPulseRefineResponse(refined_content=refined)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


# =============================================================================
# GET /api/newspulse/{task_id}/stages/{num}/console
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/console")
async def get_stage_console(task_id: str, stage_num: int, since: int = 0):
    """Get console output lines for a running stage."""
    buf_key = f"np:{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {"lines": lines, "next_index": since + len(lines), "stage_num": stage_num}


# =============================================================================
# GET /api/newspulse/recent
# =============================================================================

@router.get("/recent", response_model=list[NewsPulseRecentTaskResponse])
async def list_recent_tasks():
    """List incomplete News Pulse tasks for resume."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.mode == "newspulse",
                WorkflowRun.parent_run_id.is_(None),
                WorkflowRun.status.in_(["executing", "draft", "planning"]),
            )
            .order_by(WorkflowRun.started_at.desc())
            .limit(20)
            .all()
        )

        result = []
        for run in runs:
            repo = _get_stage_repo(db, session_id=run.session_id)
            progress = repo.get_task_progress(parent_run_id=run.id)
            current_stage = None
            stages = repo.list_stages(parent_run_id=run.id)
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

            result.append(NewsPulseRecentTaskResponse(
                task_id=run.id,
                task=run.task_description or "",
                status=run.status,
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current_stage,
                progress_percent=progress.get("progress_percent", 0.0),
            ))

        return result
    finally:
        db.close()


# =============================================================================
# POST /api/newspulse/{task_id}/stop
# =============================================================================

@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop a running News Pulse task."""
    cancelled = []
    for key in list(_running_tasks):
        if task_id in key:
            bg_task = _running_tasks.get(key)
            if bg_task and not bg_task.done():
                bg_task.cancel()
                cancelled.append(key)

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            if s.status == "running":
                repo.update_stage_status(s.id, "failed", error_message="Stopped by user")

        parent.status = "failed"
        db.commit()
        return {"status": "stopped", "task_id": task_id, "cancelled_stages": cancelled}
    finally:
        db.close()


# =============================================================================
# DELETE /api/newspulse/{task_id}
# =============================================================================

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a News Pulse task."""
    import shutil

    for key in list(_running_tasks):
        if task_id in key:
            bg_task = _running_tasks.pop(key, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()

    for key in list(_console_buffers):
        if task_id in key:
            with _console_lock:
                _console_buffers.pop(key, None)

    db = _get_db()
    work_dir = None
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        work_dir = (parent.meta or {}).get("work_dir")
        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            db.delete(s)
        db.delete(parent)
        db.commit()
    finally:
        db.close()

    if work_dir and os.path.isdir(work_dir):
        try:
            shutil.rmtree(work_dir)
        except Exception as exc:
            logger.warning("newspulse_delete_workdir_failed path=%s error=%s", work_dir, exc)

    return {"status": "deleted", "task_id": task_id}


# =============================================================================
# GET /api/newspulse/{task_id}
# =============================================================================

@router.get("/{task_id}", response_model=NewsPulseTaskStateResponse)
async def get_task_state(task_id: str):
    """Get full task state for resume."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        progress = repo.get_task_progress(parent_run_id=task_id)

        total_cost = None
        try:
            cost_repo = _get_cost_repo(db, session_id=parent.session_id)
            cost_info = cost_repo.get_task_total_cost(parent_run_id=task_id)
            total_cost = cost_info.get("total_cost_usd")
        except Exception:
            pass

        current_stage = None
        for s in stages:
            if s.status == "running":
                current_stage = s.stage_number
                break
        if current_stage is None:
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

        return NewsPulseTaskStateResponse(
            task_id=task_id,
            task=parent.task_description or "",
            status=parent.status,
            work_dir=(parent.meta or {}).get("work_dir"),
            created_at=parent.started_at.isoformat() if parent.started_at else None,
            stages=[_stage_to_response(s) for s in stages],
            current_stage=current_stage,
            progress_percent=progress.get("progress_percent", 0.0),
            total_cost_usd=total_cost,
        )
    finally:
        db.close()
