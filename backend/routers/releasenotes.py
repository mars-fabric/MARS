"""
Release Notes — 5-stage DB-backed pipeline with context carryover.

Mirrors the Deepresearch architecture:
- Database-backed stages (WorkflowRun + TaskStage)
- Shared-state context carryover between stages
- Console output streaming via polling
- Content editing and AI refinement per stage

Stages
──────
1. collect_and_diff  → validate repo, clone, generate diffs (automatic)
2. analysis          → impact + migration + documentation (agent-powered)
3. release_notes     → commercial + developer release notes (agent-powered)
4. migration         → generate migration scripts (agent-powered)
5. package           → bundle all outputs

GET  /{task_id}                         → current task state
GET  /{task_id}/stages/{num}/content    → stage output + shared_state
PUT  /{task_id}/stages/{num}/content    → save user edits
POST /{task_id}/stages/{num}/refine     → AI refinement
GET  /{task_id}/stages/{num}/console    → poll console output
"""

import asyncio
import io
import os
import subprocess
import sys
import tempfile
import shutil
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models.releasenotes_schemas import (
    ReleaseNotesCreateRequest,
    ReleaseNotesCreateResponse,
    ReleaseNotesExecuteRequest,
    ReleaseNotesStageResponse,
    ReleaseNotesStageContentResponse,
    ReleaseNotesContentUpdateRequest,
    ReleaseNotesRefineRequest,
    ReleaseNotesRefineResponse,
    ReleaseNotesTaskStateResponse,
    ReleaseNotesRecentTaskResponse,
    ReleaseNotesResumeResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/release-notes", tags=["Release Notes"])


# ═══════════════════════════════════════════════════════════════════════════
#  Stage definitions
# ═══════════════════════════════════════════════════════════════════════════

STAGE_DEFS = [
    {"number": 1, "name": "collect_and_diff", "shared_key": "diff_context", "file": "diff_context.md"},
    {"number": 2, "name": "analysis",         "shared_key": "analysis_comparison", "file": "analysis_comparison.md",
     "multi_doc": True, "doc_keys": ["analysis_base", "analysis_head", "analysis_comparison"],
     "doc_files": ["analysis_base.md", "analysis_head.md", "analysis_comparison.md"]},
    {"number": 3, "name": "release_notes",    "shared_key": "release_notes", "file": "release_notes.md",
     "multi_doc": True, "doc_keys": ["release_notes_commercial", "release_notes_developer", "release_notes_code"],
     "doc_files": ["release_notes_commercial.md", "release_notes_developer.md", "release_notes_code.py"]},
    {"number": 4, "name": "migration",         "shared_key": "migration_script", "file": "migration_script.md"},
    {"number": 5, "name": "package",          "shared_key": None,           "file": None},
]

FILE_CATEGORIES = {
    "code":      [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".cs", ".rb", ".php", ".swift", ".kt"],
    "config":    [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".properties"],
    "database":  [".sql", ".migration", ".prisma"],
    "migration": [".alembic", ".migrate"],
    "docs":      [".md", ".rst", ".txt", ".adoc"],
    "infra":     ["Dockerfile", "docker-compose", ".tf", ".hcl", "Makefile", "Jenkinsfile", ".github"],
    "test":      ["test_", "_test.", ".spec.", ".test."],
}

_running_tasks: Dict[str, asyncio.Task] = {}
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════
#  DB helpers
# ═══════════════════════════════════════════════════════════════════════════

_db_initialized = False


def _get_db():
    global _db_initialized
    if not _db_initialized:
        from cmbagent.database.base import init_database
        init_database()
        _db_initialized = True
    from cmbagent.database.base import get_db_session
    return get_db_session()


def _get_stage_repo(db, session_id: str = "releasenotes"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_cost_repo(db, session_id: str = "releasenotes"):
    from cmbagent.database.repository import CostRepository
    return CostRepository(db, session_id=session_id)


def _get_work_dir(task_id: str, session_id: str = None, base_work_dir: str = None) -> str:
    from core.config import settings
    base = os.path.expanduser(base_work_dir or settings.default_work_dir)
    if session_id:
        return os.path.join(base, "sessions", session_id, "tasks", task_id)
    return os.path.join(base, "releasenotes_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    return run.session_id if run else "releasenotes"


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "releasenotes") -> Dict[str, Any]:
    """Reconstruct shared_state from completed stages — context carryover."""
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> ReleaseNotesStageResponse:
    return ReleaseNotesStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Console capture
# ═══════════════════════════════════════════════════════════════════════════

class _ConsoleCapture:
    def __init__(self, buf_key: str, original_stream):
        self._buf_key = buf_key
        self._original = original_stream

    def write(self, text: str):
        if self._original:
            self._original.write(text)
        if text and text.strip():
            with _console_lock:
                _console_buffers.setdefault(self._buf_key, []).append(text.rstrip())

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


# ═══════════════════════════════════════════════════════════════════════════
#  Git helpers
# ═══════════════════════════════════════════════════════════════════════════

def _validate_repo_url(url: str) -> str:
    url = url.strip()
    if not (url.startswith("https://github.com/") or url.startswith("https://gitlab.com/")):
        raise HTTPException(status_code=400, detail="Only HTTPS GitHub/GitLab URLs are supported.")
    if url.endswith(".git"):
        url = url[:-4]
    return url


def _categorise_file(filepath: str) -> str:
    lower = filepath.lower()
    for cat, patterns in FILE_CATEGORIES.items():
        for pat in patterns:
            if pat.startswith("."):
                if lower.endswith(pat):
                    return cat
            else:
                if pat in lower:
                    return cat
    return "other"


def _run_git(args: List[str], cwd: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  POST /create
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/create", response_model=ReleaseNotesCreateResponse)
async def create_release_notes_task(request: ReleaseNotesCreateRequest):
    """Create a new Release Notes task with 5 pending stages."""
    repo_url = _validate_repo_url(request.repo_url)
    base = request.base_branch.strip()
    head = request.head_branch.strip()

    if not base or not head:
        raise HTTPException(status_code=400, detail="Both branches are required.")
    if base == head:
        raise HTTPException(status_code=400, detail="Branches must be different.")

    repo_name = repo_url.rstrip("/").split("/")[-1]
    task_id = str(uuid.uuid4())

    from services.session_manager import get_session_manager
    from core.config import settings
    sm = get_session_manager()
    base_work_dir = request.work_dir or settings.default_work_dir
    base_work_dir = os.path.expanduser(base_work_dir)

    session_id = sm.create_session(
        mode="release-notes",
        config={"task_id": task_id, "base_work_dir": base_work_dir},
        name=f"Release Notes: {repo_name} ({base} → {head})",
    )

    work_dir = _get_work_dir(task_id, session_id=session_id, base_work_dir=base_work_dir)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.path.join(work_dir, "input_files"), exist_ok=True)

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent_run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="release-notes",
            agent="engineer",
            model="gpt-4o",
            status="executing",
            task_description=f"Generate release notes for {repo_name}: {base} → {head}",
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "base_work_dir": base_work_dir,
                "repo_url": repo_url,
                "repo_name": repo_name,
                "base_branch": base,
                "head_branch": head,
                "auth_token": request.auth_token,
                "extra_instructions": request.extra_instructions or "",
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
                    "repo_url": repo_url, "repo_name": repo_name,
                    "base_branch": base, "head_branch": head,
                },
            )
            stage_responses.append(_stage_to_response(stage))

        db.commit()
        logger.info("release_notes_task_created task_id=%s session_id=%s", task_id, session_id)
        return ReleaseNotesCreateResponse(task_id=task_id, session_id=session_id, work_dir=work_dir, stages=stage_responses)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  POST /{task_id}/stages/{num}/execute
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_stage(task_id: str, stage_num: int, request: ReleaseNotesExecuteRequest = None):
    """Trigger stage execution asynchronously."""
    if stage_num < 1 or stage_num > 5:
        raise HTTPException(status_code=400, detail="stage_num must be 1-5")

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

        if stage.status == "running" and bg_key in _running_tasks and not _running_tasks[bg_key].done():
            raise HTTPException(status_code=409, detail="Stage is already running")
        if stage.status == "completed":
            raise HTTPException(status_code=409, detail="Stage is already completed")

        for s in stages:
            if s.stage_number < stage_num and s.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first",
                )

        from cmbagent.database.models import WorkflowRun
        parent_run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent_run:
            raise HTTPException(status_code=404, detail="Parent workflow run not found")

        meta = parent_run.meta or {}
        work_dir = meta.get("work_dir") or _get_work_dir(task_id)

        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)
        shared_state["repo_url"] = meta.get("repo_url", "")
        shared_state["repo_name"] = meta.get("repo_name", "")
        shared_state["base_branch"] = meta.get("base_branch", "")
        shared_state["head_branch"] = meta.get("head_branch", "")
        shared_state["auth_token"] = meta.get("auth_token")
        shared_state["extra_instructions"] = meta.get("extra_instructions", "")

        repo.update_stage_status(stage.id, "running")
        config_overrides = (request.config_overrides if request else None) or {}
    finally:
        db.close()

    task = asyncio.create_task(
        _run_stage(task_id, stage_num, work_dir, shared_state, config_overrides, session_id)
    )
    _running_tasks[bg_key] = task
    return {"status": "executing", "stage_num": stage_num, "task_id": task_id}


# ═══════════════════════════════════════════════════════════════════════════
#  Background stage execution
# ═══════════════════════════════════════════════════════════════════════════

async def _run_stage(
    task_id: str, stage_num: int, work_dir: str,
    shared_state: Dict[str, Any], config_overrides: Dict[str, Any], session_id: str,
):
    """Execute a Release Notes stage in the background.

    Stages 1 & 5: no AI (git ops / packaging).
    Stages 2-4: planning_and_control_context_carryover via releasenotes_helpers.
    Matches the Deepresearch / NewsPulse execution pattern exactly.
    """
    sdef = STAGE_DEFS[stage_num - 1]
    buf_key = f"{task_id}:{stage_num}"
    with _console_lock:
        _console_buffers[buf_key] = [f"Starting {sdef['name']}..."]

    try:
        if stage_num == 1:
            output_data = await _run_collect_and_diff(shared_state, work_dir, buf_key)
        elif stage_num in (2, 3, 4):
            output_data = await _run_planning_control_stage(
                task_id, stage_num, sdef, buf_key,
                work_dir, shared_state, config_overrides, session_id,
            )
        elif stage_num == 5:
            output_data = await _run_package(task_id, shared_state, buf_key)
        else:
            raise ValueError(f"Unknown stage {stage_num}")

        # Persist to DB (fresh session)
        persist_db = _get_db()
        try:
            repo = _get_stage_repo(persist_db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(
                    stage.id, "completed",
                    output_data=output_data,
                    output_files=list(output_data.get("artifacts", {}).values()),
                )
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} ({sdef['name']}) completed successfully."
                    )

            # Check if all stages completed → mark workflow done
            all_stages = repo.list_stages(parent_run_id=task_id)
            if all(s.status == "completed" for s in all_stages):
                from cmbagent.database.models import WorkflowRun
                parent = persist_db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                if parent:
                    parent.status = "completed"
                    parent.completed_at = datetime.now(timezone.utc)

            persist_db.commit()
            logger.info("release_notes_stage_completed task=%s stage=%d", task_id, stage_num)
        finally:
            persist_db.close()

    except Exception as e:
        logger.error("release_notes_stage_exception task=%s stage=%d error=%s", task_id, stage_num, e, exc_info=True)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"Error: {e}")

        err_db = _get_db()
        try:
            repo = _get_stage_repo(err_db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "failed", error_message=str(e))

            # Update parent WorkflowRun status to failed
            from cmbagent.database.models import WorkflowRun
            parent = err_db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            if parent:
                parent.status = "failed"

            err_db.commit()
        finally:
            err_db.close()
    finally:
        _running_tasks.pop(f"{task_id}:{stage_num}", None)


async def _run_planning_control_stage(
    task_id: str,
    stage_num: int,
    sdef: dict,
    buf_key: str,
    work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any],
    session_id: str,
):
    """Run stages 2-4 via one_shot with full callback infrastructure.

    Follows the Deepresearch 7-phase pattern:
      1. Setup DB session for cost + event tracking
      2. Build WorkflowCallbacks (agent msgs, code exec, tool calls, cost)
      3. Build stage-specific kwargs + dispatch
      4. Execute with unified stdout/stderr capture
      5. Extract results
      6. Cost safety net (scan work_dir)
      7. Close callback DB session
    """
    from cmbagent.callbacks import merge_callbacks, create_print_callbacks, WorkflowCallbacks
    from cmbagent.task_framework import releasenotes_helpers as helpers

    # ── Phase 1: Set up DB session for cost + event tracking ──
    db = _get_db()

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
        logger.warning("releasenotes_cost_collector_init_failed error=%s", exc)

    try:
        from cmbagent.database.repository import EventRepository
        event_repo = EventRepository(db, session_id)
    except Exception as exc:
        logger.warning("releasenotes_event_repo_init_failed error=%s", exc)

    # ── Phase 2: Build callback infrastructure ──
    execution_order = [0]

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
            logger.debug("releasenotes_event_create_failed error=%s", exc)
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
            logger.debug("releasenotes_code_event_failed error=%s", exc)
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
            logger.debug("releasenotes_tool_event_failed error=%s", exc)
            try:
                db.rollback()
            except Exception:
                pass

    def on_cost_update(cost_data):
        if cost_collector:
            try:
                cost_collector.collect_from_callback(cost_data)
            except Exception as exc:
                logger.debug("releasenotes_cost_callback_failed error=%s", exc)
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

    # ── Phase 3: Build stage-specific kwargs + dispatch ──
    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Stage {stage_num} ({sdef['name']}) initialized, executing..."
        )

    if stage_num == 2:
        output_data = await _run_analysis_one_shot(
            task_id, buf_key, work_dir, shared_state,
            config_overrides, helpers, workflow_callbacks,
        )
    elif stage_num == 3:
        output_data = await _run_release_notes_one_shot(
            task_id, buf_key, work_dir, shared_state,
            config_overrides, helpers, workflow_callbacks,
        )
    elif stage_num == 4:
        output_data = await _run_migration_one_shot(
            task_id, buf_key, work_dir, shared_state,
            config_overrides, helpers, workflow_callbacks,
        )

    # ── Phase 6: Cost safety net — scan work_dir for cost files ──
    if cost_collector:
        try:
            cost_collector.collect_from_work_dir(work_dir)
        except Exception as exc:
            logger.debug("releasenotes_cost_work_dir_failed error=%s", exc)

    # ── Phase 7: Close callback DB session ──
    try:
        db.close()
    except Exception:
        pass

    return output_data


def _run_one_shot_sync(task: str, agent: str = "researcher", work_dir: str = None,
                       config_overrides: Dict[str, Any] = None,
                       callbacks=None) -> Dict[str, Any]:
    """Synchronous one_shot agent call for use with asyncio.to_thread.

    Accepts optional WorkflowCallbacks for cost tracking and event logging,
    matching the Deepresearch callback injection pattern.
    """
    import cmbagent
    from cmbagent.utils import get_api_keys_from_env

    config_overrides = config_overrides or {}
    researcher_model = config_overrides.get("researcher_model", config_overrides.get("model", "gpt-4.1"))
    engineer_model = config_overrides.get("engineer_model", config_overrides.get("model", "gpt-4o"))

    return cmbagent.one_shot(
        task=task,
        agent=agent,
        max_rounds=config_overrides.get("max_rounds", 3),
        engineer_model=engineer_model,
        researcher_model=researcher_model,
        work_dir=work_dir or tempfile.gettempdir(),
        api_keys=get_api_keys_from_env(),
        clear_work_dir=False,
        callbacks=callbacks,
    )


async def _run_analysis_one_shot(
    task_id: str, buf_key: str, work_dir: str,
    shared_state: Dict[str, Any],
    config_overrides: Dict[str, Any], helpers, callbacks=None,
) -> Dict[str, Any]:
    """Stage 2: Run 3 one_shot calls (base/head/comparison) sequentially.

    Matches the Deepresearch pattern with unified stdout/stderr capture
    and callback injection into each agent call.
    """
    from cmbagent.task_framework.prompts.releasenotes.analysis import (
        base_researcher_prompt, head_researcher_prompt, comparison_researcher_prompt,
    )

    repo_name = shared_state.get("repo_name", "repository")
    base_branch = shared_state.get("base_branch", "")
    head_branch = shared_state.get("head_branch", "")
    diff_context = shared_state.get("diff_context", "")

    fmt = dict(repo_name=repo_name, base_branch=base_branch,
               head_branch=head_branch, diff_context=diff_context)

    doc_specs = [
        ("analysis_base", "analysis_base.md", "Last Release Branch",
         base_researcher_prompt.format(**fmt)),
        ("analysis_head", "analysis_head.md", "Current Release Branch",
         head_researcher_prompt.format(**fmt)),
        ("analysis_comparison", "analysis_comparison.md", "Detailed Comparison",
         comparison_researcher_prompt.format(**fmt)),
    ]

    results_map: Dict[str, str] = {}
    artifacts: Dict[str, str] = {}
    chat_histories: Dict[str, list] = {}

    # Unified stdout/stderr capture for entire stage
    original_stdout, original_stderr = sys.stdout, sys.stderr
    capture_out = _ConsoleCapture(buf_key, original_stdout)
    capture_err = _ConsoleCapture(buf_key, original_stderr)

    try:
        sys.stdout = capture_out
        sys.stderr = capture_err

        for i, (doc_key, doc_file, label, task_prompt) in enumerate(doc_specs):
            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Running analysis document {i+1}/3: {label}..."
                )

            stage_work_dir = os.path.join(work_dir, f"stage_2_{doc_key}")
            os.makedirs(stage_work_dir, exist_ok=True)

            result = await asyncio.to_thread(
                _run_one_shot_sync, task_prompt, "researcher",
                stage_work_dir, config_overrides, callbacks,
            )

            text = helpers.extract_stage_result(result)
            file_path = helpers.save_stage_file(text, work_dir, doc_file)

            results_map[doc_key] = text
            artifacts[doc_key] = file_path
            chat_histories[doc_key] = result.get("chat_history", [])

            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Document {i+1}/3 ({label}) complete — {len(text)} chars"
                )

    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    return helpers.build_analysis_output(
        results_map["analysis_base"],
        results_map["analysis_head"],
        results_map["analysis_comparison"],
        artifacts,
        chat_histories,
    )


async def _run_release_notes_one_shot(
    task_id: str, buf_key: str, work_dir: str,
    shared_state: Dict[str, Any], config_overrides: Dict[str, Any],
    helpers, callbacks=None,
) -> Dict[str, Any]:
    """Stage 3: single one_shot call — commercial + developer release notes.

    Unified stdout/stderr capture with callback injection.
    """
    from cmbagent.task_framework.prompts.releasenotes.release_notes import (
        release_notes_researcher_prompt,
    )

    extra = shared_state.get("extra_instructions", "")
    extra_section = f"## Additional Instructions\n{extra}" if extra else ""

    task_prompt = release_notes_researcher_prompt.format(
        repo_name=shared_state.get("repo_name", "repository"),
        base_branch=shared_state.get("base_branch", ""),
        head_branch=shared_state.get("head_branch", ""),
        diff_context=shared_state.get("diff_context", ""),
        analysis_base=shared_state.get("analysis_base", ""),
        analysis_head=shared_state.get("analysis_head", ""),
        analysis_comparison=shared_state.get("analysis_comparison", ""),
        extra_instructions_section=extra_section,
    )

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            "Generating release notes (commercial + developer)..."
        )

    stage_work_dir = os.path.join(work_dir, "stage_3_release_notes")
    os.makedirs(stage_work_dir, exist_ok=True)

    # Unified stdout/stderr capture
    original_stdout, original_stderr = sys.stdout, sys.stderr
    capture_out = _ConsoleCapture(buf_key, original_stdout)
    capture_err = _ConsoleCapture(buf_key, original_stderr)

    try:
        sys.stdout = capture_out
        sys.stderr = capture_err
        result = await asyncio.to_thread(
            _run_one_shot_sync, task_prompt, "researcher",
            stage_work_dir, config_overrides, callbacks,
        )
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    text = helpers.extract_stage_result(result)
    file_path = helpers.save_stage_file(text, work_dir, "release_notes.md")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Release notes complete — {len(text)} chars"
        )

    return helpers.build_release_notes_output(text, file_path, result.get("chat_history", []))


async def _run_migration_one_shot(
    task_id: str, buf_key: str, work_dir: str,
    shared_state: Dict[str, Any], config_overrides: Dict[str, Any],
    helpers, callbacks=None,
) -> Dict[str, Any]:
    """Stage 4: single one_shot call — migration scripts.

    Unified stdout/stderr capture with callback injection.
    """
    from cmbagent.task_framework.prompts.releasenotes.migration import (
        migration_researcher_prompt,
    )

    migration_type = config_overrides.get("migration_type", "comprehensive")
    extra = shared_state.get("extra_instructions", "")
    extra_section = f"## Additional Instructions\n{extra}" if extra else ""

    task_prompt = migration_researcher_prompt.format(
        repo_name=shared_state.get("repo_name", "repository"),
        base_branch=shared_state.get("base_branch", ""),
        head_branch=shared_state.get("head_branch", ""),
        migration_type=migration_type,
        diff_context=shared_state.get("diff_context", ""),
        analysis_comparison=shared_state.get("analysis_comparison", ""),
        release_notes=shared_state.get("release_notes", ""),
        extra_instructions_section=extra_section,
    )

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Generating {migration_type} migration script..."
        )

    stage_work_dir = os.path.join(work_dir, "stage_4_migration")
    os.makedirs(stage_work_dir, exist_ok=True)

    # Unified stdout/stderr capture
    original_stdout, original_stderr = sys.stdout, sys.stderr
    capture_out = _ConsoleCapture(buf_key, original_stdout)
    capture_err = _ConsoleCapture(buf_key, original_stderr)

    try:
        sys.stdout = capture_out
        sys.stderr = capture_err
        result = await asyncio.to_thread(
            _run_one_shot_sync, task_prompt, "researcher",
            stage_work_dir, config_overrides, callbacks,
        )
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    text = helpers.extract_stage_result(result)
    file_path = helpers.save_stage_file(text, work_dir, "migration_script.md")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Migration script complete — {len(text)} chars"
        )

    return helpers.build_migration_output(
        text, migration_type, file_path, result.get("chat_history", []),
    )


async def _run_collect_and_diff(shared_state: Dict[str, Any], work_dir: str, buf_key: str) -> Dict[str, Any]:
    """Stage 1: Clone repo, capture SHAs, generate diffs."""
    repo_url = shared_state["repo_url"]
    base = shared_state["base_branch"]
    head = shared_state["head_branch"]
    token = shared_state.get("auth_token")

    clone_url = repo_url
    if token:
        clone_url = repo_url.replace("https://", f"https://{token}@")

    tmp_dir = tempfile.mkdtemp(prefix="rn_clone_")

    def _do():
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"Cloning {repo_url}...")

        result = subprocess.run(
            ["git", "clone", "--no-single-branch", "--depth=100", "--branch", head, clone_url, tmp_dir],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Clone failed: {result.stderr.strip()}")

        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append("Fetching base branch...")

        r = _run_git(["fetch", "origin", base, "--depth=100"], cwd=tmp_dir)
        if r.returncode != 0:
            raise RuntimeError(f"Failed to fetch base: {r.stderr.strip()}")

        base_sha = _run_git(["rev-parse", f"origin/{base}"], cwd=tmp_dir).stdout.strip()
        head_sha = _run_git(["rev-parse", f"origin/{head}"], cwd=tmp_dir).stdout.strip()

        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"SHAs: base={base_sha[:8]} head={head_sha[:8]}")
            _console_buffers[buf_key].append("Generating diffs...")

        diff_range = f"origin/{base}..origin/{head}"

        log_r = _run_git(["log", "--oneline", "--no-merges", diff_range], cwd=tmp_dir)
        commits = [ln.strip() for ln in log_r.stdout.strip().splitlines() if ln.strip()]

        merge_r = _run_git(["log", "--oneline", "--merges", diff_range], cwd=tmp_dir)
        merges = [ln.strip() for ln in merge_r.stdout.strip().splitlines() if ln.strip()]

        files_r = _run_git(["diff", "--name-status", diff_range], cwd=tmp_dir)
        raw_files = [ln.strip() for ln in files_r.stdout.strip().splitlines() if ln.strip()]

        categorised: Dict[str, List[str]] = {}
        file_list = []
        for line in raw_files:
            parts = line.split("\t", 1)
            status_ch = parts[0] if parts else "?"
            fpath = parts[1] if len(parts) > 1 else line
            cat = _categorise_file(fpath)
            categorised.setdefault(cat, []).append(fpath)
            file_list.append({"status": status_ch, "path": fpath, "category": cat})

        stat_r = _run_git(["diff", "--stat", diff_range], cwd=tmp_dir)
        diff_stat = stat_r.stdout.strip()

        diff_r = _run_git(["diff", diff_range], cwd=tmp_dir, timeout=180)
        full_diff = diff_r.stdout
        if len(full_diff) > 200_000:
            full_diff = full_diff[:200_000] + "\n\n... [diff truncated] ..."

        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(
                f"Found {len(commits)} commits, {len(file_list)} files across {len(categorised)} categories."
            )

        return {
            "base_sha": base_sha, "head_sha": head_sha,
            "commits": commits, "commit_count": len(commits),
            "merges": merges, "merge_count": len(merges),
            "file_list": file_list, "file_count": len(file_list),
            "categorised": {k: len(v) for k, v in categorised.items()},
            "categorised_files": categorised,
            "diff_stat": diff_stat, "full_diff": full_diff,
        }

    try:
        data = await asyncio.to_thread(_do)
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    repo_name = shared_state.get("repo_name", "repository")
    diff_context = (
        f"# Diff Context — {repo_name}\n\n"
        f"Comparing `{base}` → `{head}`\n\n"
        f"- {data['commit_count']} commits, {data['file_count']} files changed\n"
        f"- Categories: {', '.join(f'{k}: {v}' for k, v in data['categorised'].items())}\n\n"
        f"## Diff Stat\n```\n{data['diff_stat']}\n```\n\n"
        f"## Changed Files\n"
    )
    for cat, files in data["categorised_files"].items():
        diff_context += f"\n### {cat.upper()} ({len(files)} files)\n"
        for f in files[:50]:
            diff_context += f"- {f}\n"
        if len(files) > 50:
            diff_context += f"- ... and {len(files) - 50} more\n"
    diff_context += f"\n## Full Diff\n```\n{data['full_diff']}\n```\n"

    ctx_path = os.path.join(work_dir, "input_files", "diff_context.md")
    os.makedirs(os.path.dirname(ctx_path), exist_ok=True)
    with open(ctx_path, "w") as f:
        f.write(diff_context)

    return {
        "shared": {
            "diff_context": diff_context,
            "repo_name": repo_name,
            "base_branch": base, "head_branch": head,
            "commit_count": data["commit_count"], "file_count": data["file_count"],
            "categorised": data["categorised"], "diff_stat": data["diff_stat"],
            "base_sha": data["base_sha"], "head_sha": data["head_sha"],
            "commits": data["commits"][:200], "merges": data["merges"][:100],
            "categorised_files": data["categorised_files"],
            "full_diff": data["full_diff"],
        },
        "artifacts": {"diff_context": ctx_path},
    }


async def _run_package(task_id: str, shared_state: Dict[str, Any], buf_key: str) -> Dict[str, Any]:
    """Stage 5: Bundle all outputs."""
    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append("Assembling output package...")

    package = {
        "task_id": task_id,
        "repo_name": shared_state.get("repo_name"),
        "base_branch": shared_state.get("base_branch"),
        "head_branch": shared_state.get("head_branch"),
        "commit_count": shared_state.get("commit_count", 0),
        "file_count": shared_state.get("file_count", 0),
        "has_analysis": bool(shared_state.get("analysis_base")),
        "has_release_notes": bool(shared_state.get("release_notes_commercial")),
        "has_code_guide": bool(shared_state.get("release_notes_code")),
        "has_migration_script": bool(shared_state.get("migration_script")),
        "migration_type": shared_state.get("migration_type"),
    }

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append("Output package assembled.")

    return {"shared": {}, "package": package}



# ═══════════════════════════════════════════════════════════════════════════
#  GET /recent — list resumable tasks (must be before /{task_id})
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/recent", response_model=list[ReleaseNotesRecentTaskResponse])
async def list_recent_tasks():
    """List incomplete Release Notes tasks for the resume flow."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.mode == "release-notes",
                WorkflowRun.parent_run_id.is_(None),
                WorkflowRun.status.in_(["executing", "draft", "planning"]),
            )
            .order_by(WorkflowRun.started_at.desc())
            .limit(20)
            .all()
        )

        result = []
        for run in runs:
            meta = run.meta or {}
            repo = _get_stage_repo(db, session_id=run.session_id)
            progress = repo.get_task_progress(parent_run_id=run.id)
            current_stage = None
            stages = repo.list_stages(parent_run_id=run.id)
            for s in stages:
                if s.status != "completed":
                    current_stage = s.stage_number
                    break

            result.append(ReleaseNotesRecentTaskResponse(
                task_id=run.id,
                repo_name=meta.get("repo_name", ""),
                base_branch=meta.get("base_branch", ""),
                head_branch=meta.get("head_branch", ""),
                status=run.status,
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current_stage,
                progress_percent=progress.get("progress_percent", 0.0),
            ))

        return result
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  GET /{task_id}
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{task_id}", response_model=ReleaseNotesTaskStateResponse)
async def get_task_state(task_id: str):
    """Get full task state for resume — all stages, costs, and progress."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = parent.session_id
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        progress = repo.get_task_progress(parent_run_id=task_id)
        meta = parent.meta or {}

        # Get cost info
        total_cost = None
        try:
            cost_repo = _get_cost_repo(db, session_id=session_id)
            cost_info = cost_repo.get_task_total_cost(parent_run_id=task_id)
            total_cost = cost_info.get("total_cost_usd")
        except Exception:
            pass

        # Determine current stage (running first, then first non-completed)
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

        return ReleaseNotesTaskStateResponse(
            task_id=task_id,
            session_id=session_id,
            repo_url=meta.get("repo_url", ""),
            repo_name=meta.get("repo_name", ""),
            base_branch=meta.get("base_branch", ""),
            head_branch=meta.get("head_branch", ""),
            status=parent.status or "executing",
            work_dir=meta.get("work_dir"),
            created_at=parent.started_at.isoformat() if parent.started_at else None,
            stages=[_stage_to_response(s) for s in stages],
            current_stage=current_stage,
            progress_percent=progress.get("progress_percent", 0.0),
            total_cost_usd=total_cost,
        )
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  POST /{task_id}/resume — auto-execute next pending stage
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/{task_id}/resume", response_model=ReleaseNotesResumeResponse)
async def resume_task(task_id: str, request: ReleaseNotesExecuteRequest = None):
    """Resume a task from the last completed stage.

    Finds the first non-completed stage (pending or failed) and triggers
    execution — exactly like the client calling GET /{task_id} then
    POST /{task_id}/stages/{next}/execute, but in a single call.
    """
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        if parent.status == "completed":
            return ReleaseNotesResumeResponse(
                task_id=task_id, status="completed", stage_num=None,
                message="All stages already completed",
            )

        session_id = parent.session_id
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)

        # Find first non-completed stage (prefer pending, allow failed retry)
        next_stage = None
        for s in stages:
            if s.status in ("pending", "failed"):
                next_stage = s
                break
            if s.status == "running":
                bg_key = f"{task_id}:{s.stage_number}"
                if bg_key in _running_tasks and not _running_tasks[bg_key].done():
                    return ReleaseNotesResumeResponse(
                        task_id=task_id, status="executing",
                        stage_num=s.stage_number,
                        message=f"Stage {s.stage_number} ({s.stage_name}) is still running",
                    )
                # Stale running — treat as retryable
                next_stage = s
                break

        if not next_stage:
            return ReleaseNotesResumeResponse(
                task_id=task_id, status="completed", stage_num=None,
                message="No pending stages to execute",
            )

        # Validate prerequisites (all prior stages must be completed)
        for s in stages:
            if s.stage_number < next_stage.stage_number and s.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first",
                )

        meta = parent.meta or {}
        work_dir = meta.get("work_dir") or _get_work_dir(task_id)
        shared_state = build_shared_state(task_id, next_stage.stage_number, db, session_id=session_id)
        shared_state["repo_url"] = meta.get("repo_url", "")
        shared_state["repo_name"] = meta.get("repo_name", "")
        shared_state["base_branch"] = meta.get("base_branch", "")
        shared_state["head_branch"] = meta.get("head_branch", "")
        shared_state["auth_token"] = meta.get("auth_token")
        shared_state["extra_instructions"] = meta.get("extra_instructions", "")

        repo.update_stage_status(next_stage.id, "running")
        config_overrides = (request.config_overrides if request else None) or {}
    finally:
        db.close()

    stage_num = next_stage.stage_number
    bg_key = f"{task_id}:{stage_num}"
    task = asyncio.create_task(
        _run_stage(task_id, stage_num, work_dir, shared_state, config_overrides, session_id)
    )
    _running_tasks[bg_key] = task

    return ReleaseNotesResumeResponse(
        task_id=task_id, status="executing", stage_num=stage_num,
        message=f"Resumed: executing stage {stage_num} ({next_stage.stage_name})",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  GET/PUT/POST — content, refine, console
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{task_id}/stages/{stage_num}/content", response_model=ReleaseNotesStageContentResponse)
async def get_stage_content(task_id: str, stage_num: int):
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
        documents = None
        if stage.output_data:
            shared = stage.output_data.get("shared")
            sdef = STAGE_DEFS[stage_num - 1]

            # Multi-document stages (analysis)
            if sdef.get("multi_doc") and shared:
                documents = {}
                for key in sdef["doc_keys"]:
                    documents[key] = shared.get(key, "")
                content = shared.get(sdef["shared_key"])
            elif sdef["shared_key"] and shared:
                content = shared.get(sdef["shared_key"])

            if not content and sdef.get("file"):
                from cmbagent.database.models import WorkflowRun
                parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
                fp = os.path.join(wd, "input_files", sdef["file"])
                if os.path.exists(fp):
                    with open(fp, "r") as f:
                        content = f.read()

        return ReleaseNotesStageContentResponse(
            stage_number=stage.stage_number, stage_name=stage.stage_name,
            status=stage.status, content=content,
            shared_state=shared, output_files=stage.output_files,
            documents=documents,
        )
    finally:
        db.close()


@router.put("/{task_id}/stages/{stage_num}/content")
async def update_stage_content(task_id: str, stage_num: int, request: ReleaseNotesContentUpdateRequest):
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
            raise HTTPException(status_code=400, detail="Can only edit completed stages")

        output_data = stage.output_data or {}
        shared = output_data.get("shared", {})
        shared[request.field] = request.content
        output_data["shared"] = shared
        repo.update_stage_status(stage.id, "completed", output_data=output_data)

        # Write to the correct file based on field key
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id)) if parent else _get_work_dir(task_id)
        input_dir = os.path.join(wd, "input_files")
        os.makedirs(input_dir, exist_ok=True)

        # For multi-doc stages, map field key to the correct file
        if sdef.get("multi_doc") and sdef.get("doc_keys") and sdef.get("doc_files"):
            key_to_file = dict(zip(sdef["doc_keys"], sdef["doc_files"]))
            target_file = key_to_file.get(request.field)
            if target_file:
                fp = os.path.join(input_dir, target_file)
                with open(fp, "w") as f:
                    f.write(request.content)
        elif sdef.get("file"):
            fp = os.path.join(input_dir, sdef["file"])
            with open(fp, "w") as f:
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


@router.post("/{task_id}/stages/{stage_num}/refine", response_model=ReleaseNotesRefineResponse)
async def refine_stage_content(task_id: str, stage_num: int, request: ReleaseNotesRefineRequest):
    from cmbagent.llm_provider import safe_completion

    content = request.content or ""
    logger.info("releasenotes_refine task=%s stage=%d content_len=%d", task_id, stage_num, len(content))

    # Truncate very large content to keep LLM response within proxy timeout.
    # Preserve start + end for context (same approach as RFP refine).
    MAX_CONTENT_CHARS = 12_000
    if len(content) > MAX_CONTENT_CHARS:
        half = MAX_CONTENT_CHARS // 2
        content = content[:half] + "\n\n[... middle section trimmed for brevity ...]\n\n" + content[-half:]
        logger.info("releasenotes_refine content truncated to %d chars", len(content))

    system_msg = (
        "You are helping a software engineer refine release documentation. "
        "Return ONLY the refined content, no preamble or explanations."
    )
    user_msg = (
        f"--- CURRENT CONTENT ---\n{content}\n\n"
        f"--- USER REQUEST ---\n{request.message}"
    )

    try:
        def _call_refine():
            return safe_completion(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                model="gpt-4o",
                temperature=0.7,
                max_tokens=4096,
            )

        refined = await asyncio.to_thread(_call_refine)
        refined = refined or request.content

        logger.info("releasenotes_refine_ok task=%s stage=%d", task_id, stage_num)
        return ReleaseNotesRefineResponse(refined_content=refined)
    except Exception as e:
        logger.error("releasenotes_refine_failed task=%s stage=%d error=%s", task_id, stage_num, e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {e}")


@router.get("/{task_id}/stages/{stage_num}/console")
async def get_stage_console(task_id: str, stage_num: int, since: int = 0):
    buf_key = f"{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    bg_key = f"{task_id}:{stage_num}"
    is_running = bg_key in _running_tasks and not _running_tasks[bg_key].done()
    return {"lines": lines, "next_index": since + len(lines), "is_done": not is_running and since > 0}


@router.get("/{task_id}/stages/{stage_num}/download")
async def download_stage_file(task_id: str, stage_num: int, doc_key: str = None):
    """Download a stage output file. For multi-doc stages, specify doc_key."""
    if stage_num < 1 or stage_num > 5:
        raise HTTPException(status_code=400, detail="stage_num must be 1-5")

    sdef = STAGE_DEFS[stage_num - 1]
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")
        wd = (parent.meta or {}).get("work_dir", _get_work_dir(task_id))
    finally:
        db.close()

    if sdef.get("multi_doc") and doc_key:
        key_to_file = dict(zip(sdef["doc_keys"], sdef["doc_files"]))
        fname = key_to_file.get(doc_key)
        if not fname:
            raise HTTPException(status_code=400, detail=f"Unknown doc_key: {doc_key}")
    elif sdef.get("file"):
        fname = sdef["file"]
    else:
        raise HTTPException(status_code=400, detail="No file for this stage")

    file_path = os.path.join(wd, "input_files", fname)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {fname}")

    return FileResponse(
        path=file_path,
        filename=fname,
        media_type="text/markdown",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  POST /{task_id}/stop — cancel running task
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop a running Release Notes task.

    Cancels any executing background stage and marks it as failed.
    """
    cancelled = []
    for key in list(_running_tasks):
        if key.startswith(f"{task_id}:"):
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


# ═══════════════════════════════════════════════════════════════════════════
#  DELETE /{task_id} — delete task and all history
# ═══════════════════════════════════════════════════════════════════════════

@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a Release Notes task, its DB records, and its work directory.

    Removes:
    - Running background tasks (cancelled)
    - Console output buffers
    - Database records (WorkflowRun + TaskStage rows)
    - Work directory from disk
    """
    # 1. Cancel any running background tasks
    for key in list(_running_tasks):
        if key.startswith(f"{task_id}:"):
            bg_task = _running_tasks.pop(key, None)
            if bg_task and not bg_task.done():
                bg_task.cancel()

    # 2. Clean up console buffers
    for key in list(_console_buffers):
        if key.startswith(f"{task_id}:"):
            with _console_lock:
                _console_buffers.pop(key, None)

    # 3. Delete DB records and get work directory
    db = _get_db()
    work_dir = None
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        work_dir = (parent.meta or {}).get("work_dir")

        # Delete all TaskStage rows (cascade handled by FK)
        repo = _get_stage_repo(db, session_id=parent.session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        for s in stages:
            db.delete(s)

        # Delete WorkflowRun record
        db.delete(parent)
        db.commit()
    finally:
        db.close()

    # 4. Remove work directory from disk
    if work_dir and os.path.isdir(work_dir):
        try:
            shutil.rmtree(work_dir)
        except Exception as exc:
            logger.warning("releasenotes_delete_workdir_failed path=%s error=%s", work_dir, exc)

    return {"status": "deleted", "task_id": task_id}
