"""
Control phase implementation for CMBAgent.

This module provides the ControlPhase class that executes
plan steps with context carryover between steps.

Uses PhaseExecutionManager for:
- Automatic callback invocation (step_start, step_complete, etc.)
- Database event logging
- DAG node management
- File tracking
- Pause/cancel handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import shutil
import time
import copy
import json
import pickle
import re
import traceback
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.execution_manager import PhaseExecutionManager


# ---------------------------------------------------------------------------
# Context-window guard: compress old step summaries to avoid exceeding the
# model's token limit when the accumulated previous_steps_execution_summary
# is injected into every agent's system prompt.
# ---------------------------------------------------------------------------
_MAX_SUMMARY_CHARS = 60_000       # ~15k tokens – safe headroom for 128k models
_RECENT_STEPS_FULL = 3            # keep the last N steps verbatim
_COMPRESSED_LINE_MAX_CHARS = 300  # max chars per compressed old-step line


def _truncate_step_summaries(step_summaries: list[str]) -> str:
    """Return a bounded version of the joined step summaries.

    * The most recent ``_RECENT_STEPS_FULL`` summaries are kept in full.
    * Older summaries are compressed to their first ``_COMPRESSED_LINE_MAX_CHARS``
      characters (roughly the first paragraph / heading).
    * If the result still exceeds ``_MAX_SUMMARY_CHARS`` it is hard-truncated
      from the front (oldest content removed first).
    """
    if not step_summaries:
        return "\n"

    n = len(step_summaries)
    parts: list[str] = []

    for idx, summary in enumerate(step_summaries):
        is_recent = idx >= n - _RECENT_STEPS_FULL
        if is_recent:
            parts.append(summary)
        else:
            # Keep only the heading / first meaningful line
            compressed = summary[:_COMPRESSED_LINE_MAX_CHARS].rstrip()
            if len(summary) > _COMPRESSED_LINE_MAX_CHARS:
                compressed += " ... [truncated]"
            parts.append(compressed)

    joined = "\n\n".join(parts)

    # Hard cap – drop oldest content so the newest context survives
    if len(joined) > _MAX_SUMMARY_CHARS:
        joined = (
            "[Earlier steps truncated to fit context window]\n\n"
            + joined[-_MAX_SUMMARY_CHARS:]
        )

    return joined


# Keys whose values are large but transient – safe to cap between steps.
_CONTEXT_LARGE_VALUE_CAP = 20_000   # chars (~5k tokens)
_CONTEXT_KEYS_TO_RESET = {
    # Chat artefacts that get rebuilt each step
    'chat_history', 'messages', 'last_message',
}


def _prune_carryover_context(ctx: dict) -> None:
    """In-place prune of a context dict to limit token growth between steps."""
    for key in _CONTEXT_KEYS_TO_RESET:
        if key in ctx:
            ctx[key] = None

    for key, value in list(ctx.items()):
        if key == 'previous_steps_execution_summary':
            continue  # already handled by _truncate_step_summaries
        if isinstance(value, str) and len(value) > _CONTEXT_LARGE_VALUE_CAP:
            ctx[key] = value[:_CONTEXT_LARGE_VALUE_CAP] + "\n... [value truncated for context window safety]"
        elif isinstance(value, list) and len(value) > 200:
            ctx[key] = value[-100:]  # keep only the most recent items


from cmbagent.utils import get_model_config, default_agents_llm_model


@dataclass
class ControlPhaseConfig(PhaseConfig):
    """
    Configuration for control/execution phase.

    Attributes:
        max_rounds: Maximum conversation rounds per step
        max_n_attempts: Maximum attempts per step before failure
        execute_all_steps: Whether to execute all plan steps
        step_number: Specific step to execute (if not all steps)
        hitl_enabled: Enable human-in-the-loop checkpoints
        hitl_after_each_step: Require approval after each step
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        engineer_instructions: Additional instructions for engineer
        researcher_instructions: Additional instructions for researcher
    """
    phase_type: str = "control"

    # Execution parameters
    max_rounds: int = 100
    max_n_attempts: int = 3

    # Step handling
    execute_all_steps: bool = True
    step_number: Optional[int] = None

    # HITL options
    hitl_enabled: bool = False
    hitl_after_each_step: bool = False

    # Model selection
    engineer_model: str = field(default_factory=lambda: default_agents_llm_model['engineer'])
    researcher_model: str = field(default_factory=lambda: default_agents_llm_model['researcher'])
    web_surfer_model: str = field(default_factory=lambda: default_agents_llm_model.get('web_surfer', default_agents_llm_model['researcher']))
    retrieve_assistant_model: str = field(default_factory=lambda: default_agents_llm_model.get('retrieve_assistant', default_agents_llm_model['researcher']))
    idea_maker_model: str = field(default_factory=lambda: default_agents_llm_model['idea_maker'])
    idea_hater_model: str = field(default_factory=lambda: default_agents_llm_model['idea_hater'])
    camb_context_model: str = field(default_factory=lambda: default_agents_llm_model['camb_context'])
    plot_judge_model: str = field(default_factory=lambda: default_agents_llm_model['plot_judge'])

    # Instructions
    engineer_instructions: str = ""
    researcher_instructions: str = ""


class ControlPhase(Phase):
    """
    Control phase that executes plan steps.

    Can execute:
    - All steps in sequence (execute_all_steps=True)
    - A single specific step (step_number=N)

    Input Context:
        - final_plan or plan_steps: The plan to execute
        - task: Original task
        - work_dir: Working directory

    Output Context:
        - step_results: Results from each step
        - final_context: Final context after all steps
        - step_summaries: Summary of each step
    """

    config_class = ControlPhaseConfig

    def __init__(self, config: ControlPhaseConfig = None):
        if config is None:
            config = ControlPhaseConfig()
        super().__init__(config)
        self.config: ControlPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "control"

    @property
    def display_name(self) -> str:
        return "Execution"

    def get_required_agents(self) -> List[str]:
        return ["control", "control_starter", "engineer", "researcher"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute the control phase.

        Runs plan steps with context carryover between steps.

        Args:
            context: Input context with plan and configuration

        Returns:
            PhaseResult with step results
        """
        from cmbagent.cmbagent import CMBAgent
        from cmbagent.workflows.utils import load_plan

        # Use PhaseExecutionManager for automatic callback/logging handling
        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        # Setup
        control_dir = os.path.join(context.work_dir, "control")
        os.makedirs(control_dir, exist_ok=True)

        context_dir = os.path.join(context.work_dir, "context")
        os.makedirs(context_dir, exist_ok=True)

        # Get plan from input (check multiple sources including preloaded plans)
        plan_steps = (
            # Check for preloaded plan in config params (from control_phases wrapper)
            self.config.params.get('preloaded_plan') or
            # Standard locations from previous phases
            context.input_data.get('final_plan') or
            context.shared_state.get('plan_steps') or
            context.shared_state.get('final_plan') or
            context.input_data.get('planning_context', {}).get('final_plan')
        )

        planning_context = (
            context.input_data.get('planning_context') or
            context.shared_state.get('planning_context') or
            {}
        )

        # If plan was preloaded, build a minimal planning context
        if self.config.params.get('preloaded_plan') and not planning_context:
            planning_context = {
                'final_plan': plan_steps,
                'number_of_steps_in_plan': len(plan_steps) if plan_steps else 0,
                'agent_for_sub_task': plan_steps[0].get('sub_task_agent') if plan_steps else None,
                'current_sub_task': plan_steps[0].get('sub_task') if plan_steps else None,
            }

        # Normalize plan_steps format - extract list from wrapper if needed
        if isinstance(plan_steps, dict) and 'sub_tasks' in plan_steps:
            plan_steps = plan_steps['sub_tasks']
        elif isinstance(plan_steps, str):
            # Try to load from JSON file
            try:
                plan_file = os.path.join(context.work_dir, "planning/final_plan.json")
                if os.path.exists(plan_file):
                    plan_steps = load_plan(plan_file).get('sub_tasks', [])
            except Exception:
                pass

        if not plan_steps:
            return manager.fail("No plan found in context. Run planning phase first.")

        # Extract human feedback from previous HITL phases
        hitl_feedback = context.shared_state.get('hitl_feedback', '')
        user_modifications = context.shared_state.get('user_modifications', {})
        
        # If we have feedback, inject it into the control agent's context
        feedback_context = ""
        if hitl_feedback:
            feedback_context = f"\n\n## Human Feedback from Previous Phase\n{hitl_feedback}\n\nPlease consider this feedback during execution.\n"
        
        if user_modifications:
            feedback_context += f"\n\n## Human Modifications\nThe plan was modified by the human. Modified elements: {user_modifications}\n"

        # Determine steps to execute
        if self.config.execute_all_steps:
            steps_to_run = range(1, len(plan_steps) + 1)
        else:
            steps_to_run = [self.config.step_number]

        # Get model configs
        engineer_config = get_model_config(self.config.engineer_model, context.api_keys)
        researcher_config = get_model_config(self.config.researcher_model, context.api_keys)
        web_surfer_config = get_model_config(self.config.web_surfer_model, context.api_keys)
        retrieve_assistant_config = get_model_config(self.config.retrieve_assistant_model, context.api_keys)
        idea_maker_config = get_model_config(self.config.idea_maker_model, context.api_keys)
        idea_hater_config = get_model_config(self.config.idea_hater_model, context.api_keys)
        camb_context_config = get_model_config(self.config.camb_context_model, context.api_keys)
        plot_judge_config = get_model_config(self.config.plot_judge_model, context.api_keys)

        step_results = []
        step_summaries = []
        all_chat_history = []

        # Initialize current context from planning output
        current_context = copy.deepcopy(planning_context)
        current_context['work_dir'] = control_dir

        try:
            for step in steps_to_run:
                # Check for pause/cancel before each step
                manager.raise_if_cancelled()

                # Resolve the current plan step explicitly to avoid stale carry-over
                # from previous steps in shared context.
                plan_step = plan_steps[step - 1] if step <= len(plan_steps) else {}

                # Get step description for callbacks
                step_desc = plan_step.get('sub_task', f'Step {step}')
                manager.start_step(step, step_desc)

                clear_work_dir = (step == 1)
                starter_agent = "control" if step == 1 else "control_starter"

                # Initialize CMBAgent
                init_start = time.time()
                cmbagent = CMBAgent(
                    cache_seed=42,
                    work_dir=control_dir,
                    clear_work_dir=clear_work_dir,
                    agent_llm_configs={
                        'engineer': engineer_config,
                        'researcher': researcher_config,
                        'web_surfer': web_surfer_config,
                        'retrieve_assistant': retrieve_assistant_config,
                        'idea_maker': idea_maker_config,
                        'idea_hater': idea_hater_config,
                        'camb_context': camb_context_config,
                        'plot_judge': plot_judge_config,
                    },
                    mode="planning_and_control_context_carryover",
                    api_keys=context.api_keys,
                    **manager.get_managed_cmbagent_kwargs()
                )
                cmbagent._callbacks = context.callbacks
                init_time = time.time() - init_start

                # Get agent for this step from plan first; only then fallback to context.
                agent_for_step = plan_step.get('sub_task_agent') or current_context.get('agent_for_sub_task')

                # Normalize instructions for status/control routing.
                step_instructions = plan_step.get('instructions')
                if not step_instructions:
                    bullet_points = plan_step.get('bullet_points') or []
                    if isinstance(bullet_points, list) and bullet_points:
                        step_instructions = "\n".join(f"- {bp}" for bp in bullet_points)
                    else:
                        step_instructions = step_desc

                # Prepare step context
                step_context = copy.deepcopy(current_context)
                step_context['current_plan_step_number'] = step
                step_context['number_of_steps_in_plan'] = len(plan_steps)
                step_context['n_attempts'] = 0
                step_context['agent_for_sub_task'] = agent_for_step
                step_context['current_sub_task'] = step_desc
                step_context['current_instructions'] = step_instructions
                step_context['current_status'] = 'in progress'
                step_context['engineer_append_instructions'] = self.config.engineer_instructions
                step_context['researcher_append_instructions'] = self.config.researcher_instructions

                # Execute step with retry for transient API errors
                exec_start = time.time()
                step_max_retries = 3
                step_base_delay = 5  # seconds
                for step_attempt in range(1, step_max_retries + 1):
                    try:
                        cmbagent.solve(
                            context.task,
                            max_rounds=self.config.max_rounds,
                            initial_agent=starter_agent,
                            shared_context=step_context,
                            step=step,
                        )
                        break  # success
                    except Exception as solve_err:
                        err_str = str(solve_err)
                        is_rate_limit = (
                            'rate_limit' in err_str.lower()
                            or '429' in err_str
                            or 'RateLimitError' in type(solve_err).__name__
                        )
                        if is_rate_limit and step_attempt < step_max_retries:
                            delay = step_base_delay * (2 ** (step_attempt - 1))
                            logger.warning(
                                "Rate limit hit during step %d (attempt %d/%d), "
                                "retrying in %ds: %s",
                                step, step_attempt, step_max_retries, delay, solve_err,
                            )
                            time.sleep(delay)
                        else:
                            raise
                exec_time = time.time() - exec_start

                # Check for failures
                n_failures = cmbagent.final_context.get('n_attempts', 0)
                if n_failures >= self.config.max_n_attempts:
                    manager.fail_step(step, f"Max attempts ({n_failures}) exceeded")
                    self._status = PhaseStatus.FAILED
                    return manager.fail(
                        f"Step {step} failed after {n_failures} attempts",
                    )

                # Extract step summary and log agent messages
                this_step_summary = None
                for msg in cmbagent.chat_result.chat_history[::-1]:
                    if 'name' in msg and agent_for_step:
                        agent_clean = agent_for_step.removesuffix("_context").removesuffix("_agent")
                        if msg['name'] in [agent_clean, f"{agent_clean}_nest", f"{agent_clean}_response_formatter"]:
                            this_step_summary = msg['content']
                            summary = f"### Step {step}\n{this_step_summary.strip()}"
                            step_summaries.append(summary)
                            cmbagent.final_context['previous_steps_execution_summary'] = _truncate_step_summaries(step_summaries)
                            break

                # Log agent messages from chat history
                for msg in cmbagent.chat_result.chat_history:
                    agent_name = msg.get('name', msg.get('role', 'unknown'))
                    role = msg.get('role', 'assistant')
                    content = msg.get('content', '')
                    if content and isinstance(content, str):
                        # Detect and log code blocks
                        code_blocks = re.findall(r'```(\w*)\n([\s\S]*?)```', content)
                        for language, code in code_blocks:
                            if code.strip():
                                manager.log_code_execution(agent_name, code.strip()[:2000], language or 'python', None)

                        # Log the message
                        manager.log_agent_message(agent_name, role, content[:1000], {"step": step})

                # Mark step complete
                manager.complete_step(step, this_step_summary)

                # Collect results
                step_results.append({
                    'step': step,
                    'context': cmbagent.final_context,
                    'execution_time': exec_time,
                    'initialization_time': init_time,
                    'summary': this_step_summary,
                })
                all_chat_history.extend(cmbagent.chat_result.chat_history)

                # Update context for next step – prune large transient fields
                # to prevent unbounded growth across steps.
                current_context = copy.deepcopy(cmbagent.final_context)
                _prune_carryover_context(current_context)

                # Save step context (filter non-picklable items)
                context_path = os.path.join(context_dir, f"context_step_{step}.pkl")
                
                filtered_context = {}
                for key, value in cmbagent.final_context.items():
                    if key.startswith('_'):
                        continue
                    try:
                        pickle.dumps(value)
                        filtered_context[key] = value
                    except (TypeError, pickle.PicklingError, AttributeError):
                        logger.debug("Skipping non-picklable context key: %s", key)
                
                with open(context_path, 'wb') as f:
                    pickle.dump(filtered_context, f)

                # Save chat history
                chat_full_path = os.path.join(control_dir, "chats")
                os.makedirs(chat_full_path, exist_ok=True)
                chat_output_path = os.path.join(chat_full_path, f"chat_history_step_{step}.json")
                with open(chat_output_path, 'w') as f:
                    json.dump(cmbagent.chat_result.chat_history, f, indent=2)

                # Create dummy groupchat if needed
                if not hasattr(cmbagent, 'groupchat'):
                    Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                    cmbagent.groupchat = Dummy()

                # Display cost
                cmbagent.display_cost(name_append=f"step_{step}")

                logger.info("Step %d completed in %.4f seconds", step, exec_time)

            # Build output
            # Copy output files from control_dir to task work_dir
            # The executor writes files inside control_dir, but the frontend
            # looks in the task root. Copy any report/output files up.
            output_extensions = {'.md', '.txt', '.csv', '.json', '.html', '.pdf'}
            try:
                for item in os.listdir(control_dir):
                    item_path = os.path.join(control_dir, item)
                    if os.path.isfile(item_path):
                        ext = os.path.splitext(item)[1].lower()
                        if ext in output_extensions:
                            dest = os.path.join(context.work_dir, item)
                            shutil.copy2(item_path, dest)
                            logger.info("Copied output file %s to %s", item, dest)
                # Also search in control_dir subdirectories (e.g. data/, codebase/)
                for subdir in ['data', 'codebase']:
                    sub_path = os.path.join(control_dir, subdir)
                    if os.path.isdir(sub_path):
                        for item in os.listdir(sub_path):
                            item_path = os.path.join(sub_path, item)
                            if os.path.isfile(item_path):
                                ext = os.path.splitext(item)[1].lower()
                                if ext in output_extensions:
                                    dest = os.path.join(context.work_dir, item)
                                    shutil.copy2(item_path, dest)
                                    logger.info("Copied output file %s from %s to %s", item, subdir, dest)
            except Exception as copy_err:
                logger.warning("Failed to copy output files: %s", copy_err)

            output_data = {
                'step_results': step_results,
                'final_context': current_context,
                'step_summaries': step_summaries,
                'shared': {
                    'execution_complete': True,
                    'final_context': current_context,
                }
            }

            self._status = PhaseStatus.COMPLETED
            return manager.complete(
                output_data=output_data,
                chat_history=all_chat_history,
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            logger.error("Control phase failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required for control phase")

        # Check for plan (including preloaded plans)
        has_plan = (
            self.config.params.get('preloaded_plan') or
            context.input_data.get('final_plan') or
            context.shared_state.get('plan_steps') or
            context.shared_state.get('final_plan')
        )

        # Distinguish between "no plan key" and "empty plan list"
        if not has_plan and self.config.execute_all_steps:
            plan_present_but_empty = (
                context.input_data.get('final_plan') == [] or
                context.shared_state.get('plan_steps') == [] or
                context.shared_state.get('final_plan') == []
            )
            if plan_present_but_empty:
                errors.append(
                    "Plan is empty (0 steps). The planning phase completed but "
                    "generated no plan steps — check the planner output."
                )
            else:
                errors.append("Plan is required for control phase (run planning first)")

        return errors
