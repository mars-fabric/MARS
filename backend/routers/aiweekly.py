"""
AI Weekly Report endpoints.

Phase-based pipeline:
  1. Data Collection — Direct tool calls (RSS, APIs, web search)
  2. Content Curation — LLM filters and deduplicates
  3. Report Generation — LLM writes the 4-section report
  4. Quality Review — LLM polishes to publication quality
"""

import asyncio
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from models.aiweekly_schemas import (
    AIWeeklyCreateRequest,
    AIWeeklyCreateResponse,
    AIWeeklyExecuteRequest,
    AIWeeklyStageResponse,
    AIWeeklyStageContentResponse,
    AIWeeklyContentUpdateRequest,
    AIWeeklyRefineRequest,
    AIWeeklyRefineResponse,
    AIWeeklyTaskStateResponse,
    AIWeeklyRecentTaskResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/aiweekly", tags=["AI Weekly Report"])


# =============================================================================
# Stage definitions
# =============================================================================
STAGE_DEFS = [
    {"number": 1, "name": "data_collection",     "shared_key": "raw_collection",  "file": "collection.md"},
    {"number": 2, "name": "content_curation",     "shared_key": "curated_items",   "file": "curated.md"},
    {"number": 3, "name": "report_generation",    "shared_key": "draft_report",    "file": "report_draft.md"},
    {"number": 4, "name": "quality_review",       "shared_key": "final_report",    "file": "report_final.md"},
]

STAGE_NAMES = {d["number"]: d["name"] for d in STAGE_DEFS}


def _get_default_model() -> str:
    try:
        from cmbagent.config import get_workflow_config
        return get_workflow_config().default_llm_model
    except Exception:
        return "gpt-4o"


# =============================================================================
# Background task tracking
# =============================================================================
_running_tasks: Dict[str, asyncio.Task] = {}
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()


class _ConsoleCapture:
    """Thread-safe stdout capture for streaming console to UI."""

    def __init__(self, buf_key: str, original):
        self._buf_key = buf_key
        self._original = original

    def write(self, text: str):
        if self._original:
            self._original.write(text)
        if text.strip():
            with _console_lock:
                _console_buffers.setdefault(self._buf_key, []).append(text.rstrip())

    def flush(self):
        if self._original:
            self._original.flush()

    def isatty(self):
        return False

    def fileno(self):
        if self._original:
            return self._original.fileno()
        raise AttributeError("no fileno")


def _get_console_lines(buf_key: str, since_index: int = 0) -> List[str]:
    with _console_lock:
        buf = _console_buffers.get(buf_key, [])
        return buf[since_index:]


# =============================================================================
# Phase class loading
# =============================================================================
_PHASE_CLASSES = {
    1: "cmbagent.phases.aiweekly.collection_phase:AIWeeklyCollectionPhase",
    2: "cmbagent.phases.aiweekly.curation_phase:AIWeeklyCurationPhase",
    3: "cmbagent.phases.aiweekly.generation_phase:AIWeeklyGenerationPhase",
    4: "cmbagent.phases.aiweekly.review_phase:AIWeeklyReviewPhase",
}


def _load_phase_class(stage_num: int):
    import importlib
    ref = _PHASE_CLASSES[stage_num]
    module_path, cls_name = ref.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


# =============================================================================
# Helper: build shared state from prior stages
# =============================================================================
def _build_shared_state(task_id: str, stage_num: int, task_config: dict) -> dict:
    from cmbagent.database.models import TaskStage
    from cmbagent.database.base import get_db_session

    shared: dict = {"task_config": task_config}
    db = get_db_session()
    try:
        stages = db.query(TaskStage).filter(
            TaskStage.parent_run_id == task_id,
            TaskStage.stage_number < stage_num,
            TaskStage.status == "completed",
        ).order_by(TaskStage.stage_number).all()

        for s in stages:
            if s.output_data and isinstance(s.output_data, dict):
                shared_data = s.output_data.get("shared", {})
                shared.update(shared_data)
    finally:
        db.close()
    return shared


# =============================================================================
# Stage execution
# =============================================================================
async def _run_aiweekly_stage(
    task_id: str,
    stage_num: int,
    task_text: str,
    work_dir: str,
    task_config: dict,
    model: str,
    n_reviews: int = 1,
    review_model: str = None,
    specialist_model: str = None,
    temperature: float = 0.7,
):
    from cmbagent.database.models import TaskStage
    from cmbagent.database.base import get_db_session
    from cmbagent.phases.base import PhaseContext

    buf_key = f"{task_id}:{stage_num}"
    old_stdout, old_stderr = sys.stdout, sys.stderr
    cap = _ConsoleCapture(buf_key, old_stdout)
    sys.stdout = cap
    sys.stderr = cap

    db = get_db_session()
    try:
        stage_row = db.query(TaskStage).filter(
            TaskStage.parent_run_id == task_id,
            TaskStage.stage_number == stage_num,
        ).first()
        if stage_row:
            stage_row.status = "running"
            stage_row.started_at = datetime.now(timezone.utc)
            db.commit()

        PhaseClass = _load_phase_class(stage_num)
        ConfigClass = PhaseClass.config_class if hasattr(PhaseClass, "config_class") else None

        if stage_num == 1:
            # Data collection — no LLM config needed
            phase = PhaseClass()
        else:
            config = ConfigClass(
                model=model,
                n_reviews=n_reviews,
                review_model=review_model,
                specialist_model=specialist_model,
                temperature=temperature,
            ) if ConfigClass else None
            phase = PhaseClass(config=config)

        shared_state = _build_shared_state(task_id, stage_num, task_config)
        ctx = PhaseContext(
            workflow_id=f"aiweekly_{task_id}",
            run_id=task_id,
            phase_id=f"stage{stage_num}_{uuid.uuid4().hex[:6]}",
            task=task_text,
            work_dir=work_dir,
            shared_state=shared_state,
        )

        # Stage 1 does blocking network I/O (RSS, APIs) — run in a thread
        # to avoid starving the event loop and crashing the HTTP server.
        # Stages 2-4 already use asyncio.to_thread internally for LLM calls.
        if stage_num == 1:
            import functools

            def _run_sync():
                import asyncio as _aio
                loop = _aio.new_event_loop()
                try:
                    return loop.run_until_complete(phase.execute(ctx))
                finally:
                    loop.close()

            result = await asyncio.wait_for(
                asyncio.to_thread(_run_sync), timeout=900
            )
        else:
            result = await asyncio.wait_for(phase.execute(ctx), timeout=900)

        if result.status.value == "completed":
            output_data = result.context.output_data or {}
            stage_def = next((d for d in STAGE_DEFS if d["number"] == stage_num), {})
            content = output_data.get("shared", {}).get(stage_def.get("shared_key", ""), "")

            if stage_row:
                stage_row.status = "completed"
                stage_row.output_data = output_data
                stage_row.completed_at = datetime.now(timezone.utc)
                db.commit()

            # If all stages are now completed, mark the workflow run as completed
            all_stages = db.query(TaskStage).filter(
                TaskStage.parent_run_id == task_id
            ).all()
            if all_stages and all(s.status == "completed" for s in all_stages):
                from cmbagent.database.models import WorkflowRun
                run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
                if run and run.status != "completed":
                    run.status = "completed"
                    run.completed_at = datetime.now(timezone.utc)
                    db.commit()

            print(f"[Stage {stage_num}] ✅ Complete — {len(content)} chars")
        else:
            error_msg = result.error or "Unknown error"
            if stage_row:
                stage_row.status = "failed"
                stage_row.error_message = error_msg
                db.commit()
            print(f"[Stage {stage_num}] ❌ Failed — {error_msg}")

    except asyncio.TimeoutError:
        if stage_row:
            stage_row.status = "failed"
            stage_row.error_message = "Stage timed out (900s)"
            db.commit()
        print(f"[Stage {stage_num}] ❌ Timeout")
    except Exception as exc:
        logger.error("AIWeekly stage %d failed: %s", stage_num, exc, exc_info=True)
        if stage_row:
            stage_row.status = "failed"
            stage_row.error_message = str(exc)
            db.commit()
        print(f"[Stage {stage_num}] ❌ Error: {exc}")
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        db.close()


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/create", response_model=AIWeeklyCreateResponse)
async def create_aiweekly_task(request: AIWeeklyCreateRequest):
    """Create a new AI Weekly Report task with 4 stages."""
    from cmbagent.database.models import WorkflowRun, TaskStage
    from cmbagent.database.base import get_db_session
    from services.session_manager import get_session_manager

    db = get_db_session()
    try:
        sm = get_session_manager()
        session_id = sm.create_session(
            mode="aiweekly",
            config={},
            name=f"AI Weekly: {request.date_from} to {request.date_to}",
        )
        task_id = str(uuid.uuid4())

        work_dir = request.work_dir or os.path.join(
            os.path.expanduser("~/Desktop/cmbdir"), "aiweekly", task_id[:8]
        )
        os.makedirs(work_dir, exist_ok=True)

        task_config = {
            "date_from": request.date_from,
            "date_to": request.date_to,
            "topics": request.topics,
            "sources": request.sources,
            "style": request.style,
        }

        run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="aiweekly",
            agent="phase_orchestrator",
            model=_get_default_model(),
            status="executing",
            task_description=f"AI Weekly Report: {request.date_from} to {request.date_to}",
            meta={
                "work_dir": work_dir,
                "task_config": task_config,
                "orchestration": "phase-based",
            },
        )
        db.add(run)
        db.flush()

        stages_out = []
        for sd in STAGE_DEFS:
            ts = TaskStage(
                id=str(uuid.uuid4()),
                parent_run_id=task_id,
                stage_number=sd["number"],
                stage_name=sd["name"],
                status="pending",
            )
            db.add(ts)
            stages_out.append({
                "stage_number": sd["number"],
                "stage_name": sd["name"],
                "status": "pending",
            })

        db.commit()

        # Save task config to file
        input_dir = os.path.join(work_dir, "input_files")
        os.makedirs(input_dir, exist_ok=True)
        import json
        with open(os.path.join(input_dir, "task_config.json"), "w") as f:
            json.dump(task_config, f, indent=2)

        return AIWeeklyCreateResponse(
            task_id=task_id,
            work_dir=work_dir,
            stages=stages_out,
        )
    finally:
        db.close()


@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_aiweekly_stage(
    task_id: str,
    stage_num: int,
    request: AIWeeklyExecuteRequest = None,
):
    """Execute a specific stage."""
    if stage_num < 1 or stage_num > 4:
        raise HTTPException(400, f"Invalid stage number: {stage_num}")

    from cmbagent.database.models import WorkflowRun
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(404, "Task not found")

        meta = run.meta or {}
        work_dir = meta.get("work_dir", "")
        task_config = meta.get("task_config", {})

        config_overrides = (request.config_overrides if request else None) or {}
        model = config_overrides.get("model", _get_default_model())
        n_reviews = config_overrides.get("n_reviews", 1)
        review_model = config_overrides.get("review_model") or None
        specialist_model = config_overrides.get("specialist_model") or None
        temperature = config_overrides.get("temperature", 0.7)

        task_text = f"AI Weekly Report: {task_config.get('date_from')} to {task_config.get('date_to')}"

        task = asyncio.create_task(
            _run_aiweekly_stage(
                task_id, stage_num, task_text, work_dir, task_config,
                model, n_reviews, review_model, specialist_model, temperature,
            )
        )
        _running_tasks[f"{task_id}:{stage_num}"] = task

        return {"status": "started", "stage_num": stage_num, "model": model, "review_model": review_model, "specialist_model": specialist_model}
    finally:
        db.close()


# =============================================================================
# Recent tasks (for resume flow — must be BEFORE /{task_id} routes)
# =============================================================================
@router.get("/recent", response_model=List[AIWeeklyRecentTaskResponse])
async def get_recent_aiweekly_tasks():
    """List incomplete AI Weekly tasks for the resume flow."""
    from cmbagent.database.models import WorkflowRun, TaskStage
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        runs = (
            db.query(WorkflowRun)
            .filter(
                WorkflowRun.mode == "aiweekly",
                WorkflowRun.status.in_(["executing", "draft"]),
            )
            .order_by(WorkflowRun.started_at.desc())
            .limit(10)
            .all()
        )

        results = []
        for run in runs:
            stages = (
                db.query(TaskStage)
                .filter(TaskStage.parent_run_id == run.id)
                .order_by(TaskStage.stage_number)
                .all()
            )
            current = None
            completed_count = 0
            for s in stages:
                if s.status == "completed":
                    completed_count += 1
                elif current is None:
                    current = s.stage_number

            total_stages = len(stages) or 4
            progress = round((completed_count / total_stages) * 100, 1)

            # Skip fully-completed tasks
            if progress >= 100:
                continue

            results.append(AIWeeklyRecentTaskResponse(
                task_id=run.id,
                task=run.task_description or "",
                status=run.status,
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current,
                progress_percent=progress,
            ))

        return results
    finally:
        db.close()


@router.get("/{task_id}", response_model=AIWeeklyTaskStateResponse)
async def get_aiweekly_task(task_id: str):
    """Get full task state."""
    from cmbagent.database.models import WorkflowRun, TaskStage
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(404, "Task not found")

        stages = db.query(TaskStage).filter(
            TaskStage.parent_run_id == task_id
        ).order_by(TaskStage.stage_number).all()

        completed = sum(1 for s in stages if s.status == "completed")
        progress = (completed / len(STAGE_DEFS)) * 100 if stages else 0

        return AIWeeklyTaskStateResponse(
            task_id=task_id,
            status=run.status,
            progress=progress,
            stages=[
                AIWeeklyStageResponse(
                    stage_number=s.stage_number,
                    stage_name=s.stage_name,
                    status=s.status,
                    error=s.error_message,
                    started_at=str(s.started_at) if s.started_at else None,
                    completed_at=str(s.completed_at) if s.completed_at else None,
                ) for s in stages
            ],
        )
    finally:
        db.close()


@router.get("/{task_id}/stages/{stage_num}/content", response_model=AIWeeklyStageContentResponse)
async def get_aiweekly_stage_content(task_id: str, stage_num: int):
    """Get stage output content."""
    from cmbagent.database.models import TaskStage
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        stage = db.query(TaskStage).filter(
            TaskStage.parent_run_id == task_id,
            TaskStage.stage_number == stage_num,
        ).first()
        if not stage:
            raise HTTPException(404, "Stage not found")

        stage_def = next((d for d in STAGE_DEFS if d["number"] == stage_num), {})
        shared_key = stage_def.get("shared_key", "")
        content = ""
        if stage.output_data and isinstance(stage.output_data, dict):
            content = stage.output_data.get("shared", {}).get(shared_key, "")

        return AIWeeklyStageContentResponse(
            stage_number=stage_num,
            stage_name=stage_def.get("name", ""),
            content=content,
            field=shared_key,
        )
    finally:
        db.close()


@router.put("/{task_id}/stages/{stage_num}/content")
async def save_aiweekly_stage_content(task_id: str, stage_num: int, request: AIWeeklyContentUpdateRequest):
    """Save user edits to stage content."""
    from cmbagent.database.models import WorkflowRun, TaskStage
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        stage = db.query(TaskStage).filter(
            TaskStage.parent_run_id == task_id,
            TaskStage.stage_number == stage_num,
        ).first()
        if not stage:
            raise HTTPException(404, "Stage not found")

        if not stage.output_data:
            stage.output_data = {}
        if "shared" not in stage.output_data:
            stage.output_data["shared"] = {}
        stage.output_data["shared"][request.field] = request.content

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(stage, "output_data")
        db.commit()

        # Also save to file
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if run and run.meta:
            work_dir = run.meta.get("work_dir", "")
            stage_def = next((d for d in STAGE_DEFS if d["number"] == stage_num), {})
            filename = stage_def.get("file")
            if filename and work_dir:
                file_path = os.path.join(work_dir, "input_files", filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(request.content)

        return {"status": "saved", "field": request.field}
    finally:
        db.close()


@router.post("/{task_id}/stages/{stage_num}/refine", response_model=AIWeeklyRefineResponse)
async def refine_aiweekly_content(task_id: str, stage_num: int, request: AIWeeklyRefineRequest):
    """LLM refinement of stage content."""
    from cmbagent.llm_provider import safe_completion
    from cmbagent.phases.rfp.token_utils import count_tokens, get_model_limits

    model = _get_default_model()
    max_ctx, _ = get_model_limits(model)
    system_msg = "You are an AI news editor. Refine the content based on the instruction. Return ONLY the refined markdown."
    user_msg = f"Current content:\n\n{request.content}\n\n---\n\nInstruction: {request.message}"

    prompt_tokens = count_tokens(system_msg, model) + count_tokens(user_msg, model) + 6
    available = max_ctx - prompt_tokens - 200
    max_comp = min(16384, max(available, 4096))

    def _call():
        return safe_completion(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model,
            temperature=0.7,
            max_tokens=max_comp,
        )

    refined = await asyncio.to_thread(_call)
    refined = refined or request.content
    return AIWeeklyRefineResponse(refined_content=refined, message="Content refined successfully")


@router.get("/{task_id}/stages/{stage_num}/console")
async def get_aiweekly_console(task_id: str, stage_num: int, since: int = 0):
    """Get console output for a running stage."""
    buf_key = f"{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {"lines": lines, "next_index": since + len(lines), "stage_num": stage_num}


@router.post("/{task_id}/reset-from/{stage_num}")
async def reset_aiweekly_from_stage(task_id: str, stage_num: int):
    """Reset stages from stage_num onwards to pending."""
    from cmbagent.database.models import TaskStage
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        stages = db.query(TaskStage).filter(
            TaskStage.parent_run_id == task_id,
            TaskStage.stage_number >= stage_num,
        ).all()

        for s in stages:
            s.status = "pending"
            s.output_data = None
            s.error_message = None
            s.started_at = None
            s.completed_at = None

        db.commit()
        return {"status": "reset", "from_stage": stage_num}
    finally:
        db.close()


# =============================================================================
# Stop a running task
# =============================================================================
@router.post("/{task_id}/stop")
async def stop_aiweekly_task(task_id: str):
    """Stop a running AI Weekly task.

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
    from cmbagent.database.models import WorkflowRun, TaskStage
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        stages = (
            db.query(TaskStage)
            .filter(TaskStage.parent_run_id == task_id)
            .all()
        )
        for s in stages:
            if s.status == "running":
                s.status = "failed"
                s.error_message = "Stopped by user"

        parent.status = "failed"
        db.commit()

        return {"status": "stopped", "task_id": task_id, "cancelled_stages": cancelled}
    finally:
        db.close()


@router.delete("/{task_id}")
async def delete_aiweekly_task(task_id: str):
    """Delete a weekly task and its data."""
    import shutil
    from cmbagent.database.models import WorkflowRun
    from cmbagent.database.base import get_db_session

    db = get_db_session()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(404, "Task not found")

        work_dir = (run.meta or {}).get("work_dir", "")
        if work_dir and os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

        db.delete(run)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


@router.get("/{task_id}/download/{filename}")
async def download_aiweekly_artifact(task_id: str, filename: str):
    """Download a report file."""
    from cmbagent.database.models import WorkflowRun
    from cmbagent.database.base import get_db_session

    # Validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")

    db = get_db_session()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(404, "Task not found")

        work_dir = (run.meta or {}).get("work_dir", "")
        file_path = os.path.join(work_dir, "input_files", filename)
        if not os.path.isfile(file_path):
            raise HTTPException(404, "File not found")

        return FileResponse(
            file_path,
            filename=filename,
            media_type="application/octet-stream",
        )
    finally:
        db.close()


def _md_to_pdf(md_path: str, pdf_path: str) -> None:
    """Convert a markdown file to PDF using markdown + PyMuPDF."""
    import markdown
    import fitz

    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc"],
    )

    html = f"""<!DOCTYPE html>
<html><head><style>
body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a1a; }}
h1 {{ font-size: 20pt; margin-top: 18pt; margin-bottom: 8pt; }}
h2 {{ font-size: 16pt; margin-top: 14pt; margin-bottom: 6pt; }}
h3 {{ font-size: 13pt; margin-top: 10pt; margin-bottom: 4pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 10pt 0; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; font-size: 9pt; }}
th {{ background-color: #f2f2f2; font-weight: bold; }}
a {{ color: #1a73e8; }}
ul, ol {{ padding-left: 18pt; }}
</style></head><body>{html_body}</body></html>"""

    story = fitz.Story(html=html)
    writer = fitz.DocumentWriter(pdf_path)
    mediabox = fitz.paper_rect("a4")
    content_rect = mediabox + (36, 36, -36, -36)  # 0.5-inch margins

    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()


@router.get("/{task_id}/download-pdf/{filename}")
async def download_aiweekly_artifact_pdf(task_id: str, filename: str):
    """Download a report file converted to PDF."""
    from cmbagent.database.models import WorkflowRun
    from cmbagent.database.base import get_db_session

    # Validate filename — must be a .md file
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    if not filename.endswith(".md"):
        raise HTTPException(400, "Only markdown files can be converted to PDF")

    db = get_db_session()
    try:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(404, "Task not found")

        work_dir = (run.meta or {}).get("work_dir", "")
        md_path = os.path.join(work_dir, "input_files", filename)
        if not os.path.isfile(md_path):
            raise HTTPException(404, "File not found")

        pdf_filename = filename.rsplit(".", 1)[0] + ".pdf"
        pdf_path = os.path.join(work_dir, "input_files", pdf_filename)

        _md_to_pdf(md_path, pdf_path)

        return FileResponse(
            pdf_path,
            filename=pdf_filename,
            media_type="application/pdf",
        )
    finally:
        db.close()
