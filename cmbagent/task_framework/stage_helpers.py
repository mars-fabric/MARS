"""
Stage-specific helpers for Deepresearch stages 1-3.

Pure functions that handle prompt formatting, result extraction,
post-processing, file I/O, and output structuring for each stage.
Called directly from the router -- no Phase subclasses needed.
"""

import os
import re
import shutil
import logging
from typing import Any, Dict, List, Tuple

from cmbagent.task_framework.config import (
    INPUT_FILES, IDEA_FILE, METHOD_FILE, RESULTS_FILE, PLOTS_FOLDER,
)
from cmbagent.task_framework.utils import (
    get_task_result, create_work_dir, extract_clean_markdown,
)

logger = logging.getLogger(__name__)


# ─── Default model assignments (from original phase configs) ─────────────

IDEA_DEFAULTS = {
    "idea_maker_model": "gpt-4o",
    "idea_hater_model": "o3-mini",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

METHOD_DEFAULTS = {
    "researcher_model": "gpt-4.1",
    "planner_model": "gpt-4.1",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
}

EXPERIMENT_DEFAULTS = {
    "engineer_model": "gpt-4.1",
    "researcher_model": "o3-mini",
    "planner_model": "gpt-4o",
    "plan_reviewer_model": "o3-mini",
    "orchestration_model": "gpt-4.1",
    "formatter_model": "o3-mini",
    "involved_agents": ["engineer", "researcher"],
    "max_n_attempts": 10,
    "max_n_steps": 6,
    "restart_at_step": -1,
    "hardware_constraints": "",
}


# ═══════════════════════════════════════════════════════════════════════════
# Stage 1 — Idea Generation
# ═══════════════════════════════════════════════════════════════════════════

def build_idea_kwargs(
    data_description: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs dict for planning_and_control_context_carryover (idea stage).

    The returned dict includes 'task' as a key; the caller should pop it
    and pass it as the first positional argument.
    """
    from cmbagent.task_framework.prompts.deepresearch.idea import idea_planner_prompt

    cfg = {**IDEA_DEFAULTS, **(config_overrides or {})}
    idea_dir = create_work_dir(work_dir, "idea")

    return dict(
        task=data_description,
        n_plan_reviews=1,
        max_plan_steps=6,
        idea_maker_model=cfg["idea_maker_model"],
        idea_hater_model=cfg["idea_hater_model"],
        plan_instructions=idea_planner_prompt,
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        work_dir=str(idea_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="idea_generation",
        callbacks=callbacks,
    )


def extract_idea_result(results: dict) -> str:
    """Extract and post-process idea from chat_history.

    Tries ``idea_maker`` first (actual content agent), then
    ``idea_maker_nest`` (wrapper — usually has empty content).
    Falls back to scanning all idea-related agents for the longest
    non-empty message if the primary agents return nothing.
    """
    chat_history = results["chat_history"]

    # Try idea_maker first (actual content), then nest wrapper
    task_result = ""
    for agent_name in ("idea_maker", "idea_maker_nest"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: scan ALL messages from idea-related agents,
    # pick the longest non-empty content (likely the final refined idea)
    if not task_result:
        logger.warning("Primary idea extraction failed, scanning all idea-related messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and "idea_maker" in name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best
            logger.info("Recovered idea from broad scan, length=%d", len(best))

    if not task_result:
        # Log available agent names for debugging
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Idea extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "Neither 'idea_maker' nor 'idea_maker_nest' found with content in chat history. "
            f"Available agents: {list(set(agent_names))}"
        )

    logger.info("Extracted idea, length=%d", len(task_result))

    # Post-processing regex from original idea.py:82-84
    pattern = r'\*\*Ideas\*\*\s*\n- Idea 1:'
    replacement = "Project Idea:"
    return re.sub(pattern, replacement, task_result)


def save_idea(research_idea: str, work_dir: str) -> str:
    """Write idea.md to input_files/ and return the file path."""
    input_files_dir = os.path.join(str(work_dir), INPUT_FILES)
    os.makedirs(input_files_dir, exist_ok=True)
    idea_path = os.path.join(input_files_dir, IDEA_FILE)
    with open(idea_path, "w") as f:
        f.write(research_idea)
    logger.info("Saved idea to %s, length=%d", idea_path, len(research_idea))
    return idea_path


def build_idea_output(
    research_idea: str,
    data_description: str,
    idea_path: str,
    chat_history: list,
) -> dict:
    """Build the output_data dict for DB storage (idea stage)."""
    return {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
        },
        "artifacts": {
            "idea.md": idea_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2 — Method Development
# ═══════════════════════════════════════════════════════════════════════════

def build_method_kwargs(
    data_description: str,
    research_idea: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs dict for planning_and_control_context_carryover (method stage)."""
    from cmbagent.task_framework.prompts.deepresearch.method import (
        method_planner_prompt,
        method_researcher_prompt,
    )

    cfg = {**METHOD_DEFAULTS, **(config_overrides or {})}
    method_dir = create_work_dir(work_dir, "method")

    return dict(
        task=data_description,
        n_plan_reviews=1,
        max_n_attempts=4,
        max_plan_steps=4,
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=method_planner_prompt.format(research_idea=research_idea),
        researcher_instructions=method_researcher_prompt.format(research_idea=research_idea),
        work_dir=str(method_dir),
        api_keys=api_keys,
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="method_development",
        callbacks=callbacks,
    )


def extract_method_result(results: dict) -> str:
    """Extract and post-process methodology from chat_history.

    Tries ``researcher_response_formatter`` first; falls back to
    ``researcher`` if the formatter returned empty content.
    As a last resort, scans all messages for the longest non-empty
    content from any agent.
    """
    chat_history = results["chat_history"]

    task_result = ""
    for agent_name in ("researcher_response_formatter", "researcher"):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: scan ALL messages for longest non-empty content
    if not task_result:
        logger.warning("Primary method extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best
            logger.info("Recovered method result from broad scan, length=%d", len(best))

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Method extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "No agent found with content in chat history for methodology. "
            f"Available agents: {list(set(agent_names))}"
        )

    return extract_clean_markdown(task_result)


def save_method(methodology: str, work_dir: str) -> str:
    """Write methods.md to input_files/ and return the file path."""
    input_files_dir = os.path.join(str(work_dir), INPUT_FILES)
    os.makedirs(input_files_dir, exist_ok=True)
    methods_path = os.path.join(input_files_dir, METHOD_FILE)
    with open(methods_path, "w") as f:
        f.write(methodology)
    return methods_path


def build_method_output(
    research_idea: str,
    data_description: str,
    methodology: str,
    methods_path: str,
    chat_history: list,
) -> dict:
    """Build the output_data dict for DB storage (method stage)."""
    return {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
            "methodology": methodology,
        },
        "artifacts": {
            "methods.md": methods_path,
        },
        "chat_history": chat_history,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Stage 3 — Experiment Execution
# ═══════════════════════════════════════════════════════════════════════════

def build_experiment_kwargs(
    data_description: str,
    research_idea: str,
    methodology: str,
    work_dir: str,
    api_keys: dict | None = None,
    parent_run_id: str | None = None,
    config_overrides: dict | None = None,
    callbacks=None,
) -> dict:
    """Build kwargs dict for planning_and_control_context_carryover (experiment stage)."""
    from cmbagent.task_framework.prompts.deepresearch.experiment import (
        experiment_planner_prompt,
        experiment_engineer_prompt,
        experiment_researcher_prompt,
    )

    cfg = {**EXPERIMENT_DEFAULTS, **(config_overrides or {})}
    involved_agents = cfg["involved_agents"]
    involved_agents_str = ", ".join(involved_agents)
    experiment_dir = create_work_dir(work_dir, "experiment")

    return dict(
        task=data_description,
        n_plan_reviews=1,
        max_n_attempts=cfg["max_n_attempts"],
        max_plan_steps=cfg["max_n_steps"],
        max_rounds_control=500,
        engineer_model=cfg["engineer_model"],
        researcher_model=cfg["researcher_model"],
        planner_model=cfg["planner_model"],
        plan_reviewer_model=cfg["plan_reviewer_model"],
        plan_instructions=experiment_planner_prompt.format(
            research_idea=research_idea,
            methodology=methodology,
            involved_agents_str=involved_agents_str,
        ),
        researcher_instructions=experiment_researcher_prompt.format(
            research_idea=research_idea,
            methodology=methodology,
        ),
        engineer_instructions=experiment_engineer_prompt.format(
            research_idea=research_idea,
            methodology=methodology,
        ),
        work_dir=str(experiment_dir),
        api_keys=api_keys,
        restart_at_step=cfg["restart_at_step"],
        hardware_constraints=cfg["hardware_constraints"],
        default_llm_model=cfg["orchestration_model"],
        default_formatter_model=cfg["formatter_model"],
        parent_run_id=parent_run_id,
        stage_name="experiment_execution",
        callbacks=callbacks,
    )


def extract_experiment_result(results: dict) -> Tuple[str, List[str]]:
    """Extract experiment results text and plot paths.

    Tries ``researcher_response_formatter`` first; falls back to
    ``researcher``, then ``engineer_response_formatter``, then
    ``engineer`` if earlier agents returned empty content.
    As a last resort, scans all messages for the longest non-empty
    content from any response-formatter or execution agent.

    Returns:
        (experiment_results_markdown, plot_paths_list)
    """
    chat_history = results["chat_history"]
    final_context = results["final_context"]

    task_result = ""
    for agent_name in (
        "researcher_response_formatter",
        "researcher",
        "engineer_response_formatter",
        "engineer",
        "executor_response_formatter",
    ):
        try:
            candidate = get_task_result(chat_history, agent_name)
            if candidate and candidate.strip():
                task_result = candidate
                break
        except ValueError:
            continue

    # Broader fallback: scan ALL messages for the longest non-empty content
    if not task_result:
        logger.warning("Primary experiment extraction failed, scanning all messages")
        best = ""
        for msg in chat_history:
            name = msg.get("name", "")
            content = msg.get("content", "")
            if name and content and content.strip():
                if len(content) > len(best):
                    best = content
        if best:
            task_result = best
            logger.info("Recovered experiment result from broad scan, length=%d", len(best))

    if not task_result:
        agent_names = [msg.get("name", "<no name>") for msg in chat_history if msg.get("name")]
        logger.error(
            "Experiment extraction failed. Agents in chat_history: %s",
            list(set(agent_names)),
        )
        raise ValueError(
            "No agent found with content in chat history for experiment results. "
            f"Available agents: {list(set(agent_names))}"
        )

    experiment_results = extract_clean_markdown(task_result)
    plot_paths = final_context.get("displayed_images", [])
    return experiment_results, plot_paths


def save_experiment(
    experiment_results: str,
    plot_paths: List[str],
    work_dir: str,
) -> Tuple[str, str, List[str]]:
    """Write results.md, move plots to input_files/plots/.

    Returns:
        (results_path, plots_dir, final_plot_paths)
    """
    input_files_dir = os.path.join(str(work_dir), INPUT_FILES)
    os.makedirs(input_files_dir, exist_ok=True)

    # Write results markdown
    results_path = os.path.join(input_files_dir, RESULTS_FILE)
    with open(results_path, "w") as f:
        f.write(experiment_results)

    # Prepare plots directory
    plots_dir = os.path.join(input_files_dir, PLOTS_FOLDER)
    os.makedirs(plots_dir, exist_ok=True)

    # Clear existing plots
    for file in os.listdir(plots_dir):
        file_path = os.path.join(plots_dir, file)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Move new plots
    for plot_path in plot_paths:
        if os.path.exists(plot_path):
            shutil.move(plot_path, plots_dir)

    # Build final plot paths list
    final_plot_paths = []
    if os.path.exists(plots_dir):
        final_plot_paths = [
            os.path.join(plots_dir, f)
            for f in os.listdir(plots_dir)
            if os.path.isfile(os.path.join(plots_dir, f))
        ]

    return results_path, plots_dir, final_plot_paths


def build_experiment_output(
    research_idea: str,
    data_description: str,
    methodology: str,
    experiment_results: str,
    final_plot_paths: List[str],
    results_path: str,
    plots_dir: str,
    chat_history: list,
) -> dict:
    """Build the output_data dict for DB storage (experiment stage)."""
    return {
        "shared": {
            "research_idea": research_idea,
            "data_description": data_description,
            "methodology": methodology,
            "results": experiment_results,
            "plot_paths": final_plot_paths,
        },
        "artifacts": {
            "results.md": results_path,
            "plots/": plots_dir,
        },
        "chat_history": chat_history,
    }
