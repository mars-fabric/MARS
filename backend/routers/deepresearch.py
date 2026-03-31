"""
Deepresearch Research Paper wizard endpoints.

Provides staged execution of the 4-phase Deepresearch workflow
(idea → method → experiment → paper) where each stage is triggered
individually by the user after review/edit.
"""

import asyncio
import io
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from models.deepresearch_schemas import (
    DeepresearchCreateRequest,
    DeepresearchCreateResponse,
    DeepresearchExecuteRequest,
    DeepresearchStageResponse,
    DeepresearchStageContentResponse,
    DeepresearchContentUpdateRequest,
    DeepresearchRefineRequest,
    DeepresearchRefineResponse,
    DeepresearchTaskStateResponse,
    DeepresearchRecentTaskResponse,
    AnalyzeFilesResponse,
    RefineContextRequest,
    RefineContextResponse,
    UpdateDescriptionRequest,
    AiEditTexRequest,
    AiEditTexResponse,
    CompileTexRequest,
    CompileTexResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/deepresearch", tags=["Deepresearch"])


# Stage definitions
STAGE_DEFS = [
    {"number": 1, "name": "idea_generation", "shared_key": "research_idea", "file": "idea.md"},
    {"number": 2, "name": "method_development", "shared_key": "methodology", "file": "methods.md"},
    {"number": 3, "name": "experiment_execution", "shared_key": "results", "file": "results.md"},
    {"number": 4, "name": "paper_generation", "shared_key": None, "file": None},
]


# Track running background tasks
_running_tasks: Dict[str, asyncio.Task] = {}

# Track running file-analysis background tasks
_running_analyses: Dict[str, asyncio.Task] = {}

# Shared console buffers for stage execution (thread-safe)
# Key: "task_id:stage_num", Value: list of output lines
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()


# =============================================================================
# Helpers
# =============================================================================

_db_initialized = False

def _get_db():
    """Get a database session, ensuring schema is up to date."""
    global _db_initialized
    if not _db_initialized:
        from cmbagent.database.base import init_database
        init_database()
        _db_initialized = True
    from cmbagent.database.base import get_db_session
    return get_db_session()


def _get_stage_repo(db, session_id: str = "deepresearch"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_cost_repo(db, session_id: str = "deepresearch"):
    from cmbagent.database.repository import CostRepository
    return CostRepository(db, session_id=session_id)


def _get_work_dir(task_id: str, session_id: str = None, base_work_dir: str = None) -> str:
    """Get the work directory for a deepresearch task.

    Uses session-based structure: {base}/sessions/{session_id}/tasks/{task_id}
    matching the structure used by all other task modes.
    Falls back to legacy deepresearch_tasks/{task_id} when session_id is absent.
    """
    from core.config import settings
    base = os.path.expanduser(base_work_dir or settings.default_work_dir)
    if session_id:
        return os.path.join(base, "sessions", session_id, "tasks", task_id)
    # Legacy fallback for old tasks without a session
    return os.path.join(base, "deepresearch_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    """Look up the session_id for a deepresearch task from its WorkflowRun."""
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run:
        return run.session_id
    return "deepresearch"  # fallback for legacy tasks


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "deepresearch") -> Dict[str, Any]:
    """Reconstruct shared_state from completed stages' output_data['shared'].

    This accumulates context (research_idea, methodology, results, etc.)
    from all completed stages prior to the one being executed.
    """
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> DeepresearchStageResponse:
    return DeepresearchStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


# Auto-generated files in input_files/ that should NOT be listed as "uploaded data"
_AUTO_GENERATED_FILES = {
    "data_description.md", "idea.md", "methods.md", "results.md", "data_context.md",
}
_AUTO_GENERATED_DIRS = {"plots", "paper"}


def _build_file_context(work_dir: str) -> str:
    """Scan input_files/ for user-uploaded data files and build context string.

    If data_context.md exists (written by the analyze-files endpoint), it is
    included first as the authoritative 'Research Data Foundation'. Individual
    file paths + raw previews follow so agents can reference exact paths.
    """
    input_dir = os.path.join(work_dir, "input_files")
    if not os.path.isdir(input_dir):
        return ""

    sections = []

    # ── Primary: AI-generated data context (if analysis has been run) ──
    data_context_path = os.path.join(input_dir, "data_context.md")
    if os.path.isfile(data_context_path):
        try:
            with open(data_context_path, 'r', encoding='utf-8', errors='replace') as f:
                ctx = f.read().strip()
            if ctx:
                sections.append("\n\n---\n## Research Data Foundation\n\n" + ctx)
        except Exception:
            pass

    # ── Secondary: Individual file paths + raw previews ──
    uploaded_files = []
    for entry in os.listdir(input_dir):
        if entry in _AUTO_GENERATED_FILES:
            continue
        if entry in _AUTO_GENERATED_DIRS:
            continue
        full_path = os.path.join(input_dir, entry)
        if not os.path.isfile(full_path):
            continue
        uploaded_files.append((entry, full_path))

    if not uploaded_files:
        return "\n".join(sections) if sections else ""

    lines = ["\n\n---\n## Uploaded Data Files\n"]
    lines.append("The following data files have been uploaded and are available at the paths below.\n")

    for name, path in sorted(uploaded_files):
        size = os.path.getsize(path)
        size_str = f"{size}" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
        lines.append(f"### `{name}` ({size_str})")
        lines.append(f"**Absolute path:** `{path}`\n")

        # For text-readable files, include a preview
        text_exts = {'.csv', '.txt', '.md', '.json', '.tsv', '.dat'}
        ext = os.path.splitext(name)[1].lower()
        if ext in text_exts and size < 10 * 1024 * 1024:  # Skip previews for files >10MB
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    preview_lines = []
                    for i, line in enumerate(f):
                        if i >= 15:
                            preview_lines.append("... (truncated)")
                            break
                        preview_lines.append(line.rstrip())
                if preview_lines:
                    lines.append("**Preview (first 15 lines):**")
                    lines.append("```")
                    lines.extend(preview_lines)
                    lines.append("```\n")
            except Exception:
                pass

    lines.append("Use the absolute paths above to read these files in your code.\n")
    sections.append("\n".join(lines))
    return "\n".join(sections)


class _ConsoleCapture:
    """Thread-safe stdout/stderr capture that stores output in a shared buffer."""

    def __init__(self, buf_key: str, original_stream):
        self._buf_key = buf_key
        self._original = original_stream

    def write(self, text: str):
        # Always write to original stream too
        if self._original:
            self._original.write(text)
        # Store in shared buffer (line by line)
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
    """Get console output lines since a given index."""
    with _console_lock:
        buf = _console_buffers.get(buf_key, [])
        return buf[since_index:]


def _clear_console_buffer(buf_key: str):
    """Remove a console buffer once done."""
    with _console_lock:
        _console_buffers.pop(buf_key, None)


# =============================================================================
# POST /api/deepresearch/create
# =============================================================================

@router.post("/create", response_model=DeepresearchCreateResponse)
async def create_deepresearch_task(request: DeepresearchCreateRequest):
    """Create a new Deepresearch research task with 4 pending stages."""
    task_id = str(uuid.uuid4())

    # Create a proper session via SessionManager (matches AI-Weekly, etc.)
    from services.session_manager import get_session_manager
    from core.config import settings
    sm = get_session_manager()

    # Resolve base work directory from request (frontend config) or backend setting
    base_work_dir = request.work_dir or settings.default_work_dir
    base_work_dir = os.path.expanduser(base_work_dir)

    # Create session first so we have the session_id for path construction
    session_id = sm.create_session(
        mode="deepresearch-research",
        config={"task_id": task_id, "base_work_dir": base_work_dir},
        name=f"Deepresearch: {request.task[:60]}",
    )

    # Session-based work dir: {base}/sessions/{session_id}/tasks/{task_id}
    # This matches the structure used by all other task modes
    work_dir = _get_work_dir(task_id, session_id=session_id, base_work_dir=base_work_dir)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "input_files"), exist_ok=True)
    # Create standard subdirectories agents expect
    for subdir in ("data", "codebase", "chats", "planning", "control"):
        os.makedirs(os.path.join(work_dir, subdir), exist_ok=True)

    db = _get_db()
    try:
        # Create parent WorkflowRun
        from cmbagent.database.models import WorkflowRun

        parent_run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="deepresearch-research",
            agent="planner",
            model="gpt-4o",
            status="executing",
            task_description=request.task,
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "base_work_dir": base_work_dir,
                "data_description": request.data_description or "",
                "config": request.config or {},
                "session_id": session_id,
            },
        )
        db.add(parent_run)
        db.flush()

        # Create 4 pending TaskStage records
        repo = _get_stage_repo(db, session_id=session_id)
        stage_responses = []
        for sdef in STAGE_DEFS:
            stage = repo.create_stage(
                parent_run_id=task_id,
                stage_number=sdef["number"],
                stage_name=sdef["name"],
                status="pending",
                input_data={"task": request.task, "data_description": request.data_description},
            )
            stage_responses.append(_stage_to_response(stage))

        db.commit()

        # Write data description to input_files/
        if request.data_description:
            desc_path = os.path.join(work_dir, "input_files", "data_description.md")
            with open(desc_path, "w") as f:
                f.write(request.data_description)

        logger.info("deepresearch_task_created task_id=%s session_id=%s", task_id, session_id)
        return DeepresearchCreateResponse(
            task_id=task_id,
            work_dir=work_dir,
            stages=stage_responses,
        )
    except Exception as e:
        db.rollback()
        logger.error("deepresearch_create_failed error=%s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# =============================================================================
# POST /api/deepresearch/{task_id}/stages/{num}/execute
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_stage(task_id: str, stage_num: int, request: DeepresearchExecuteRequest = None):
    """Trigger execution of a single Deepresearch phase.

    Runs the phase asynchronously in the background. Connect to
    the WebSocket /ws/deepresearch/{task_id}/{stage_num} for streaming output.
    """
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(status_code=400, detail="stage_num must be 1-4")

    # Check not already running
    bg_key = f"{task_id}:{stage_num}"
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
            # Check if the background task is actually alive
            if bg_key in _running_tasks and not _running_tasks[bg_key].done():
                raise HTTPException(status_code=409, detail="Stage is already running")
            # Otherwise it's a stale "running" from a previous server session -- allow retry

        if stage.status == "completed":
            raise HTTPException(status_code=409, detail="Stage is already completed")

        # Validate prerequisites: all previous stages must be completed
        for s in stages:
            if s.stage_number < stage_num and s.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first"
                )

        # Get parent run metadata
        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Parent workflow run not found")

        work_dir = parent_run.meta.get("work_dir") if parent_run.meta else _get_work_dir(task_id)
        task_description = parent_run.task_description or ""
        data_description = (parent_run.meta or {}).get("data_description") or ""

        # Enhance data_description with uploaded file context
        file_context = _build_file_context(work_dir)
        if file_context:
            data_description = data_description + file_context

        # Build shared state from completed stages
        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)
        shared_state.setdefault("data_description", data_description)

        # Mark stage as running
        repo.update_stage_status(stage.id, "running")

        config_overrides = (request.config_overrides if request else None) or {}
    finally:
        db.close()

    # Launch background execution
    task = asyncio.create_task(
        _run_phase(task_id, stage_num, task_description, work_dir, shared_state, config_overrides)
    )
    _running_tasks[bg_key] = task

    return {"status": "executing", "stage_num": stage_num, "task_id": task_id}


async def _run_phase(
    task_id: str,
    stage_num: int,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Execute a Deepresearch phase in the background.

    Stages 1-3 call planning_and_control_context_carryover() directly
    with full callbacks (cost tracking, event logging, structured print).
    Stage 4 uses DeepresearchPaperPhase (LangGraph).
    """
    sdef = STAGE_DEFS[stage_num - 1]
    buf_key = f"{task_id}:{stage_num}"

    # Initialize console buffer
    with _console_lock:
        _console_buffers[buf_key] = [f"Starting {sdef['name']}..."]

    try:
        if stage_num <= 3:
            await _run_planning_control_stage(
                task_id, stage_num, sdef, buf_key,
                task_description, work_dir, shared_state, config_overrides,
            )
        else:
            await _run_paper_stage(
                task_id, stage_num, sdef, buf_key,
                task_description, work_dir, shared_state, config_overrides,
            )
    except Exception as e:
        logger.error("deepresearch_phase_exception task=%s stage=%d error=%s", task_id, stage_num, e, exc_info=True)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                f"Error: {e}"
            )
        # Mark stage as failed
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
        bg_key = f"{task_id}:{stage_num}"
        _running_tasks.pop(bg_key, None)
        # Don't clear buffer here - WS endpoint needs to read remaining lines
        # Buffer is cleared after WS sends final event or after a timeout


async def _run_planning_control_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stages 1-3 by calling planning_and_control_context_carryover directly.

    Sets up full callback infrastructure (CostCollector, ExecutionEvent logging,
    structured print callbacks) before calling the function, matching the
    observability of the standard task execution flow in task_executor.py.
    """
    from cmbagent.workflows.planning_control import planning_and_control_context_carryover
    from cmbagent.callbacks import merge_callbacks, create_print_callbacks, WorkflowCallbacks
    from cmbagent.task_framework import stage_helpers

    # ── 1. Set up DB session for cost + event tracking ──
    db = _get_db()
    session_id = _get_session_id_for_task(task_id, db)

    cost_collector = None
    event_repo = None
    try:
        from backend.execution.cost_collector import CostCollector
        cost_collector = CostCollector(
            db_session=db,
            session_id=session_id,
            run_id=task_id,
        )
    except Exception as exc:
        logger.warning("deepresearch_cost_collector_init_failed error=%s", exc)

    try:
        from cmbagent.database.repository import EventRepository
        event_repo = EventRepository(db, session_id)
    except Exception as exc:
        logger.warning("deepresearch_event_repo_init_failed error=%s", exc)

    # ── 2. Build event tracking callbacks ──
    execution_order = [0]  # mutable counter for ordering

    def on_agent_msg(agent, role, content, metadata):
        if not event_repo:
            return
        try:
            execution_order[0] += 1
            event_repo.create_event(
                run_id=task_id,
                event_type="agent_call",
                execution_order=execution_order[0],
                agent_name=agent,
                status="completed",
                inputs={"role": role, "message": (content or "")[:500]},
                outputs={"full_content": (content or "")[:3000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception as exc:
            logger.debug("deepresearch_event_create_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_code_exec(agent, code, language, result):
        if not event_repo:
            return
        try:
            execution_order[0] += 1
            event_repo.create_event(
                run_id=task_id,
                event_type="code_exec",
                execution_order=execution_order[0],
                agent_name=agent,
                status="completed",
                inputs={"language": language, "code": (code or "")[:2000]},
                outputs={"result": (str(result) if result else "")[:2000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception as exc:
            logger.debug("deepresearch_code_event_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_tool(agent, tool_name, arguments, result):
        if not event_repo:
            return
        try:
            import json as _json
            execution_order[0] += 1
            args_str = _json.dumps(arguments, default=str)[:500] if isinstance(arguments, dict) else str(arguments)[:500]
            event_repo.create_event(
                run_id=task_id,
                event_type="tool_call",
                execution_order=execution_order[0],
                agent_name=agent,
                status="completed",
                inputs={"tool": tool_name, "args": args_str},
                outputs={"result": (str(result) if result else "")[:2000]},
                meta={"stage_num": stage_num, "stage_name": sdef["name"]},
            )
        except Exception as exc:
            logger.debug("deepresearch_tool_event_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_cost_update(cost_data):
        if cost_collector:
            try:
                cost_collector.collect_from_callback(cost_data)
            except Exception as exc:
                logger.debug("deepresearch_cost_callback_failed error=%s", exc)
                try:
                    db.rollback()
                except Exception:
                    pass

    event_tracking_callbacks = WorkflowCallbacks(
        on_agent_message=on_agent_msg,
        on_code_execution=on_code_exec,
        on_tool_call=on_tool,
        on_cost_update=on_cost_update,
    )

    workflow_callbacks = merge_callbacks(
        create_print_callbacks(),
        event_tracking_callbacks,
    )

    # ── 3. Build stage-specific kwargs ──
    data_description = shared_state.get("data_description") or task_description

    if stage_num == 1:
        kwargs = stage_helpers.build_idea_kwargs(
            data_description=data_description,
            work_dir=work_dir,
            parent_run_id=task_id,
            config_overrides=config_overrides,
        )
    elif stage_num == 2:
        kwargs = stage_helpers.build_method_kwargs(
            data_description=data_description,
            research_idea=shared_state["research_idea"],
            work_dir=work_dir,
            parent_run_id=task_id,
            config_overrides=config_overrides,
        )
    elif stage_num == 3:
        kwargs = stage_helpers.build_experiment_kwargs(
            data_description=data_description,
            research_idea=shared_state["research_idea"],
            methodology=shared_state["methodology"],
            work_dir=work_dir,
            parent_run_id=task_id,
            config_overrides=config_overrides,
        )

    # Inject callbacks
    kwargs["callbacks"] = workflow_callbacks

    # Extract task arg (planning_and_control takes it as first positional arg)
    task_arg = kwargs.pop("task")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Stage {stage_num} ({sdef['name']}) initialized, executing..."
        )

    # ── 4. Run with stdout/stderr capture ──
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    capture_out = _ConsoleCapture(buf_key, original_stdout)
    capture_err = _ConsoleCapture(buf_key, original_stderr)

    try:
        sys.stdout = capture_out
        sys.stderr = capture_err
        results = await asyncio.to_thread(
            planning_and_control_context_carryover,
            task_arg,
            **kwargs,
        )
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    # ── 5. Extract results + save files ──
    if stage_num == 1:
        research_idea = stage_helpers.extract_idea_result(results)
        idea_path = stage_helpers.save_idea(research_idea, work_dir)
        output_data = stage_helpers.build_idea_output(
            research_idea, data_description, idea_path, results["chat_history"],
        )
    elif stage_num == 2:
        methodology = stage_helpers.extract_method_result(results)
        methods_path = stage_helpers.save_method(methodology, work_dir)
        output_data = stage_helpers.build_method_output(
            shared_state["research_idea"], data_description,
            methodology, methods_path, results["chat_history"],
        )
    elif stage_num == 3:
        experiment_results, plot_paths = stage_helpers.extract_experiment_result(results)
        results_path, plots_dir, final_plot_paths = stage_helpers.save_experiment(
            experiment_results, plot_paths, work_dir,
        )
        output_data = stage_helpers.build_experiment_output(
            shared_state["research_idea"], data_description,
            shared_state["methodology"], experiment_results,
            final_plot_paths, results_path, plots_dir, results["chat_history"],
        )

    # ── 6. Safety net: scan work_dir for cost files written to disk ──
    if cost_collector:
        try:
            cost_collector.collect_from_work_dir(work_dir)
        except Exception as exc:
            logger.debug("deepresearch_cost_work_dir_failed error=%s", exc)

    # Close the callback DB session — it may be in a bad state after
    # long-running callbacks.  Use a fresh session for the persist step.
    try:
        db.close()
    except Exception:
        pass

    # ── 7. Persist to DB (fresh session) ──
    persist_db = _get_db()
    try:
        repo = _get_stage_repo(persist_db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            repo.update_stage_status(
                stage.id,
                "completed",
                output_data=output_data,
                output_files=list(output_data.get("artifacts", {}).values()),
            )
            logger.info("deepresearch_stage_completed task=%s stage=%d", task_id, stage_num)
            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Stage {stage_num} ({sdef['name']}) completed successfully."
                )
        persist_db.commit()
    finally:
        persist_db.close()


async def _run_paper_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    task_description: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
):
    """Run stage 4 (paper generation) using DeepresearchPaperPhase (LangGraph)."""
    from cmbagent.task_framework.phases.paper import DeepresearchPaperPhase, DeepresearchPaperPhaseConfig
    from cmbagent.phases.base import PhaseContext, PhaseStatus

    config_kwargs = {"parent_run_id": task_id, **config_overrides}
    phase = DeepresearchPaperPhase(DeepresearchPaperPhaseConfig(**config_kwargs))

    context = PhaseContext(
        workflow_id=f"deepresearch-{task_id}",
        run_id=task_id,
        phase_id=f"stage-{stage_num}",
        task=task_description,
        work_dir=work_dir,
        shared_state=shared_state,
        api_keys={},
        callbacks=None,
    )

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Paper generation initialized, executing..."
        )

    # Run the phase with stdout/stderr capture
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

    # Persist result to DB
    db = _get_db()
    try:
        sid = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=sid)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            if result.status == PhaseStatus.COMPLETED:
                repo.update_stage_status(
                    stage.id,
                    "completed",
                    output_data=result.context.output_data,
                    output_files=list((result.context.output_data or {}).get("artifacts", {}).values()),
                )
                logger.info("deepresearch_stage_completed task=%s stage=%d", task_id, stage_num)
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} ({sdef['name']}) completed successfully."
                    )
            else:
                repo.update_stage_status(
                    stage.id,
                    "failed",
                    error_message=result.error or "Phase failed",
                )
                logger.error("deepresearch_stage_failed task=%s stage=%d error=%s", task_id, stage_num, result.error)
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} failed: {result.error}"
                    )
        db.commit()
    finally:
        db.close()


# =============================================================================
# GET /api/deepresearch/{task_id}/stages/{num}/content
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/content", response_model=DeepresearchStageContentResponse)
async def get_stage_content(task_id: str, stage_num: int):
    """Get the output content and shared_state for a completed stage."""
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
            # Try to get main content from the shared_state key
            sdef = STAGE_DEFS[stage_num - 1]
            if sdef["shared_key"] and shared:
                content = shared.get(sdef["shared_key"])

            # Fallback 1: read from the .md file on disk
            if not content and sdef["file"]:
                from cmbagent.database.models import WorkflowRun
                parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
                file_path = os.path.join(work_dir, "input_files", sdef["file"])
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        content = f.read()

            # Fallback 2: re-extract from chat_history stored in output_data
            if not content and stage.output_data.get("chat_history"):
                try:
                    from cmbagent.task_framework import stage_helpers
                    if stage_num == 1:
                        content = stage_helpers.extract_idea_result(
                            {"chat_history": stage.output_data["chat_history"]}
                        )
                        # Repair: persist the recovered content back to DB and disk
                        if content and shared is not None and sdef["shared_key"]:
                            shared[sdef["shared_key"]] = content
                            stage.output_data["shared"] = shared
                            from cmbagent.database.repository import TaskStageRepository
                            repo.update_stage_status(
                                stage.id, "completed", output_data=stage.output_data
                            )
                            db.commit()
                            logger.info("deepresearch_content_recovered task=%s stage=%d len=%d",
                                        task_id, stage_num, len(content))
                except Exception as exc:
                    logger.warning("deepresearch_content_recovery_failed task=%s stage=%d error=%s",
                                   task_id, stage_num, exc)

        # Sanitize output_files: expand any directory entries to their actual files
        # (handles old tasks whose artifacts dict included 'paper/': <dir>)
        raw_files = stage.output_files or []
        sanitized_files = []
        for f in raw_files:
            if f and os.path.isfile(f):
                sanitized_files.append(f)
            elif f and os.path.isdir(f):
                # Expand directory: include .tex and .pdf files
                for fname in sorted(os.listdir(f)):
                    if fname.endswith(('.tex', '.pdf')):
                        sanitized_files.append(os.path.join(f, fname))

        return DeepresearchStageContentResponse(
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
# PUT /api/deepresearch/{task_id}/stages/{num}/content
# =============================================================================

@router.put("/{task_id}/stages/{stage_num}/content")
async def update_stage_content(task_id: str, stage_num: int, request: DeepresearchContentUpdateRequest):
    """Save user edits to a stage's content.

    Updates both the markdown file on disk and the output_data['shared']
    in the database so the next stage reads the edited version.
    """
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

        # If stage was failed but has recovered content, mark it as completed
        new_status = "completed" if stage.status == "failed" else stage.status

        # Update output_data['shared'][field]
        output_data = stage.output_data or {}
        shared = output_data.get("shared", {})
        shared[request.field] = request.content
        output_data["shared"] = shared

        repo.update_stage_status(stage.id, new_status, output_data=output_data)

        # Also update the .md file on disk
        if sdef["file"]:
            from cmbagent.database.models import WorkflowRun
            parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            work_dir = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
            file_path = os.path.join(work_dir, "input_files", sdef["file"])
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
# POST /api/deepresearch/{task_id}/stages/{num}/refine
# =============================================================================

@router.post("/{task_id}/stages/{stage_num}/refine", response_model=DeepresearchRefineResponse)
async def refine_stage_content(task_id: str, stage_num: int, request: DeepresearchRefineRequest):
    """Use LLM to refine stage content based on user instruction.

    This is a single LLM call (not a full phase execution).
    Returns the refined content for the user to review and apply.
    """
    import asyncio
    import concurrent.futures

    prompt = (
        "You are helping a researcher refine their work. "
        "Below is their current content, followed by their edit request.\n\n"
        f"--- CURRENT CONTENT ---\n{request.content}\n\n"
        f"--- USER REQUEST ---\n{request.message}\n\n"
        "Please provide the refined version of the content. "
        "Return ONLY the refined content, no explanations or preamble."
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

        return DeepresearchRefineResponse(
            refined_content=refined,
            message="Content refined successfully",
        )
    except Exception as e:
        logger.error("deepresearch_refine_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


# =============================================================================
# File Analysis  (POST analyze-files, GET console, PUT context, POST refine, PATCH description)
# =============================================================================

@router.post("/{task_id}/analyze-files", response_model=AnalyzeFilesResponse)
async def analyze_files(task_id: str):
    """Analyze uploaded files using LLM — runs in background.

    Extracts metadata for CSV/TSV, JSON, TXT, FITS, HDF5, NPY/NPZ, PDF files,
    then calls gpt-4o to produce a structured Research Data Context document
    saved to input_files/data_context.md.

    Poll GET /{task_id}/analyze-files/console for streaming progress.
    """
    if task_id in _running_analyses and not _running_analyses[task_id].done():
        raise HTTPException(status_code=409, detail="Analysis already running")

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (parent_run.meta or {}).get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    buf_key = f"{task_id}:analyze"
    with _console_lock:
        _console_buffers[buf_key] = ["Starting file analysis..."]

    task_obj = asyncio.create_task(_run_file_analysis(task_id, work_dir, buf_key))
    _running_analyses[task_id] = task_obj
    return AnalyzeFilesResponse()


@router.get("/{task_id}/analyze-files/console")
async def get_analyze_console(task_id: str, since: int = 0):
    """Poll analysis progress. Returns is_done=True and context_text when complete."""
    buf_key = f"{task_id}:analyze"
    lines = _get_console_lines(buf_key, since_index=since)

    with _console_lock:
        full_buf = list(_console_buffers.get(buf_key, []))
    has_done = "__ANALYZE_DONE__" in full_buf
    has_error = "__ANALYZE_ERROR__" in full_buf
    is_done = has_done or has_error

    # Filter sentinels from displayed lines
    lines = [l for l in lines if l not in ("__ANALYZE_DONE__", "__ANALYZE_ERROR__")]

    context_text = None
    if has_done:
        db = _get_db()
        try:
            from cmbagent.database.models import WorkflowRun
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            work_dir = (run.meta or {}).get("work_dir") if run and run.meta else _get_work_dir(task_id)
        finally:
            db.close()
        ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
        if os.path.isfile(ctx_path):
            try:
                with open(ctx_path, 'r', encoding='utf-8') as f:
                    context_text = f.read()
            except Exception:
                pass

    return {
        "lines": lines,
        "next_index": since + len(lines),
        "is_done": is_done,
        "has_error": has_error,
        "context_text": context_text,
    }


@router.put("/{task_id}/context")
async def save_file_context(task_id: str, request: RefineContextRequest):
    """Save an edited data context directly to data_context.md (no LLM involved)."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (run.meta or {}).get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
    try:
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "saved"}


@router.post("/{task_id}/refine-context", response_model=RefineContextResponse)
async def refine_file_context(task_id: str, request: RefineContextRequest):
    """Use LLM to refine the data context according to user instruction, then save."""
    import concurrent.futures

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")
        work_dir = (run.meta or {}).get("work_dir") or _get_work_dir(task_id)
    finally:
        db.close()

    prompt = (
        "You are helping a researcher refine their research data context document.\n"
        "Below is their current data context, followed by their refinement request.\n\n"
        f"--- CURRENT DATA CONTEXT ---\n{request.content}\n\n"
        f"--- USER REQUEST ---\n{request.message}\n\n"
        "Update the data context according to the request. Keep the structured markdown format. "
        "Return ONLY the updated document, no preamble or explanation."
    )

    try:
        def _call():
            from cmbagent.llm_provider import safe_completion
            return safe_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4o",
                temperature=0.4,
                max_tokens=4096,
            )

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            refined = await loop.run_in_executor(executor, _call)

        ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(refined)

        return RefineContextResponse(refined_content=refined)
    except Exception as e:
        logger.error("deepresearch_refine_context_failed error=%s", e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")


@router.patch("/{task_id}/description")
async def update_task_description(task_id: str, request: UpdateDescriptionRequest):
    """Update task description and/or data description — used when task is pre-created."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")
        if request.task is not None:
            run.task_description = request.task
        if request.data_description is not None:
            meta = dict(run.meta or {})
            meta["data_description"] = request.data_description
            run.meta = meta
            work_dir = meta.get("work_dir") or _get_work_dir(task_id)
            desc_path = os.path.join(work_dir, "input_files", "data_description.md")
            os.makedirs(os.path.dirname(desc_path), exist_ok=True)
            with open(desc_path, 'w', encoding='utf-8') as f:
                f.write(request.data_description)
        db.commit()
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


async def _run_file_analysis(task_id: str, work_dir: str, buf_key: str):
    """Background: inspect each uploaded file, build LLM prompt, write data_context.md."""
    import concurrent.futures

    def _do_analysis():
        input_dir = os.path.join(work_dir, "input_files")
        if not os.path.isdir(input_dir):
            return "No input_files directory found."

        file_infos = []
        for entry in sorted(os.listdir(input_dir)):
            if entry in _AUTO_GENERATED_FILES or entry in _AUTO_GENERATED_DIRS:
                continue
            full_path = os.path.join(input_dir, entry)
            if not os.path.isfile(full_path):
                continue
            file_infos.append((entry, full_path))

        if not file_infos:
            return "No user-uploaded data files found to analyze."

        with _console_lock:
            _console_buffers[buf_key].append(
                f"Found {len(file_infos)} file(s). Extracting metadata..."
            )

        summaries = []
        for name, path in file_infos:
            with _console_lock:
                _console_buffers[buf_key].append(f"  \u2192 Inspecting: {name}")

            size = os.path.getsize(path)
            size_str = (
                f"{size}B" if size < 1024
                else f"{size/1024:.1f}KB" if size < 1024 * 1024
                else f"{size/1024/1024:.1f}MB"
            )
            ext = os.path.splitext(name)[1].lower()
            info = [f"### File: `{name}` ({size_str})", f"**Path:** `{path}`"]

            try:
                if ext in ('.csv', '.tsv'):
                    import csv as _csv
                    delim = '\t' if ext == '.tsv' else ','
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        reader = _csv.reader(f, delimiter=delim)
                        rows = []
                        for i, row in enumerate(reader):
                            if i >= 35:
                                rows.append(['...'])
                                break
                            rows.append(row)
                    if rows:
                        info.append(f"Format: {'TSV' if ext == '.tsv' else 'CSV'}, {len(rows[0])} columns")
                        info.append(f"Columns: {', '.join(rows[0])}")
                        info.append(f"Preview ({min(5, len(rows)-1)} data rows):")
                        info.append("```")
                        info.append(', '.join(str(v) for v in rows[0]))
                        for r in rows[1:6]:
                            info.append(', '.join(str(v) for v in r))
                        info.append("```")

                elif ext == '.json':
                    import json as _json
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        raw = f.read(100_000)
                    try:
                        data = _json.loads(raw)
                        if isinstance(data, list):
                            info.append(f"Format: JSON array with {len(data)} items")
                            if data and isinstance(data[0], dict):
                                info.append(f"Item keys: {list(data[0].keys())}")
                                info.append("```json")
                                info.append(_json.dumps(data[0], indent=2)[:600])
                                info.append("```")
                        elif isinstance(data, dict):
                            info.append(f"Format: JSON object, keys: {list(data.keys())}")
                            info.append("```json")
                            info.append(_json.dumps({k: data[k] for k in list(data)[:10]}, indent=2)[:600])
                            info.append("```")
                    except _json.JSONDecodeError:
                        info.append("Note: file does not parse as valid JSON")

                elif ext in ('.txt', '.md', '.dat'):
                    with open(path, 'r', encoding='utf-8', errors='replace') as f:
                        preview = [f.readline() for _ in range(50)]
                    preview = [l.rstrip('\n') for l in preview if l]
                    info.append(f"Format: text ({len(preview)} lines shown):")
                    info.append("```")
                    info.extend(preview)
                    info.append("```")

                elif ext in ('.fits', '.fit', '.fts'):
                    try:
                        import astropy.io.fits as fits
                        with fits.open(path) as hdul:
                            info.append(f"Format: FITS with {len(hdul)} HDU(s):")
                            for i, hdu in enumerate(hdul):
                                shape = hdu.data.shape if hdu.data is not None else None
                                info.append(f"  HDU {i} ({type(hdu).__name__}): shape={shape}")
                                if hasattr(hdu, 'columns') and hdu.columns:
                                    info.append(f"    Columns: {', '.join(hdu.columns.names)}")
                                interesting = [
                                    'BUNIT', 'CRVAL1', 'CRVAL2', 'OBJECT',
                                    'TELESCOP', 'INSTRUME', 'DATE-OBS',
                                ]
                                if hdu.header:
                                    hdr_items = [(k, v) for k, v in hdu.header.items()
                                                 if k in interesting and v]
                                    if hdr_items:
                                        info.append("    Key header: " +
                                                    ', '.join(f'{k}={v}' for k, v in hdr_items))
                    except ImportError:
                        info.append("Format: FITS (astropy not available)")
                    except Exception as e:
                        info.append(f"Format: FITS (read error: {e})")

                elif ext in ('.hdf5', '.h5', '.he5'):
                    try:
                        import h5py
                        with h5py.File(path, 'r') as f:
                            info.append("Format: HDF5, structure:")
                            def _visit(name, obj):
                                if name.count('/') >= 4:
                                    return
                                if isinstance(obj, h5py.Dataset):
                                    info.append(f"  Dataset /{name}: shape={obj.shape}, dtype={obj.dtype}")
                                elif isinstance(obj, h5py.Group):
                                    info.append(f"  Group   /{name}/")
                            f.visititems(_visit)
                    except ImportError:
                        info.append("Format: HDF5 (h5py not available)")
                    except Exception as e:
                        info.append(f"Format: HDF5 (read error: {e})")

                elif ext == '.npy':
                    try:
                        import numpy as np
                        arr = np.load(path, allow_pickle=False)
                        info.append(f"Format: NumPy array, shape={arr.shape}, dtype={arr.dtype}")
                        if arr.size > 0:
                            info.append(f"  min={float(arr.min()):.4g}, "
                                        f"max={float(arr.max()):.4g}, "
                                        f"mean={float(arr.mean()):.4g}")
                    except Exception as e:
                        info.append(f"Format: NumPy array (read error: {e})")

                elif ext == '.npz':
                    try:
                        import numpy as np
                        data = np.load(path, allow_pickle=False)
                        info.append(f"Format: NumPy archive, {len(data.files)} arrays:")
                        for key in data.files:
                            arr = data[key]
                            info.append(f"  '{key}': shape={arr.shape}, dtype={arr.dtype}")
                    except Exception as e:
                        info.append(f"Format: NumPy archive (read error: {e})")

                elif ext == '.pdf':
                    try:
                        import pdfplumber
                        with pdfplumber.open(path) as pdf:
                            info.append(f"Format: PDF, {len(pdf.pages)} pages")
                            text = (pdf.pages[0].extract_text() or "")[:800]
                            info.append(f"First page text:\n```\n{text}\n```")
                    except ImportError:
                        try:
                            import pypdf
                            reader = pypdf.PdfReader(path)
                            info.append(f"Format: PDF, {len(reader.pages)} pages")
                            text = (reader.pages[0].extract_text() or "")[:800]
                            info.append(f"First page text:\n```\n{text}\n```")
                        except ImportError:
                            info.append("Format: PDF (no parser available)")
                    except Exception as e:
                        info.append(f"Format: PDF (read error: {e})")

                else:
                    info.append(f"Format: binary ({ext or 'unknown extension'}), {size_str}")

            except Exception as e:
                info.append(f"Error inspecting file: {e}")

            summaries.append("\n".join(info))

        files_section = "\n\n".join(summaries)
        with _console_lock:
            _console_buffers[buf_key].append(
                "Sending file metadata to LLM for scientific analysis..."
            )

        from cmbagent.llm_provider import safe_completion

        prompt = (
            "You are an expert research data analyst. Analyze the following research data files "
            "and produce a comprehensive, structured data context document.\n\n"
            "This context will be used by an AI research assistant to:\n"
            "1. Generate research ideas grounded in what the data can actually support\n"
            "2. Design methodologies that reference correct variable names, file paths, "
            "and data structures\n"
            "3. Write experiment code that correctly reads and processes these exact files\n\n"
            f"## Uploaded Research Files\n\n{files_section}\n\n"
            "## Instructions\n"
            "Generate a structured **Research Data Context** document covering:\n"
            "1. **Dataset Overview** - What dataset(s) are these? Source, survey, instrument, "
            "origin if identifiable.\n"
            "2. **File Inventory** - For each file: purpose, format, key contents, and the "
            "absolute path for use in code.\n"
            "3. **Key Variables & Columns** - Important variables with exact names, physical "
            "units, expected ranges, scientific meaning.\n"
            "4. **Data Dimensions & Scale** - Number of rows/samples, time range, spatial "
            "coverage, spectral range, etc.\n"
            "5. **Relationships Between Files** - How files relate to each other, join keys, "
            "shared indices.\n"
            "6. **Scientific Context** - What scientific questions this dataset is suited to "
            "answer.\n"
            "7. **Analysis Notes** - Known quirks, missing values, coordinate systems, "
            "calibration status, caveats.\n\n"
            "Be specific and factual. Use exact variable/column names from the files. "
            "Use markdown formatting.\n"
            "Output ONLY the data context document - no preamble, no explanation."
        )

        return safe_completion(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.3,
            max_tokens=4000,
        )

    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            context_text = await loop.run_in_executor(executor, _do_analysis)

        ctx_path = os.path.join(work_dir, "input_files", "data_context.md")
        with open(ctx_path, 'w', encoding='utf-8') as f:
            f.write(context_text)

        with _console_lock:
            _console_buffers[buf_key].append("\u2713 Analysis complete. Data context saved.")
            _console_buffers[buf_key].append("__ANALYZE_DONE__")
        logger.info("deepresearch_analyze_complete task_id=%s", task_id)
    except Exception as e:
        logger.error("deepresearch_analyze_failed task_id=%s error=%s", task_id, e, exc_info=True)
        with _console_lock:
            _console_buffers[buf_key].append(f"Error: {e}")
            _console_buffers[buf_key].append("__ANALYZE_ERROR__")
    finally:
        _running_analyses.pop(task_id, None)


# =============================================================================
# GET /api/deepresearch/{task_id}/stages/{num}/console  (REST fallback for console)
# =============================================================================

@router.get("/{task_id}/stages/{stage_num}/console")
async def get_stage_console(task_id: str, stage_num: int, since: int = 0):
    """Get console output lines for a running stage (REST polling fallback).

    Args:
        since: Line index to start from (for incremental fetching)
    """
    buf_key = f"{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {
        "lines": lines,
        "next_index": since + len(lines),
        "stage_num": stage_num,
    }


# =============================================================================
# GET /api/deepresearch/recent  (must be before /{task_id} to avoid route conflict)
# =============================================================================

@router.get("/recent", response_model=list[DeepresearchRecentTaskResponse])
async def list_recent_tasks():
    """List incomplete Deepresearch tasks for the resume flow."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        # Find deepresearch runs that are not completed/failed
        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.mode == "deepresearch-research",
                WorkflowRun.parent_run_id.is_(None),  # Only parent runs
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

            result.append(DeepresearchRecentTaskResponse(
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
# POST /api/deepresearch/{task_id}/stop
# =============================================================================

@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop a running Deepresearch task.

    Cancels any executing background stage and marks it as failed.
    """
    # Cancel any running asyncio tasks for this task_id
    cancelled = []
    for key in list(_running_tasks):
        if key.startswith(f"{task_id}:"):
            bg_task = _running_tasks.get(key)
            if bg_task and not bg_task.done():
                bg_task.cancel()
                cancelled.append(key)

    # Update DB: mark running stages as failed
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = parent.session_id
        repo = _get_stage_repo(db, session_id=session_id)
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
# DELETE /api/deepresearch/{task_id}
# =============================================================================

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a Deepresearch task, its DB records, and its work directory.

    Running stages are cancelled first.
    """
    import shutil

    # 1. Cancel any running background tasks
    for key in list(_running_tasks):
        if key.startswith(f"{task_id}:"):
            bg_task = _running_tasks.pop(key, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()

    # Clean up console buffers
    for key in list(_console_buffers):
        if key.startswith(f"{task_id}:"):
            with _console_lock:
                _console_buffers.pop(key, None)

    # 2. Delete DB records
    db = _get_db()
    work_dir = None
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        work_dir = (parent.meta or {}).get("work_dir")

        # TaskStage rows cascade-delete via FK, but delete explicitly for clarity
        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            db.delete(s)

        db.delete(parent)
        db.commit()
    finally:
        db.close()

    # 3. Remove work directory from disk
    if work_dir and os.path.isdir(work_dir):
        try:
            shutil.rmtree(work_dir)
        except Exception as exc:
            logger.warning("deepresearch_delete_workdir_failed path=%s error=%s", work_dir, exc)

    return {"status": "deleted", "task_id": task_id}


# =============================================================================
# POST /api/deepresearch/{task_id}/ai-edit-tex
# =============================================================================

@router.post("/{task_id}/ai-edit-tex", response_model=AiEditTexResponse)
async def ai_edit_tex(task_id: str, request: AiEditTexRequest):
    """Use an LLM to apply a natural-language edit instruction to a .tex file.

    Returns the edited LaTeX source. The caller is responsible for saving it
    (via PUT /api/files/content) before compiling.
    """
    import concurrent.futures

    tex_path = os.path.abspath(request.tex_path)
    if not os.path.isfile(tex_path):
        raise HTTPException(status_code=404, detail="TeX file not found")

    try:
        with open(tex_path, "r", encoding="utf-8") as f:
            original = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read TeX file: {e}")

    system_prompt = (
        "You are an expert LaTeX editor. The user will give you a LaTeX source document "
        "and an instruction describing modifications to make. "
        "Apply the instruction carefully and return ONLY the complete modified LaTeX source, "
        "with no additional commentary, markdown fences, or explanations."
    )
    user_prompt = (
        f"--- INSTRUCTION ---\n{request.instruction}\n\n"
        f"--- CURRENT LATEX SOURCE ---\n{original}"
    )

    try:
        def _call_llm():
            from cmbagent.llm_provider import safe_completion
            return safe_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="gpt-4o",
                temperature=0.2,
                max_tokens=8192,
            )

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            edited = await loop.run_in_executor(executor, _call_llm)

        return AiEditTexResponse(edited_content=edited or original)
    except Exception as e:
        logger.error("deepresearch_ai_edit_tex_failed task=%s error=%s", task_id, e)
        raise HTTPException(status_code=500, detail=f"AI edit failed: {e}")


# =============================================================================
# POST /api/deepresearch/{task_id}/compile-tex
# =============================================================================

@router.post("/{task_id}/compile-tex", response_model=CompileTexResponse)
async def compile_tex(task_id: str, request: CompileTexRequest):
    """Compile a .tex file to PDF using xelatex.

    The .tex file must already be saved on disk before calling this endpoint.
    Returns the path to the generated PDF and the compiler log.
    """
    import concurrent.futures
    import subprocess
    import shutil

    tex_path = os.path.abspath(request.tex_path)
    if not os.path.isfile(tex_path):
        raise HTTPException(status_code=404, detail="TeX file not found")

    tex_dir = os.path.dirname(tex_path)
    tex_name = os.path.basename(tex_path)
    tex_stem = os.path.splitext(tex_name)[0]
    pdf_path = os.path.join(tex_dir, f"{tex_stem}.pdf")
    bib_path = os.path.join(tex_dir, "bibliography.bib")

    def _compile():
        log_lines = []

        def run_xelatex():
            result = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-file-line-error", tex_name],
                cwd=tex_dir,
                input="\n",
                capture_output=True,
                text=True,
            )
            log_lines.append(result.stdout[-4000:] if result.stdout else "")
            return result.returncode == 0

        def run_bibtex():
            subprocess.run(
                ["bibtex", tex_stem],
                cwd=tex_dir,
                capture_output=True,
                text=True,
            )

        ok = run_xelatex()
        if os.path.exists(bib_path):
            run_bibtex()
            run_xelatex()
            run_xelatex()
        else:
            run_xelatex()

        # Clean auxiliary files
        for ext in ("aux", "log", "out", "bbl", "blg", "synctex.gz"):
            aux = os.path.join(tex_dir, f"{tex_stem}.{ext}")
            if os.path.exists(aux):
                os.remove(aux)

        success = os.path.exists(pdf_path)
        return success, "\n".join(log_lines)

    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            success, log = await loop.run_in_executor(executor, _compile)

        return CompileTexResponse(
            pdf_path=pdf_path if success else None,
            success=success,
            log=log,
        )
    except Exception as e:
        logger.error("deepresearch_compile_tex_failed task=%s error=%s", task_id, e)
        raise HTTPException(status_code=500, detail=f"Compilation failed: {e}")


# =============================================================================
# GET /api/deepresearch/{task_id}
# =============================================================================

@router.get("/{task_id}", response_model=DeepresearchTaskStateResponse)
async def get_task_state(task_id: str):
    """Get full task state for resume - all stages, costs, and progress."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        progress = repo.get_task_progress(parent_run_id=task_id)

        # Get cost info
        total_cost = None
        try:
            cost_repo = _get_cost_repo(db, session_id=parent.session_id)
            cost_info = cost_repo.get_task_total_cost(parent_run_id=task_id)
            total_cost = cost_info.get("total_cost_usd")
        except Exception:
            pass

        # Determine current stage
        current_stage = None
        for s in stages:
            if s.status == "running":
                current_stage = s.stage_number
                break
        if current_stage is None:
            # Find first non-completed stage
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

        return DeepresearchTaskStateResponse(
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
