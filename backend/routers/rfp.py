"""
RFP (Request for Proposal) Proposal Generator endpoints.

Uses the Phase-Based workflow system: each stage is executed as an
RFP Phase subclass with a built-in generate → review cycle for
higher-quality output.

Stages:
  1. Requirements Analysis — Parse and structure the RFP requirements
  2. Tools & Technology Selection — Identify required tools and technologies
  3. Cloud & Infrastructure Planning — Design cloud architecture and cost estimates
  4. Implementation Plan — Create phased delivery roadmap
  5. Architecture Design — Produce system architecture and layout
  6. Execution Strategy — Define how the plan is carried out to final product
  7. Proposal Compilation — Assemble the complete proposal document
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

from models.rfp_schemas import (
    RfpCreateRequest,
    RfpCreateResponse,
    RfpExecuteRequest,
    RfpStageResponse,
    RfpStageContentResponse,
    RfpContentUpdateRequest,
    RfpRefineRequest,
    RfpRefineResponse,
    RfpTaskStateResponse,
    RfpRecentTaskResponse,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/rfp", tags=["RFP Proposal Generator"])


# =============================================================================
# Stage definitions
# =============================================================================
STAGE_DEFS = [
    {"number": 1, "name": "requirements_analysis",     "shared_key": "requirements_analysis",  "file": "requirements.md"},
    {"number": 2, "name": "tools_technology",           "shared_key": "tools_technology",       "file": "tools.md"},
    {"number": 3, "name": "cloud_infrastructure",       "shared_key": "cloud_infrastructure",   "file": "cloud.md"},
    {"number": 4, "name": "implementation_plan",        "shared_key": "implementation_plan",    "file": "implementation.md"},
    {"number": 5, "name": "architecture_design",        "shared_key": "architecture_design",    "file": "architecture.md"},
    {"number": 6, "name": "execution_strategy",         "shared_key": "execution_strategy",     "file": "execution.md"},
    {"number": 7, "name": "proposal_compilation",       "shared_key": "proposal_compilation",   "file": "proposal.md"},
]

STAGE_NAMES = {d["number"]: d["name"] for d in STAGE_DEFS}

# ---------------------------------------------------------------------------
# Default model — pulled from cmbagent WorkflowConfig so it stays in sync
# with the rest of the platform.  The user can still override per-stage via
# config_overrides in the execute request.
# ---------------------------------------------------------------------------
def _get_default_rfp_model() -> str:
    """Return the default LLM model from cmbagent workflow config."""
    try:
        from cmbagent.config import get_workflow_config
        return get_workflow_config().default_llm_model
    except Exception:
        return "gpt-4o"


# =============================================================================
# Background task and console buffer tracking
# =============================================================================
_running_tasks: Dict[str, asyncio.Task] = {}
_console_buffers: Dict[str, List[str]] = {}
_console_lock = threading.Lock()


# =============================================================================
# Phase class lookup — lazy import to avoid circular deps
# =============================================================================

_PHASE_CLASSES = {
    1: "cmbagent.phases.rfp.requirements_phase:RfpRequirementsPhase",
    2: "cmbagent.phases.rfp.tools_phase:RfpToolsPhase",
    3: "cmbagent.phases.rfp.cloud_phase:RfpCloudPhase",
    4: "cmbagent.phases.rfp.implementation_phase:RfpImplementationPhase",
    5: "cmbagent.phases.rfp.architecture_phase:RfpArchitecturePhase",
    6: "cmbagent.phases.rfp.execution_phase:RfpExecutionPhase",
    7: "cmbagent.phases.rfp.proposal_phase:RfpProposalPhase",
}


def _load_phase_class(stage_num: int):
    """Dynamically import the Phase class for a given stage number."""
    import importlib
    ref = _PHASE_CLASSES[stage_num]
    module_path, cls_name = ref.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


# =============================================================================
# Helpers
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


def _get_stage_repo(db, session_id: str = "rfp"):
    from cmbagent.database.repository import TaskStageRepository
    return TaskStageRepository(db, session_id=session_id)


def _get_cost_repo(db, session_id: str = "rfp"):
    from cmbagent.database.repository import CostRepository
    return CostRepository(db, session_id=session_id)


def _get_work_dir(task_id: str, session_id: str = None, base_work_dir: str = None) -> str:
    from core.config import settings
    base = os.path.expanduser(base_work_dir or settings.default_work_dir)
    if session_id:
        return os.path.join(base, "sessions", session_id, "tasks", task_id)
    return os.path.join(base, "rfp_tasks", task_id)


def _get_session_id_for_task(task_id: str, db) -> str:
    from cmbagent.database.models import WorkflowRun
    run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
    if run:
        return run.session_id
    return "rfp"


def build_shared_state(task_id: str, up_to_stage: int, db, session_id: str = "rfp") -> Dict[str, Any]:
    repo = _get_stage_repo(db, session_id=session_id)
    stages = repo.list_stages(parent_run_id=task_id)
    shared: Dict[str, Any] = {}
    for stage in stages:
        if stage.stage_number < up_to_stage and stage.status == "completed":
            if stage.output_data and "shared" in stage.output_data:
                shared.update(stage.output_data["shared"])
    return shared


def _stage_to_response(stage) -> RfpStageResponse:
    return RfpStageResponse(
        stage_number=stage.stage_number,
        stage_name=stage.stage_name,
        status=stage.status,
        started_at=stage.started_at.isoformat() if stage.started_at else None,
        completed_at=stage.completed_at.isoformat() if stage.completed_at else None,
        error=stage.error_message,
    )


def _build_rfp_context(work_dir: str) -> str:
    """Read uploaded RFP files and build context string."""
    input_dir = os.path.join(work_dir, "input_files")
    if not os.path.isdir(input_dir):
        return ""

    sections = []
    auto_generated = {
        "rfp_input.md", "rfp_context.md", "requirements.md", "tools.md", "cloud.md",
        "implementation.md", "architecture.md", "execution.md", "proposal.md",
    }

    for entry in sorted(os.listdir(input_dir)):
        if entry in auto_generated:
            continue
        full_path = os.path.join(input_dir, entry)
        if not os.path.isfile(full_path):
            continue
        size = os.path.getsize(full_path)
        if size == 0:
            continue
        size_str = f"{size}" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
        sections.append(f"\n### Uploaded File: `{entry}` ({size_str})")
        sections.append(f"**Path:** `{full_path}`\n")
        _, ext = os.path.splitext(entry)
        ext_lower = ext.lower()

        # Extract text from PDFs
        if ext_lower == '.pdf':
            try:
                from services.pdf_extractor import extract_pdf_content
                pdf_text = extract_pdf_content(full_path)
                if pdf_text:
                    pdf_text = pdf_text.replace('{', '{{').replace('}', '}}')
                    sections.append(f"**Extracted Content (text, tables, and image descriptions):**\n```\n{pdf_text}\n```\n")
            except Exception:
                pass
        # Preview text-based files
        elif ext_lower in {'.txt', '.md', '.csv', '.json', '.xml', '.html', '.tsv'}:
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    preview = f.read(4096)
                # Escape braces to prevent str.format() from interpreting them
                preview = preview.replace('{', '{{').replace('}', '}}')
                sections.append(f"**Preview:**\n```\n{preview}\n```\n")
            except Exception:
                pass

    if not sections:
        return ""
    return "\n---\n## Uploaded RFP Documents\n" + "\n".join(sections)


# Console buffer helpers (exposed for WebSocket in main.py)

def _get_console_lines(buf_key: str, since_index: int = 0) -> List[str]:
    with _console_lock:
        buf = _console_buffers.get(buf_key, [])
        return buf[since_index:]


def _clear_console_buffer(buf_key: str):
    with _console_lock:
        _console_buffers.pop(buf_key, None)


class _ConsoleCapture:
    """Thread-safe stdout/stderr capture that writes to both original stream and shared buffer."""

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
        raise AttributeError("no fileno")


# =============================================================================
# Phase-based stage execution engine
# =============================================================================

async def _run_rfp_stage(
    task_id: str,
    stage_num: int,
    work_dir: str,
    rfp_content: str,
    rfp_context: str,
    shared_state: Dict[str, Any],
    config_overrides: Optional[Dict[str, Any]] = None,
    session_id: str = "rfp",
):
    """Execute a single RFP stage using the Phase-Based workflow (generate → review)."""
    buf_key = f"{task_id}:{stage_num}"

    # Initialize console buffer immediately so the UI can start showing output
    with _console_lock:
        _console_buffers[buf_key] = [f"Starting stage {stage_num}..."]

    db = _get_db()

    try:
        repo = _get_stage_repo(db, session_id=session_id)
        cost_repo = _get_cost_repo(db, session_id=session_id)

        # Set up console capture
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = _ConsoleCapture(buf_key, old_stdout)
        sys.stderr = _ConsoleCapture(buf_key, old_stderr)

        stage_def = STAGE_DEFS[stage_num - 1]
        stage_name = stage_def["name"]

        # Build phase config from overrides
        # Use dynamic model from workflow config; allow user override
        model = _get_default_rfp_model()
        n_reviews = 1
        if config_overrides:
            model = config_overrides.get("model", model)
            n_reviews = config_overrides.get("n_reviews", n_reviews)

        print(f"Configuring {stage_name} with model={model}, n_reviews={n_reviews}")

        # Load and instantiate the Phase class for this stage
        PhaseClass = _load_phase_class(stage_num)
        phase_config = PhaseClass.config_class(
            model=model,
            n_reviews=n_reviews,
        )
        phase = PhaseClass(config=phase_config)

        # Build PhaseContext
        from cmbagent.phases.base import PhaseContext as _PhaseContext

        full_shared = dict(shared_state)
        full_shared["rfp_context"] = rfp_context or ""

        ctx = _PhaseContext(
            workflow_id=f"rfp_{task_id}",
            run_id=task_id,
            phase_id=f"{stage_name}_{uuid.uuid4().hex[:6]}",
            task=rfp_content or "",
            work_dir=work_dir,
            shared_state=full_shared,
        )

        print(f"Calling LLM for {stage_name} (this may take a minute)...")

        # Execute the phase (generate → review cycle) with a timeout
        try:
            result = await asyncio.wait_for(phase.execute(ctx), timeout=600)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Stage {stage_name} timed out after 600 seconds")

        if result.status.value != "completed":
            raise RuntimeError(result.error or f"Phase {stage_name} failed")

        print(f"{stage_name} completed successfully")

        # Extract content from phase output
        output = result.context.output_data
        shared_key = stage_def.get("shared_key")
        result_content = ""
        if shared_key and "shared" in output:
            result_content = output["shared"].get(shared_key, "")

        # Track cost from phase output
        cost_data = output.get("cost", {})
        prompt_tokens = cost_data.get("prompt_tokens", 0) if cost_data else 0
        completion_tokens = cost_data.get("completion_tokens", 0) if cost_data else 0
        cost_usd = (prompt_tokens * 0.002 + completion_tokens * 0.008) / 1000
        if cost_data and (prompt_tokens or completion_tokens):
            try:
                cost_repo.record_cost(
                    run_id=task_id,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost_usd,
                )
            except Exception as e:
                logger.warning(f"Failed to record cost: {e}")

        # Save output to file
        file_name = stage_def.get("file")
        if file_name and result_content:
            input_dir = os.path.join(work_dir, "input_files")
            os.makedirs(input_dir, exist_ok=True)
            file_path = os.path.join(input_dir, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result_content)

        # Build output data for DB
        output_data: Dict[str, Any] = {
            "shared": {**shared_state},
            "artifacts": {"model": model, "n_reviews": n_reviews, "orchestration": "phase-based"},
            "cost": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
            },
        }
        if shared_key:
            output_data["shared"][shared_key] = result_content

        # For stage 7, also save the compiled proposal
        if stage_num == 7:
            proposal_path = os.path.join(work_dir, "input_files", "proposal.md")
            with open(proposal_path, "w", encoding="utf-8") as f:
                f.write(result_content)
            output_data["artifacts"]["proposal_path"] = proposal_path

        # Update stage status
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)
        if stage:
            file_name = stage_def.get("file")
            repo.update_stage_status(
                stage.id,
                status="completed",
                output_data=output_data,
                output_files=[file_name] if file_name else [],
            )

        # If all stages are now completed, mark the workflow run as completed
        all_stages = repo.list_stages(parent_run_id=task_id)
        if all_stages and all(s.status == "completed" for s in all_stages):
            from cmbagent.database.models import WorkflowRun
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            if run and run.status != "completed":
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()

            # Generate cost summary file alongside the stage output files
            try:
                _generate_cost_summary(task_id, work_dir, all_stages, cost_repo)
            except Exception as exc:
                logger.warning(f"Failed to generate cost summary: {exc}")

    except Exception as e:
        logger.error(f"RFP stage {stage_num} failed: {e}", exc_info=True)
        # Write error to console buffer so the UI can display it
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"Error: {e}")
        try:
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(
                    stage.id,
                    status="failed",
                    error_message=str(e)[:2000],
                )
        except Exception:
            pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        _running_tasks.pop(f"{task_id}:{stage_num}", None)
        db.close()


# =============================================================================
# Cost summary generator
# =============================================================================

_STAGE_DISPLAY_NAMES = {
    1: "Requirements Analysis",
    2: "Tools & Technology Selection",
    3: "Cloud & Infrastructure Planning",
    4: "Implementation Plan",
    5: "Architecture Design",
    6: "Execution Strategy",
    7: "Proposal Compilation",
}


def _generate_cost_summary(task_id: str, work_dir: str, stages, cost_repo) -> str:
    """Generate a formatted cost_summary.md file with per-stage and total cost breakdown."""
    lines: List[str] = []
    lines.append("# RFP Proposal — Cost Summary")
    lines.append("")
    lines.append(f"**Task ID:** `{task_id}`")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table header
    lines.append("## Per-Stage Cost Breakdown")
    lines.append("")
    lines.append("| # | Stage | Model | Prompt Tokens | Completion Tokens | Total Tokens | Cost (USD) |")
    lines.append("|---|-------|-------|--------------|-------------------|-------------|------------|")

    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    total_cost = 0.0

    sorted_stages = sorted(stages, key=lambda s: s.stage_number)
    for stage in sorted_stages:
        num = stage.stage_number
        display = _STAGE_DISPLAY_NAMES.get(num, stage.stage_name or f"Stage {num}")
        cost_info = {}
        model_name = "—"
        if stage.output_data:
            cost_info = stage.output_data.get("cost", {})
            artifacts = stage.output_data.get("artifacts", {})
            model_name = artifacts.get("model", "—")

        pt = cost_info.get("prompt_tokens", 0)
        ct = cost_info.get("completion_tokens", 0)
        tt = pt + ct
        cu = cost_info.get("cost_usd", 0.0)

        total_prompt += pt
        total_completion += ct
        total_tokens += tt
        total_cost += cu

        lines.append(
            f"| {num} | {display} | {model_name} | "
            f"{pt:,} | {ct:,} | {tt:,} | ${cu:.4f} |"
        )

    # Separator + totals row
    lines.append(f"| | **TOTAL** | | **{total_prompt:,}** | **{total_completion:,}** | **{total_tokens:,}** | **${total_cost:.4f}** |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary section
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Prompt Tokens:** {total_prompt:,}")
    lines.append(f"- **Total Completion Tokens:** {total_completion:,}")
    lines.append(f"- **Total Tokens Used:** {total_tokens:,}")
    lines.append(f"- **Total Cost:** ${total_cost:.4f}")
    lines.append("")

    # Cross-check with DB cost records
    try:
        db_cost = cost_repo.get_task_total_cost(parent_run_id=task_id)
        if isinstance(db_cost, dict):
            db_total = db_cost.get("total_cost_usd", 0.0)
            db_tokens = db_cost.get("total_tokens", 0)
            if abs(db_total - total_cost) > 0.0001 or db_tokens != total_tokens:
                lines.append(f"> **Note:** Database totals — ${db_total:.4f} / {db_tokens:,} tokens")
                lines.append("")
    except Exception:
        pass

    content = "\n".join(lines)
    input_dir = os.path.join(work_dir, "input_files")
    os.makedirs(input_dir, exist_ok=True)
    summary_path = os.path.join(input_dir, "cost_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(content)
    return summary_path


# =============================================================================
# REST Endpoints
# =============================================================================

@router.post("/create", response_model=RfpCreateResponse)
async def create_rfp_task(request: RfpCreateRequest):
    """Create a new RFP proposal task with 7 pending stages."""
    task_id = str(uuid.uuid4())
    db = _get_db()

    try:
        # Create session using the global SessionManager (expects a db_factory callable)
        from services.session_manager import get_session_manager
        sm = get_session_manager()
        session_id = sm.create_session(
            mode="rfp-proposal",
            config={"task_id": task_id},
            name=f"RFP: {request.task[:60]}" if request.task else "RFP Proposal",
        )

        work_dir = _get_work_dir(task_id, session_id=session_id, base_work_dir=request.work_dir)
        os.makedirs(os.path.join(work_dir, "input_files"), exist_ok=True)

        # Save RFP context
        if request.rfp_context:
            ctx_path = os.path.join(work_dir, "input_files", "rfp_context.md")
            with open(ctx_path, "w", encoding="utf-8") as f:
                f.write(request.rfp_context)

        # Save RFP content
        if request.task:
            rfp_path = os.path.join(work_dir, "input_files", "rfp_input.md")
            with open(rfp_path, "w", encoding="utf-8") as f:
                f.write(request.task)

        # Create WorkflowRun
        from cmbagent.database.models import WorkflowRun
        run = WorkflowRun(
            id=task_id,
            session_id=session_id,
            mode="rfp-proposal",
            agent="phase_orchestrator",
            model=_get_default_rfp_model(),
            status="executing",
            task_description=request.task or "",
            started_at=datetime.now(timezone.utc),
            meta={
                "work_dir": work_dir,
                "rfp_context": request.rfp_context or "",
                "config": request.config or {},
                "session_id": session_id,
                "orchestration": "phase-based",
            },
        )
        db.add(run)
        db.commit()

        # Create 7 stages
        repo = _get_stage_repo(db, session_id=session_id)
        created_stages = []
        for sdef in STAGE_DEFS:
            stage = repo.create_stage(
                parent_run_id=task_id,
                stage_number=sdef["number"],
                stage_name=sdef["name"],
                status="pending",
                input_data={"task": request.task or "", "rfp_context": request.rfp_context or ""},
            )
            created_stages.append(stage)

        return RfpCreateResponse(
            task_id=task_id,
            work_dir=work_dir,
            stages=[_stage_to_response(s) for s in created_stages],
        )
    finally:
        db.close()


@router.patch("/{task_id}/description")
async def update_rfp_task_description(task_id: str, body: dict):
    """Update task description and context (used when auto-created task gets submitted)."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")

        task_text = body.get("task", "")
        rfp_context = body.get("rfp_context", "")

        run.task_description = task_text
        if run.meta is None:
            run.meta = {}
        # SQLAlchemy needs a new dict to detect JSON mutation
        updated_meta = dict(run.meta)
        updated_meta["rfp_context"] = rfp_context
        run.meta = updated_meta

        # Also save files to disk
        work_dir = run.meta.get("work_dir", "")
        if work_dir:
            input_dir = os.path.join(work_dir, "input_files")
            os.makedirs(input_dir, exist_ok=True)
            if task_text:
                with open(os.path.join(input_dir, "rfp_input.md"), "w", encoding="utf-8") as f:
                    f.write(task_text)
            if rfp_context:
                with open(os.path.join(input_dir, "rfp_context.md"), "w", encoding="utf-8") as f:
                    f.write(rfp_context)

        db.commit()
        return {"status": "updated", "task_id": task_id}
    finally:
        db.close()


@router.get("/recent", response_model=List[RfpRecentTaskResponse])
async def get_recent_rfp_tasks():
    """List incomplete RFP tasks for the resume flow."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        runs = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.mode == "rfp-proposal", WorkflowRun.status == "executing")
            .order_by(WorkflowRun.started_at.desc())
            .limit(10)
            .all()
        )

        results = []
        for run in runs:
            session_id = run.session_id
            repo = _get_stage_repo(db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=run.id)
            progress = repo.get_task_progress(parent_run_id=run.id)
            current = None
            for s in stages:
                if s.status in ("running", "pending", "failed"):
                    current = s.stage_number
                    break

            pct = progress.get("progress_percent", 0) if isinstance(progress, dict) else 0

            # Skip fully-completed tasks
            if pct >= 100:
                continue

            results.append(RfpRecentTaskResponse(
                task_id=run.id,
                task=run.task_description or "",
                status=run.status,
                created_at=run.started_at.isoformat() if run.started_at else None,
                current_stage=current,
                progress_percent=pct,
            ))

        return results
    finally:
        db.close()


@router.get("/{task_id}", response_model=RfpTaskStateResponse)
async def get_rfp_task_state(task_id: str):
    """Get full task state including all stages, progress, and cost."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = run.session_id
        repo = _get_stage_repo(db, session_id=session_id)
        cost_repo = _get_cost_repo(db, session_id=session_id)

        stages = repo.list_stages(parent_run_id=task_id)
        progress = repo.get_task_progress(parent_run_id=task_id)
        total_cost_data = cost_repo.get_task_total_cost(parent_run_id=task_id)

        # Extract scalar values from dict responses
        if isinstance(total_cost_data, dict):
            total_cost = total_cost_data.get("total_cost_usd", 0.0)
        else:
            total_cost = total_cost_data or 0.0
        pct = progress.get("progress_percent", 0) if isinstance(progress, dict) else 0

        # Determine current stage
        current = None
        for s in stages:
            if s.status in ("running", "pending", "failed"):
                current = s.stage_number
                break

        return RfpTaskStateResponse(
            task_id=task_id,
            task=run.task_description or "",
            status=run.status,
            work_dir=run.meta.get("work_dir") if run.meta else None,
            created_at=run.started_at.isoformat() if run.started_at else None,
            stages=[_stage_to_response(s) for s in stages],
            current_stage=current,
            progress_percent=pct,
            total_cost_usd=total_cost,
        )
    finally:
        db.close()


@router.post("/{task_id}/stages/{stage_num}/execute")
async def execute_rfp_stage(task_id: str, stage_num: int, request: RfpExecuteRequest = None):
    """Execute a single RFP stage in the background."""
    if stage_num < 1 or stage_num > 7:
        raise HTTPException(status_code=400, detail="stage_num must be 1-7")

    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = run.session_id
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)

        # Validate: all prior stages must be completed
        for s in stages:
            if s.stage_number < stage_num and s.status != "completed":
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage {s.stage_number} ({s.stage_name}) must be completed first",
                )

        # Validate: this stage must not be running
        target = next((s for s in stages if s.stage_number == stage_num), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")
        if target.status == "running":
            # Allow retry if the background task is no longer alive (stale from a crashed server)
            bg_key = f"{task_id}:{stage_num}"
            bg_task = _running_tasks.get(bg_key)
            if bg_task and not bg_task.done():
                raise HTTPException(status_code=409, detail="Stage is already running")
            # Stale running state — reset so we can re-execute
            _running_tasks.pop(bg_key, None)
            repo.update_stage_status(target.id, status="pending")

        # Mark stage as running
        repo.update_stage_status(target.id, status="running")

        # Build shared state from prior stages
        shared_state = build_shared_state(task_id, stage_num, db, session_id=session_id)

        work_dir = run.meta.get("work_dir") if run.meta else _get_work_dir(task_id, session_id)
        rfp_content = run.task_description or ""
        rfp_context = run.meta.get("rfp_context", "") if run.meta else ""

        # Enhance with file context
        file_ctx = _build_rfp_context(work_dir)
        if file_ctx:
            rfp_context = (rfp_context or "") + "\n" + file_ctx

        config_overrides = request.config_overrides if request else None

        # Launch background task
        task = asyncio.create_task(
            _run_rfp_stage(
                task_id=task_id,
                stage_num=stage_num,
                work_dir=work_dir,
                rfp_content=rfp_content,
                rfp_context=rfp_context,
                shared_state=shared_state,
                config_overrides=config_overrides,
                session_id=session_id,
            )
        )
        _running_tasks[f"{task_id}:{stage_num}"] = task

        return {"status": "executing", "stage_num": stage_num, "task_id": task_id}
    finally:
        db.close()


@router.get("/{task_id}/stages/{stage_num}/content", response_model=RfpStageContentResponse)
async def get_rfp_stage_content(task_id: str, stage_num: int):
    """Get the output content for a stage."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)

        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        # Get content from shared state
        content = None
        shared_state = None
        stage_def = STAGE_DEFS[stage_num - 1]

        if stage.output_data and "shared" in stage.output_data:
            shared_state = stage.output_data["shared"]
            shared_key = stage_def.get("shared_key")
            if shared_key and shared_key in shared_state:
                content = shared_state[shared_key]

        # Fallback: read from file
        if not content and stage_def.get("file"):
            from cmbagent.database.models import WorkflowRun
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            if run and run.meta:
                work_dir = run.meta.get("work_dir", "")
                file_path = os.path.join(work_dir, "input_files", stage_def["file"])
                if os.path.isfile(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

        return RfpStageContentResponse(
            stage_number=stage.stage_number,
            stage_name=stage.stage_name,
            status=stage.status,
            content=content,
            shared_state=shared_state,
            output_files=stage.output_files if hasattr(stage, 'output_files') and stage.output_files else None,
        )
    finally:
        db.close()


@router.put("/{task_id}/stages/{stage_num}/content")
async def update_rfp_stage_content(task_id: str, stage_num: int, request: RfpContentUpdateRequest):
    """Save user edits to a stage's content."""
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        stage = next((s for s in stages if s.stage_number == stage_num), None)

        if not stage:
            raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")

        # Update shared state in DB
        output_data = stage.output_data or {"shared": {}, "artifacts": {}}
        if "shared" not in output_data:
            output_data["shared"] = {}
        output_data["shared"][request.field] = request.content
        repo.update_stage_status(stage.id, status=stage.status, output_data=output_data)

        # Also write to file
        stage_def = STAGE_DEFS[stage_num - 1]
        if stage_def.get("file"):
            from cmbagent.database.models import WorkflowRun
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            if run and run.meta:
                work_dir = run.meta.get("work_dir", "")
                file_path = os.path.join(work_dir, "input_files", stage_def["file"])
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(request.content)

        return {"status": "saved", "field": request.field}
    finally:
        db.close()


@router.post("/{task_id}/stages/{stage_num}/refine", response_model=RfpRefineResponse)
async def refine_rfp_content(task_id: str, stage_num: int, request: RfpRefineRequest):
    """Use LLM to refine stage content based on user instruction."""
    from cmbagent.llm_provider import safe_completion
    from cmbagent.phases.rfp.token_utils import count_tokens, get_model_limits

    model = _get_default_rfp_model()

    # --- token capacity check ---
    max_ctx, _ = get_model_limits(model)
    system_msg = "You are a technical proposal consultant. Refine the following content based on the user's instruction. Return ONLY the refined markdown content, no explanations."
    user_msg = f"Current content:\n\n{request.content}\n\n---\n\nInstruction: {request.message}"

    prompt_tokens = count_tokens(system_msg, model) + count_tokens(user_msg, model) + 6
    available_for_output = max_ctx - prompt_tokens - 200
    max_comp = min(16384, max(available_for_output, 4096))

    # If content is too large, trim the content passed to refine but keep
    # the user instruction intact.  This avoids a context overflow crash.
    usable_for_content = int(max_ctx * 0.75) - count_tokens(system_msg, model) - count_tokens(request.message, model) - max_comp - 200
    content_tokens = count_tokens(request.content, model)

    if content_tokens > usable_for_content and usable_for_content > 2000:
        # Truncate content to fit — take start + end to preserve context
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(request.content)
        half = usable_for_content // 2
        trimmed_tokens = tokens[:half] + tokens[-half:]
        trimmed_content = enc.decode(trimmed_tokens)
        user_msg = f"Current content:\n\n{trimmed_content}\n\n---\n\nInstruction: {request.message}"
        # Recalculate
        prompt_tokens = count_tokens(system_msg, model) + count_tokens(user_msg, model) + 6
        available_for_output = max_ctx - prompt_tokens - 200
        max_comp = min(16384, max(available_for_output, 4096))

    def _call_refine():
        return safe_completion(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            model=model,
            temperature=0.7,
            max_tokens=max_comp,
        )

    refined = await asyncio.to_thread(_call_refine)

    refined = refined or request.content
    return RfpRefineResponse(
        refined_content=refined,
        message="Content refined successfully",
    )


@router.get("/{task_id}/stages/{stage_num}/console")
async def get_rfp_console(task_id: str, stage_num: int, since: int = 0):
    """Get console output lines for a running stage."""
    buf_key = f"{task_id}:{stage_num}"
    lines = _get_console_lines(buf_key, since_index=since)
    return {
        "lines": lines,
        "next_index": since + len(lines),
        "stage_num": stage_num,
    }


@router.post("/{task_id}/reset-from/{stage_num}")
async def reset_from_stage(task_id: str, stage_num: int):
    """Reset all stages from stage_num onwards back to pending."""
    if stage_num < 1 or stage_num > 7:
        raise HTTPException(status_code=400, detail="Invalid stage number")
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        repo = _get_stage_repo(db, session_id=session_id)
        work_dir = _get_work_dir(task_id, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        reset_count = 0
        for stage in stages:
            if stage.stage_number >= stage_num:
                stage.status = "pending"
                stage.started_at = None
                stage.completed_at = None
                stage.error_message = None
                stage.result = None
                # Remove the generated file
                stage_def = next((s for s in STAGE_DEFS if s["number"] == stage.stage_number), None)
                if stage_def and stage_def["file"]:
                    fpath = os.path.join(work_dir, "input_files", stage_def["file"])
                    if os.path.isfile(fpath):
                        os.remove(fpath)
                reset_count += 1
        db.commit()
        return {"reset_count": reset_count, "from_stage": stage_num}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{task_id}/download/{filename}")
async def download_rfp_artifact(task_id: str, filename: str):
    """Download a generated RFP artifact file."""
    import mimetypes
    # Only allow known artifact filenames
    allowed = {s["file"] for s in STAGE_DEFS if s["file"]}
    allowed.add("proposal.md")
    allowed.add("rfp_context.md")
    allowed.add("cost_summary.md")
    if filename not in allowed:
        raise HTTPException(status_code=400, detail="Invalid filename")
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        work_dir = _get_work_dir(task_id, session_id=session_id)
        file_path = os.path.join(work_dir, "input_files", filename)
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return FileResponse(
            file_path,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


@router.get("/{task_id}/download-pdf")
async def download_rfp_pdf(task_id: str, inline: bool = False):
    """Generate and download the final proposal as a professional PDF.
    
    Pass ?inline=true to serve for in-browser preview (Content-Disposition: inline).
    """
    db = _get_db()
    try:
        session_id = _get_session_id_for_task(task_id, db)
        work_dir = _get_work_dir(task_id, session_id=session_id)
        md_path = os.path.join(work_dir, "input_files", "proposal.md")
        if not os.path.isfile(md_path):
            raise HTTPException(status_code=404, detail="Proposal not generated yet")

        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        pdf_path = os.path.join(work_dir, "input_files", "proposal.pdf")

        import markdown as md_lib
        from weasyprint import HTML

        html_body = md_lib.markdown(
            md_content,
            extensions=["tables", "fenced_code", "toc", "nl2br"],
        )

        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2cm;
    @bottom-center {{
      content: "Page " counter(page) " of " counter(pages);
      font-size: 9px;
      color: #888;
    }}
  }}
  body {{
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
    background-color: #ffffff;
  }}
  h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 8px; page-break-after: avoid; }}
  h2 {{ color: #2c5282; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-top: 1.5em; page-break-after: avoid; }}
  h3 {{ color: #2d3748; margin-top: 1.2em; page-break-after: avoid; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; page-break-inside: avoid; }}
  th {{ background-color: #1a365d; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 6px 12px; border: 1px solid #e2e8f0; }}
  tr:nth-child(even) {{ background-color: #f7fafc; }}
  code {{ background-color: #f7fafc; padding: 2px 4px; border-radius: 3px; font-size: 9.5pt; }}
  pre {{ background-color: #f7fafc; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 9pt; }}
  strong {{ color: #1a365d; }}
  ul, ol {{ margin-left: 1.5em; }}
  li {{ margin-bottom: 0.3em; }}
  blockquote {{ border-left: 3px solid #2c5282; padding-left: 1em; color: #4a5568; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

        HTML(string=full_html).write_pdf(pdf_path)

        disposition = 'inline; filename="RFP_Proposal.pdf"' if inline else 'attachment; filename="RFP_Proposal.pdf"'
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": disposition},
        )
    finally:
        db.close()


# =============================================================================
# Stop a running task
# =============================================================================
@router.post("/{task_id}/stop")
async def stop_rfp_task(task_id: str):
    """Stop a running RFP task.

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


@router.delete("/{task_id}")
async def delete_rfp_task(task_id: str):
    """Delete an RFP task and its work directory."""
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Task not found")

        # Delete work directory
        if run.meta and "work_dir" in run.meta:
            import shutil
            work_dir = run.meta["work_dir"]
            if os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)

        # Delete DB records (cascade handles stages)
        db.delete(run)
        db.commit()
        return {"status": "deleted", "task_id": task_id}
    finally:
        db.close()
