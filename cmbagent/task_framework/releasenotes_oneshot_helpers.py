"""
One-shot stage helpers for Release Notes pipeline stages 2-4.

Mirrors releasenotes_helpers.py but builds kwargs for cmbagent.one_shot()
instead of planning_and_control_context_carryover().

One-shot is faster (no planning overhead) but less structured — suited for
simpler analyses or when speed is preferred over multi-step reasoning.
"""

import os
import logging
from typing import Any, Dict

from cmbagent.task_framework.utils import create_work_dir
from cmbagent.task_framework.releasenotes_helpers import (
    extract_stage_result,
    save_stage_file,
    build_analysis_output,
    build_release_notes_output,
    build_migration_output,
)

logger = logging.getLogger(__name__)


# ─── Default model for one-shot stages ───────────────────────────────────

ONESHOT_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "default_llm_model": "gpt-4.1",
    "default_formatter_model": "o3-mini",
}


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — Analysis (3 documents via 3 one-shot calls)
# ═══════════════════════════════════════════════════════════════════════════

def build_analysis_base_oneshot_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    work_dir: str,
    api_keys: dict | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for one_shot() — base branch analysis."""
    from cmbagent.task_framework.prompts.releasenotes.oneshot import (
        oneshot_analysis_base_task,
    )

    cfg = {**ONESHOT_DEFAULTS, **(config_overrides or {})}
    sub_dir = create_work_dir(work_dir, "analysis_base")

    task = oneshot_analysis_base_task.format(
        repo_name=repo_name,
        base_branch=base_branch,
        head_branch=head_branch,
        diff_context=diff_context,
    )

    return dict(
        task=task,
        agent="researcher",
        max_rounds=15,
        max_n_attempts=2,
        researcher_model=cfg["researcher_model"],
        default_llm_model=cfg["default_llm_model"],
        default_formatter_model=cfg["default_formatter_model"],
        work_dir=str(sub_dir),
        api_keys=api_keys,
        clear_work_dir=False,
        callbacks=callbacks,
    )


def build_analysis_head_oneshot_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    work_dir: str,
    api_keys: dict | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for one_shot() — head branch analysis."""
    from cmbagent.task_framework.prompts.releasenotes.oneshot import (
        oneshot_analysis_head_task,
    )

    cfg = {**ONESHOT_DEFAULTS, **(config_overrides or {})}
    sub_dir = create_work_dir(work_dir, "analysis_head")

    task = oneshot_analysis_head_task.format(
        repo_name=repo_name,
        base_branch=base_branch,
        head_branch=head_branch,
        diff_context=diff_context,
    )

    return dict(
        task=task,
        agent="researcher",
        max_rounds=15,
        max_n_attempts=2,
        researcher_model=cfg["researcher_model"],
        default_llm_model=cfg["default_llm_model"],
        default_formatter_model=cfg["default_formatter_model"],
        work_dir=str(sub_dir),
        api_keys=api_keys,
        clear_work_dir=False,
        callbacks=callbacks,
    )


def build_analysis_comparison_oneshot_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    work_dir: str,
    api_keys: dict | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for one_shot() — comparison analysis."""
    from cmbagent.task_framework.prompts.releasenotes.oneshot import (
        oneshot_analysis_comparison_task,
    )

    cfg = {**ONESHOT_DEFAULTS, **(config_overrides or {})}
    sub_dir = create_work_dir(work_dir, "analysis_comparison")

    task = oneshot_analysis_comparison_task.format(
        repo_name=repo_name,
        base_branch=base_branch,
        head_branch=head_branch,
        diff_context=diff_context,
    )

    return dict(
        task=task,
        agent="researcher",
        max_rounds=15,
        max_n_attempts=2,
        researcher_model=cfg["researcher_model"],
        default_llm_model=cfg["default_llm_model"],
        default_formatter_model=cfg["default_formatter_model"],
        work_dir=str(sub_dir),
        api_keys=api_keys,
        clear_work_dir=False,
        callbacks=callbacks,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Release Notes (single one-shot call)
# ═══════════════════════════════════════════════════════════════════════════

def build_release_notes_oneshot_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    analysis_base: str,
    analysis_head: str,
    analysis_comparison: str,
    extra_instructions: str,
    work_dir: str,
    api_keys: dict | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for one_shot() — release notes generation."""
    from cmbagent.task_framework.prompts.releasenotes.oneshot import (
        oneshot_release_notes_task,
    )

    cfg = {**ONESHOT_DEFAULTS, **(config_overrides or {})}
    notes_dir = create_work_dir(work_dir, "release_notes")

    extra_section = ""
    if extra_instructions:
        extra_section = f"## Additional Instructions\n{extra_instructions}"

    task = oneshot_release_notes_task.format(
        repo_name=repo_name,
        base_branch=base_branch,
        head_branch=head_branch,
        diff_context=diff_context,
        analysis_base=analysis_base,
        analysis_head=analysis_head,
        analysis_comparison=analysis_comparison,
        extra_instructions_section=extra_section,
    )

    return dict(
        task=task,
        agent="researcher",
        max_rounds=15,
        max_n_attempts=2,
        researcher_model=cfg["researcher_model"],
        default_llm_model=cfg["default_llm_model"],
        default_formatter_model=cfg["default_formatter_model"],
        work_dir=str(notes_dir),
        api_keys=api_keys,
        clear_work_dir=False,
        callbacks=callbacks,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4 — Migration (single one-shot call)
# ═══════════════════════════════════════════════════════════════════════════

def build_migration_oneshot_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    analysis_comparison: str,
    release_notes: str,
    migration_type: str,
    extra_instructions: str,
    work_dir: str,
    api_keys: dict | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for one_shot() — migration script generation."""
    from cmbagent.task_framework.prompts.releasenotes.oneshot import (
        oneshot_migration_task,
    )

    cfg = {**ONESHOT_DEFAULTS, **(config_overrides or {})}
    migration_dir = create_work_dir(work_dir, "migration")

    extra_section = ""
    if extra_instructions:
        extra_section = f"## Additional Instructions\n{extra_instructions}"

    task = oneshot_migration_task.format(
        repo_name=repo_name,
        base_branch=base_branch,
        head_branch=head_branch,
        diff_context=diff_context,
        analysis_comparison=analysis_comparison,
        release_notes=release_notes,
        migration_type=migration_type,
        extra_instructions_section=extra_section,
    )

    return dict(
        task=task,
        agent="researcher",
        max_rounds=15,
        max_n_attempts=2,
        researcher_model=cfg["researcher_model"],
        default_llm_model=cfg["default_llm_model"],
        default_formatter_model=cfg["default_formatter_model"],
        work_dir=str(migration_dir),
        api_keys=api_keys,
        clear_work_dir=False,
        callbacks=callbacks,
    )
