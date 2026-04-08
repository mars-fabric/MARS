"""
Stage-specific helpers for Release Notes pipeline stages 2-4.

Stages:
  1 — Collect & Diff (no AI — git operations)
  2 — Analysis (AI — base/head/comparison documents)
  3 — Release Notes (AI — commercial + developer notes)
  4 — Migration (AI — migration scripts/runbook)
  5 — Package (no AI — bundle outputs)

Each AI stage (2, 3, 4) uses planning_and_control_context_carryover
with full callback infrastructure for cost tracking and observability.
"""

import os
import logging
from typing import Any, Dict, Optional

from cmbagent.task_framework.utils import (
    get_task_result, create_work_dir, extract_clean_markdown,
)

logger = logging.getLogger(__name__)


# ─── Default model assignments per stage ─────────────────────────────────

ANALYSIS_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

RELEASE_NOTES_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

MIGRATION_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4.1",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — Analysis (3 separate documents, 3 P&C calls)
# ═══════════════════════════════════════════════════════════════════════════

def _build_analysis_common(cfg, config_overrides):
    return {**ANALYSIS_DEFAULTS, **(config_overrides or {})}


def build_analysis_base_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (base branch analysis)."""
    from cmbagent.task_framework.prompts.releasenotes.analysis import (
        base_planner_prompt, base_researcher_prompt,
    )

    cfg = {**ANALYSIS_DEFAULTS, **(config_overrides or {})}
    sub_dir = create_work_dir(work_dir, "analysis_base")

    task_desc = (
        f"Produce a Last Release Branch Summary for the `{base_branch}` branch "
        f"of {repo_name}, documenting all features and architecture that existed "
        f"before the changes in `{head_branch}`."
    )

    fmt = dict(repo_name=repo_name, base_branch=base_branch,
               head_branch=head_branch, diff_context=diff_context)

    return dict(
        task=task_desc,
        n_plan_reviews=1, max_plan_steps=3, max_n_attempts=3,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=base_planner_prompt.format(**fmt),
        researcher_instructions=base_researcher_prompt.format(**fmt),
        work_dir=str(sub_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="analysis_base",
        callbacks=callbacks,
    )


def build_analysis_head_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (head branch analysis)."""
    from cmbagent.task_framework.prompts.releasenotes.analysis import (
        head_planner_prompt, head_researcher_prompt,
    )

    cfg = {**ANALYSIS_DEFAULTS, **(config_overrides or {})}
    sub_dir = create_work_dir(work_dir, "analysis_head")

    task_desc = (
        f"Produce a Current Release Branch Summary for the `{head_branch}` branch "
        f"of {repo_name}, documenting the complete state including all new changes."
    )

    fmt = dict(repo_name=repo_name, base_branch=base_branch,
               head_branch=head_branch, diff_context=diff_context)

    return dict(
        task=task_desc,
        n_plan_reviews=1, max_plan_steps=3, max_n_attempts=3,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=head_planner_prompt.format(**fmt),
        researcher_instructions=head_researcher_prompt.format(**fmt),
        work_dir=str(sub_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="analysis_head",
        callbacks=callbacks,
    )


def build_analysis_comparison_kwargs(
    repo_name: str,
    base_branch: str,
    head_branch: str,
    diff_context: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (comparison report)."""
    from cmbagent.task_framework.prompts.releasenotes.analysis import (
        comparison_planner_prompt, comparison_researcher_prompt,
    )

    cfg = {**ANALYSIS_DEFAULTS, **(config_overrides or {})}
    sub_dir = create_work_dir(work_dir, "analysis_comparison")

    task_desc = (
        f"Produce a Detailed Comparison Report for {repo_name} analysing all changes "
        f"between `{base_branch}` and `{head_branch}`, including breaking changes, "
        f"migration guide, and risk assessment."
    )

    fmt = dict(repo_name=repo_name, base_branch=base_branch,
               head_branch=head_branch, diff_context=diff_context)

    return dict(
        task=task_desc,
        n_plan_reviews=1, max_plan_steps=3, max_n_attempts=3,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=comparison_planner_prompt.format(**fmt),
        researcher_instructions=comparison_researcher_prompt.format(**fmt),
        work_dir=str(sub_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="analysis_comparison",
        callbacks=callbacks,
    )


def build_analysis_output(
    analysis_base: str,
    analysis_head: str,
    analysis_comparison: str,
    artifacts: Dict[str, str],
    chat_histories: Dict[str, list],
) -> dict:
    """Build output_data for DB storage (analysis stage — 3 documents)."""
    return {
        "shared": {
            "analysis_base": analysis_base,
            "analysis_head": analysis_head,
            "analysis_comparison": analysis_comparison,
        },
        "artifacts": artifacts,
        "documents": [
            {"key": "analysis_base", "file": "analysis_base.md", "label": "Base Branch"},
            {"key": "analysis_head", "file": "analysis_head.md", "label": "Head Branch"},
            {"key": "analysis_comparison", "file": "analysis_comparison.md", "label": "Comparison"},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Release Notes
# ═══════════════════════════════════════════════════════════════════════════

def build_release_notes_kwargs(
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
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (release notes stage)."""
    from cmbagent.task_framework.prompts.releasenotes.release_notes import (
        release_notes_planner_prompt,
        release_notes_researcher_prompt,
    )

    cfg = {**RELEASE_NOTES_DEFAULTS, **(config_overrides or {})}
    notes_dir = create_work_dir(work_dir, "release_notes")

    task_desc = (
        f"Generate comprehensive release notes for {repo_name} comparing "
        f"`{base_branch}` → `{head_branch}`. Produce two documents: "
        f"1) Commercial Release Notes for end-users, "
        f"2) Developer Release Notes for engineers."
    )

    extra_section = ""
    if extra_instructions:
        extra_section = f"## Additional Instructions\n{extra_instructions}"

    fmt_kwargs = dict(
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
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=6,
        max_n_attempts=3,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=release_notes_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=release_notes_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(notes_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="release_notes",
        callbacks=callbacks,
    )


def build_release_notes_output(
    release_notes_text: str,
    file_path: str,
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (release notes stage)."""
    return {
        "shared": {
            "release_notes": release_notes_text,
        },
        "artifacts": {
            "release_notes": file_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 4 — Migration
# ═══════════════════════════════════════════════════════════════════════════

def build_migration_kwargs(
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
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs for planning_and_control_context_carryover (migration stage)."""
    from cmbagent.task_framework.prompts.releasenotes.migration import (
        migration_planner_prompt,
        migration_researcher_prompt,
    )

    cfg = {**MIGRATION_DEFAULTS, **(config_overrides or {})}
    migration_dir = create_work_dir(work_dir, "migration")

    task_desc = (
        f"Generate a comprehensive {migration_type} migration script/runbook "
        f"for {repo_name} upgrading from `{base_branch}` to `{head_branch}`. "
        f"Include pre-migration checks, migration steps, rollback procedures, "
        f"and post-migration verification."
    )

    extra_section = ""
    if extra_instructions:
        extra_section = f"## Additional Instructions\n{extra_instructions}"

    fmt_kwargs = dict(
        repo_name=repo_name,
        base_branch=base_branch,
        head_branch=head_branch,
        migration_type=migration_type,
        diff_context=diff_context,
        analysis_comparison=analysis_comparison,
        release_notes=release_notes,
        extra_instructions_section=extra_section,
    )

    return dict(
        task=task_desc,
        n_plan_reviews=1,
        max_plan_steps=5,
        max_n_attempts=2,
        max_rounds_planning=20,
        max_rounds_control=30,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=migration_planner_prompt.format(**fmt_kwargs),
        researcher_instructions=migration_researcher_prompt.format(**fmt_kwargs),
        work_dir=str(migration_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="migration",
        callbacks=callbacks,
    )


def build_migration_output(
    migration_text: str,
    migration_type: str,
    file_path: str,
    chat_history: list,
) -> dict:
    """Build output_data for DB storage (migration stage)."""
    return {
        "shared": {
            "migration_script": migration_text,
            "migration_type": migration_type,
        },
        "artifacts": {
            "migration_script": file_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Shared utilities
# ═══════════════════════════════════════════════════════════════════════════

def extract_stage_result(results: dict) -> str:
    """Extract the report content from chat_history.

    Tries researcher and formatter agents first, then falls back to
    scanning all messages for the longest non-empty content.
    """
    chat_history = results["chat_history"]

    task_result = ""
    for agent_name in ("researcher", "researcher_response_formatter"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: pick longest non-empty message
    if not task_result:
        logger.warning("Primary extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        raise ValueError(
            f"No content found in chat history. Available agents: {list(set(agent_names))}"
        )

    return extract_clean_markdown(task_result)


def save_stage_file(content: str, work_dir: str, filename: str) -> str:
    """Write a stage output file to input_files/ and return the path."""
    input_dir = os.path.join(str(work_dir), "input_files")
    os.makedirs(input_dir, exist_ok=True)
    path = os.path.join(input_dir, filename)
    with open(path, "w") as f:
        f.write(content)
    return path
