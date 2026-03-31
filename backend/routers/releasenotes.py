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
    {"number": 3, "name": "release_notes",    "shared_key": "release_notes", "file": "release_notes.md"},
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
        return ReleaseNotesCreateResponse(task_id=task_id, work_dir=work_dir, stages=stage_responses)
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
    sdef = STAGE_DEFS[stage_num - 1]
    buf_key = f"{task_id}:{stage_num}"
    with _console_lock:
        _console_buffers[buf_key] = [f"Starting {sdef['name']}..."]

    try:
        if stage_num == 1:
            output_data = await _run_collect_and_diff(shared_state, work_dir, buf_key)
        elif stage_num == 2:
            output_data = await _run_analysis_stage(sdef, shared_state, work_dir, buf_key, config_overrides)
        elif stage_num == 3:
            output_data = await _run_agent_stage(stage_num, sdef, shared_state, work_dir, buf_key, config_overrides)
        elif stage_num == 4:
            output_data = await _run_migration(shared_state, work_dir, buf_key, config_overrides)
        elif stage_num == 5:
            output_data = await _run_package(task_id, shared_state, buf_key)

        db = _get_db()
        try:
            repo = _get_stage_repo(db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "completed", output_data=output_data)
                with _console_lock:
                    _console_buffers.setdefault(buf_key, []).append(
                        f"Stage {stage_num} ({sdef['name']}) completed successfully."
                    )
            db.commit()
        finally:
            db.close()

    except Exception as e:
        logger.error("release_notes_stage_exception task=%s stage=%d error=%s", task_id, stage_num, e, exc_info=True)
        with _console_lock:
            _console_buffers.setdefault(buf_key, []).append(f"Error: {e}")
        db = _get_db()
        try:
            repo = _get_stage_repo(db, session_id=session_id)
            stages = repo.list_stages(parent_run_id=task_id)
            stage = next((s for s in stages if s.stage_number == stage_num), None)
            if stage:
                repo.update_stage_status(stage.id, "failed", error_message=str(e))
            db.commit()
        finally:
            db.close()
    finally:
        _running_tasks.pop(f"{task_id}:{stage_num}", None)


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


def _call_llm_sync(prompt: str, config_overrides: Dict[str, Any], max_completion_tokens: int = 8192) -> str:
    """Synchronous LLM call for use in thread pools."""
    from cmbagent.llm_provider import safe_completion
    model = config_overrides.get("model", "gpt-4o")
    return safe_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.4,
        max_tokens=max_completion_tokens,
    )


async def _run_analysis_stage(
    sdef: dict, shared_state: Dict[str, Any],
    work_dir: str, buf_key: str, config_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 2: Produce 3 documents — base branch summary, head branch summary, and comparison."""
    import concurrent.futures

    repo_name = shared_state.get("repo_name", "repository")
    base = shared_state.get("base_branch", "")
    head = shared_state.get("head_branch", "")
    diff_context = shared_state.get("diff_context", "")
    categorised_files = shared_state.get("categorised_files", {})
    commits = shared_state.get("commits", [])
    diff_stat = shared_state.get("diff_stat", "")

    # --- Prompt 1: Base branch (last release) document ---
    prompt_base = (
        f"# Last Release Branch Summary — {repo_name}\n\n"
        f"Branch: `{base}`\n\n"
        f"Below is the diff context comparing `{base}` → `{head}`.\n\n"
        f"{diff_context}\n\n"
        "## Task\n"
        f"From the diff context above, produce a comprehensive document describing the **last release (`{base}`)** state.\n\n"
        "Include these sections:\n"
        "1. **Release Overview** — High-level summary of what was in this release\n"
        "2. **Features & Capabilities** — All features present as of this branch\n"
        "3. **Architecture & Components** — Key components, services, dependencies\n"
        "4. **API Surface** — Endpoints, interfaces, and contracts\n"
        "5. **Configuration** — Environment variables, config files, settings\n"
        "6. **Database Schema** — Tables, migrations, data models\n"
        "7. **Infrastructure** — Deployment, CI/CD, containers, cloud resources\n"
        "8. **Known Limitations** — Known issues, technical debt\n\n"
        "Output in clean Markdown. Focus on what EXISTS in the base branch before the new changes."
    )

    # --- Prompt 2: Head branch (current release) document ---
    prompt_head = (
        f"# Current Release Branch Summary — {repo_name}\n\n"
        f"Branch: `{head}`\n\n"
        f"Below is the diff context comparing `{base}` → `{head}`.\n\n"
        f"{diff_context}\n\n"
        "## Task\n"
        f"From the diff context above, produce a comprehensive document describing the **current release (`{head}`)** with all new changes included.\n\n"
        "Include these sections:\n"
        "1. **Release Overview** — High-level summary of this new release\n"
        "2. **New Features & Enhancements** — Everything new or improved\n"
        "3. **Architecture & Components** — Updated components, new services, changed dependencies\n"
        "4. **API Surface** — New/changed endpoints, interfaces, breaking changes\n"
        "5. **Configuration** — New/changed env vars, config files, settings\n"
        "6. **Database Schema** — New tables, migrations, schema changes\n"
        "7. **Infrastructure** — Deployment changes, new containers, cloud changes\n"
        "8. **Bug Fixes** — Issues resolved in this release\n"
        "9. **Known Limitations** — Remaining issues, new technical debt\n\n"
        "Output in clean Markdown. Describe the COMPLETE state of the head branch."
    )

    # --- Prompt 3: Detailed comparison ---
    prompt_comparison = (
        f"# Detailed Comparison — {repo_name}\n\n"
        f"Comparing `{base}` (last release) → `{head}` (current release)\n\n"
        f"{diff_context}\n\n"
        "## Task\n"
        "Produce a **detailed comparison report** between the last release and current release.\n\n"
        "Include these sections:\n"
        "1. **Executive Summary** — One-paragraph overview of all changes\n"
        "2. **New Features** — Features added since last release (with file references)\n"
        "3. **Modified Features** — Existing features that were changed (before vs after)\n"
        "4. **Removed/Deprecated** — Anything removed or deprecated\n"
        "5. **Breaking Changes** — Changes that may break existing integrations\n"
        "6. **API Changes** — New, modified, and removed endpoints (with request/response differences)\n"
        "7. **Database Changes** — Schema migrations, new tables, altered columns\n"
        "8. **Configuration Changes** — New/changed/removed config options\n"
        "9. **Infrastructure Changes** — Deployment, CI/CD, container changes\n"
        "10. **Performance Impact** — Any performance-related changes\n"
        "11. **Security Changes** — Security fixes, new auth mechanisms\n"
        "12. **Migration Guide** — Step-by-step instructions to migrate from last release to current\n"
        "13. **Risk Assessment** — High/Medium/Low risk items\n\n"
        f"Reference commit SHAs and file paths where applicable.\n"
        "Output in clean Markdown with clear section headers."
    )

    doc_keys = sdef["doc_keys"]
    doc_files = sdef["doc_files"]
    prompts = [prompt_base, prompt_head, prompt_comparison]
    labels = [f"Base Branch ({base})", f"Head Branch ({head})", "Comparison"]

    results: Dict[str, str] = {}
    artifacts: Dict[str, str] = {}
    input_dir = os.path.join(work_dir, "input_files")
    os.makedirs(input_dir, exist_ok=True)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = _ConsoleCapture(buf_key, original_stdout)
        sys.stderr = _ConsoleCapture(buf_key, original_stderr)
        loop = asyncio.get_event_loop()

        for i, (prompt, key, fname, label) in enumerate(zip(prompts, doc_keys, doc_files, labels)):
            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Generating document {i+1}/3: {label} ({len(prompt)} chars prompt)..."
                )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                text = await loop.run_in_executor(
                    executor, _call_llm_sync, prompt, config_overrides, 8192
                )

            file_path = os.path.join(input_dir, fname)
            with open(file_path, "w") as f:
                f.write(text)

            results[key] = text
            artifacts[key] = file_path

            with _console_lock:
                _console_buffers.setdefault(buf_key, []).append(
                    f"Document {i+1}/3 ({label}) complete — {len(text)} chars, saved to {fname}"
                )
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr

    return {
        "shared": results,
        "artifacts": artifacts,
        "documents": [
            {"key": k, "file": f, "label": l}
            for k, f, l in zip(doc_keys, doc_files, labels)
        ],
    }


async def _run_agent_stage(
    stage_num: int, sdef: dict, shared_state: Dict[str, Any],
    work_dir: str, buf_key: str, config_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """Stage 3: Agent-powered release notes (LLM call with full context carryover)."""
    import concurrent.futures

    repo_name = shared_state.get("repo_name", "repository")
    base = shared_state.get("base_branch", "")
    head = shared_state.get("head_branch", "")
    diff_context = shared_state.get("diff_context", "")

    analysis_comparison = shared_state.get("analysis_comparison", "")
    analysis_base = shared_state.get("analysis_base", "")
    analysis_head = shared_state.get("analysis_head", "")
    extra = shared_state.get("extra_instructions", "")

    prompt = (
        f"# Release Notes — {repo_name}\nComparing `{base}` → `{head}`\n\n"
        f"{diff_context}\n\n"
    )
    if analysis_comparison:
        prompt += f"## Comparison Analysis\n{analysis_comparison}\n\n"
    if analysis_base:
        prompt += f"## Base Branch Analysis\n{analysis_base}\n\n"
    if analysis_head:
        prompt += f"## Head Branch Analysis\n{analysis_head}\n\n"
    if extra:
        prompt += f"## Additional Instructions\n{extra}\n\n"
    prompt += (
        "## Task\nProduce **TWO** documents:\n\n"
        "### Document 1: Commercial Release Notes\n"
        "Audience: end-users. Sections: What's New, Improvements, Bug Fixes, Known Issues.\n\n"
        "### Document 2: Developer Release Notes\n"
        "Audience: engineers. Sections: Overview, New Features, Bug Fixes, "
        "Breaking Changes, Migration Notes, Impact Analysis, Infrastructure Changes.\n"
        "Reference commit SHAs and file paths.\n\n"
        "Output both in Markdown, clearly separated."
    )

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Stage {stage_num} prompt built ({len(prompt)} chars), executing agent..."
        )

    def _call_llm():
        return _call_llm_sync(prompt, config_overrides)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = _ConsoleCapture(buf_key, original_stdout)
        sys.stderr = _ConsoleCapture(buf_key, original_stderr)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result_text = await loop.run_in_executor(executor, _call_llm)
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr

    file_path = os.path.join(work_dir, "input_files", sdef["file"])
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(result_text)

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Agent produced {len(result_text)} chars, saved to {sdef['file']}"
        )

    return {"shared": {sdef["shared_key"]: result_text}, "artifacts": {sdef["shared_key"]: file_path}}


async def _run_migration(shared_state: Dict[str, Any], work_dir: str, buf_key: str, config_overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 4: Generate migration script using LLM based on release notes and diff context."""
    import concurrent.futures

    migration_type = config_overrides.get("migration_type", "database")
    extra_instructions = config_overrides.get("extra_instructions", "")

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Generating {migration_type} migration script..."
        )

    repo_name = shared_state.get("repo_name", "repository")
    base = shared_state.get("base_branch", "")
    head = shared_state.get("head_branch", "")
    diff_context = shared_state.get("diff_context", "")
    release_notes = shared_state.get("release_notes", "")
    analysis_comparison = shared_state.get("analysis_comparison", "")

    prompt = (
        f"# Migration Script Generation — {repo_name}\n"
        f"Comparing `{base}` → `{head}`\n\n"
        f"## Migration Type: {migration_type}\n\n"
    )
    if diff_context:
        prompt += f"## Diff Context\n{diff_context}\n\n"
    if analysis_comparison:
        prompt += f"## Analysis\n{analysis_comparison}\n\n"
    if release_notes:
        prompt += f"## Release Notes\n{release_notes}\n\n"
    if extra_instructions:
        prompt += f"## Additional Instructions\n{extra_instructions}\n\n"

    prompt += (
        "## Task\n"
        "Based on the code changes above, generate a **migration script** that includes:\n\n"
    )

    if migration_type == "database":
        prompt += (
            "1. **Database Schema Changes**: CREATE TABLE, ALTER TABLE, ADD/DROP COLUMN, index changes\n"
            "2. **Data Migrations**: INSERT, UPDATE, DELETE for seed data or data transformations\n"
            "3. **Rollback Script**: A corresponding rollback/downgrade script\n"
            "4. **Pre-migration Checks**: Validation queries to run before migration\n"
            "5. **Post-migration Verification**: Queries to verify migration success\n\n"
            "Output valid SQL migration scripts in Markdown code blocks with clear section headers.\n"
        )
    elif migration_type == "api":
        prompt += (
            "1. **API Endpoint Changes**: New, modified, or deprecated endpoints\n"
            "2. **Request/Response Schema Changes**: Field additions, removals, type changes\n"
            "3. **Backward Compatibility Notes**: What breaks and how to handle it\n"
            "4. **Client Migration Guide**: Step-by-step instructions for API consumers\n"
            "5. **Versioning Strategy**: How the API version should be bumped\n\n"
            "Output a detailed migration guide in Markdown with code examples.\n"
        )
    elif migration_type == "infrastructure":
        prompt += (
            "1. **Infrastructure Changes**: New services, config changes, environment variables\n"
            "2. **Deployment Steps**: Ordered steps to deploy the changes\n"
            "3. **Rollback Plan**: Steps to revert if deployment fails\n"
            "4. **Dependency Updates**: Package/version changes required\n"
            "5. **Configuration Migration**: Config file changes needed\n\n"
            "Output a structured migration runbook in Markdown.\n"
        )
    else:
        prompt += (
            "1. **All Changes Requiring Migration**: Schema, API, config, infrastructure\n"
            "2. **Step-by-Step Migration Plan**: Ordered steps with dependencies\n"
            "3. **Rollback Plan**: How to revert each step\n"
            "4. **Verification Steps**: How to confirm migration success\n\n"
            "Output in Markdown with clear section headers and code blocks.\n"
        )

    def _call_llm_migration():
        return _call_llm_sync(prompt, config_overrides)

    original_stdout, original_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = _ConsoleCapture(buf_key, original_stdout)
        sys.stderr = _ConsoleCapture(buf_key, original_stderr)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result_text = await loop.run_in_executor(executor, _call_llm_migration)
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr

    file_path = os.path.join(work_dir, "input_files", "migration_script.md")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as fw:
        fw.write(result_text)

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append(
            f"Migration script generated ({len(result_text)} chars), saved to migration_script.md"
        )

    return {
        "shared": {"migration_script": result_text, "migration_type": migration_type},
        "artifacts": {"migration_script": file_path},
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
        "has_analysis": bool(shared_state.get("analysis")),
        "has_release_notes": bool(shared_state.get("release_notes")),
        "has_migration_script": bool(shared_state.get("migration_script")),
        "migration_type": shared_state.get("migration_type"),
    }

    with _console_lock:
        _console_buffers.setdefault(buf_key, []).append("Output package assembled.")

    return {"shared": {}, "package": package}


# ═══════════════════════════════════════════════════════════════════════════
#  GET /{task_id}
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{task_id}", response_model=ReleaseNotesTaskStateResponse)
async def get_task_state(task_id: str):
    db = _get_db()
    try:
        from cmbagent.database.models import WorkflowRun
        parent = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Task not found")

        session_id = parent.session_id
        repo = _get_stage_repo(db, session_id=session_id)
        stages = repo.list_stages(parent_run_id=task_id)
        meta = parent.meta or {}

        completed = sum(1 for s in stages if s.status == "completed")
        current = max((s.stage_number for s in stages if s.status in ("running", "completed")), default=1)

        return ReleaseNotesTaskStateResponse(
            task_id=task_id,
            repo_url=meta.get("repo_url", ""),
            repo_name=meta.get("repo_name", ""),
            base_branch=meta.get("base_branch", ""),
            head_branch=meta.get("head_branch", ""),
            status=parent.status or "executing",
            work_dir=meta.get("work_dir"),
            created_at=parent.started_at.isoformat() if parent.started_at else None,
            stages=[_stage_to_response(s) for s in stages],
            current_stage=current,
            progress_percent=(completed / len(STAGE_DEFS)) * 100,
        )
    finally:
        db.close()


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
    import concurrent.futures
    prompt = (
        "You are helping a software engineer refine release documentation.\n\n"
        f"--- CURRENT CONTENT ---\n{request.content}\n\n"
        f"--- USER REQUEST ---\n{request.message}\n\n"
        "Return ONLY the refined content, no preamble."
    )
    try:
        def _call():
            from cmbagent.llm_provider import safe_completion
            return safe_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4o",
                temperature=0.7,
                max_tokens=4096,
            )

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            refined = await loop.run_in_executor(executor, _call)
        return ReleaseNotesRefineResponse(refined_content=refined)
    except Exception as e:
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
