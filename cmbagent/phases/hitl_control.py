"""
HITL Control Phase - Step-by-step execution with human approval.

This module provides a HITLControlPhase that allows humans to:
1. Approve each step before execution
2. Review step results and provide feedback
3. Modify step parameters or skip steps
4. Use AG2's human_input_mode for interactive execution

Uses PhaseExecutionManager for automatic:
- Callback invocation
- Database event logging
- DAG node management
- File tracking
- Pause/cancel handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import time
import copy
import json
import pickle
import re
import logging
import structlog

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.control import _truncate_step_summaries
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.utils import get_model_config, default_agents_llm_model

logger = structlog.get_logger(__name__)


@dataclass
class HITLControlPhaseConfig(PhaseConfig):
    """
    Configuration for HITL control/execution phase.

    Attributes:
        max_rounds: Maximum conversation rounds per step
        max_n_attempts: Maximum attempts per step before failure
        execute_all_steps: Whether to execute all plan steps
        step_number: Specific step to execute (if not all steps)
        approval_mode: When to ask for approval ("before_step", "after_step", "both", "on_error")
        allow_step_skip: Allow human to skip failed steps
        allow_step_retry: Allow human to retry failed steps
        allow_step_modification: Allow human to modify step parameters
        show_step_context: Show accumulated context before each step
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
    """
    phase_type: str = "hitl_control"

    # Execution parameters
    max_rounds: int = 100
    max_n_attempts: int = 3
    max_redos: int = 2  # Maximum number of redo attempts per step

    # Step handling
    execute_all_steps: bool = True
    step_number: Optional[int] = None

    # HITL options
    approval_mode: str = "before_step"  # "before_step", "after_step", "both", "on_error"
    allow_step_skip: bool = True
    allow_step_retry: bool = True
    allow_step_modification: bool = True
    show_step_context: bool = True
    auto_approve_successful_steps: bool = False  # Auto-approve if step succeeds

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

    # AG2 HITL Handoff Configuration (NEW!)
    use_ag2_handoffs: bool = False  # Enable AG2-native HITL handoffs
    ag2_mandatory_checkpoints: List[str] = field(default_factory=list)  # e.g., ["before_file_edit", "before_execution"]
    ag2_smart_approval: bool = False  # Enable dynamic escalation
    ag2_smart_criteria: Dict = field(default_factory=dict)  # Criteria for smart escalation


class HITLControlPhase(Phase):
    """
    Human-in-the-loop control phase with step-by-step approval.

    This phase executes plan steps with human oversight:
    1. Present step to human for approval (before_step mode)
    2. Execute step with agents
    3. Present results to human for review (after_step mode)
    4. Handle errors with human feedback (on_error mode)
    5. Continue or abort based on human decisions

    Input Context:
        - final_plan or plan_steps: The plan to execute
        - task: Original task
        - work_dir: Working directory
        - planning_context: Context from planning phase

    Output Context:
        - step_results: Results from each step
        - final_context: Final context after all steps
        - step_summaries: Summary of each step
        - human_interventions: List of human interventions
        - skipped_steps: List of steps skipped by human
    """

    config_class = HITLControlPhaseConfig

    def __init__(self, config: HITLControlPhaseConfig = None):
        if config is None:
            config = HITLControlPhaseConfig()
        super().__init__(config)
        self.config: HITLControlPhaseConfig = config
        # Initialize feedback state (set properly in execute(), safe defaults here)
        self._accumulated_feedback = ""
        self._step_feedback = []

    @property
    def phase_type(self) -> str:
        return "hitl_control"

    @property
    def display_name(self) -> str:
        return "Interactive Execution (HITL)"

    def get_required_agents(self) -> List[str]:
        return ["control", "control_starter", "engineer", "researcher"]

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute HITL control phase with human feedback loop.

        Args:
            context: Input context with plan and configuration

        Returns:
            PhaseResult with execution results
        """
        # Create execution manager for automatic infrastructure
        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        try:
            # Extract plan (do this before validate_input since we check shared_state too)
            plan_steps = self._extract_plan(context)
            if not plan_steps:
                raise ValueError("No plan steps found in context")

            # Get approval manager
            approval_manager = context.shared_state.get('_approval_manager')
            logger.debug("approval_manager_info", manager_type=f"{type(approval_manager)}", manager=f"{approval_manager}")
            if approval_manager:
                logger.debug("approval_manager_capabilities", has_ws_send_event=hasattr(approval_manager, 'ws_send_event'))
            else:
                logger.warning("no_approval_manager_in_shared_state", shared_state_keys=f"{list(context.shared_state.keys())}")

            # Setup
            from cmbagent.cmbagent import CMBAgent

            api_keys = context.api_keys or {}

            # Get model configs (must match standard control phase)
            engineer_config = get_model_config(self.config.engineer_model, api_keys)
            researcher_config = get_model_config(self.config.researcher_model, api_keys)
            web_surfer_config = get_model_config(self.config.web_surfer_model, api_keys)
            retrieve_assistant_config = get_model_config(self.config.retrieve_assistant_model, api_keys)
            idea_maker_config = get_model_config(self.config.idea_maker_model, api_keys)
            idea_hater_config = get_model_config(self.config.idea_hater_model, api_keys)
            camb_context_config = get_model_config(self.config.camb_context_model, api_keys)
            plot_judge_config = get_model_config(self.config.plot_judge_model, api_keys)

            agent_llm_configs = {
                'engineer': engineer_config,
                'researcher': researcher_config,
                'web_surfer': web_surfer_config,
                'retrieve_assistant': retrieve_assistant_config,
                'idea_maker': idea_maker_config,
                'idea_hater': idea_hater_config,
                'camb_context': camb_context_config,
                'plot_judge': plot_judge_config,
            }

            # Include any feedback from previous HITL phases
            hitl_feedback = context.shared_state.get('hitl_feedback', '')

            # Determine which steps to execute
            if self.config.execute_all_steps:
                steps_to_execute = list(range(1, len(plan_steps) + 1))
            elif self.config.step_number is not None:
                steps_to_execute = [self.config.step_number]
            else:
                steps_to_execute = list(range(1, len(plan_steps) + 1))

            # Execution tracking
            step_results = []
            step_summaries = []
            human_interventions = []
            skipped_steps = []
            all_chat_history = []

            # Initialize current context from planning output (matches standard ControlPhase)
            planning_context = (
                context.input_data.get('planning_context') or
                context.shared_state.get('planning_context') or
                {}
            )
            current_context = copy.deepcopy(planning_context)

            # Setup directories (match standard ControlPhase)
            control_dir = os.path.join(context.work_dir, "control")
            os.makedirs(control_dir, exist_ok=True)
            context_dir = os.path.join(context.work_dir, "context")
            os.makedirs(context_dir, exist_ok=True)

            current_context['work_dir'] = control_dir

            # Initialize accumulated feedback from previous phases
            self._accumulated_feedback = hitl_feedback
            self._step_feedback = []  # Feedback collected during control phase

            # Execute steps
            for step_num in steps_to_execute:
                step = plan_steps[step_num - 1]

                # Check for cancellation
                manager.raise_if_cancelled()

                # Update manager's current step
                manager.current_step = step_num

                logger.info("step_begin", step_num=step_num, total_steps=len(plan_steps), sub_task=step.get('sub_task', 'Unknown'))

                # Before-step approval
                if self.config.approval_mode in ["before_step", "both"]:
                    approval_result = await self._request_step_approval(
                        approval_manager,
                        context,
                        step,
                        step_num,
                        "before_step",
                        current_context,
                        manager
                    )

                    if approval_result is None:  # Skip
                        skipped_steps.append(step_num)
                        logger.info("step_skipped_by_human", step_num=step_num)
                        continue
                    elif approval_result is False:  # Rejected
                        return manager.fail(f"Step {step_num} rejected by human", None)
                    elif isinstance(approval_result, dict):  # Approved with feedback
                        if 'feedback' in approval_result:
                            feedback = approval_result['feedback']
                            self._add_feedback(step_num, "guidance", feedback, "before")
                            logger.info("human_feedback_received", step_num=step_num, feedback=feedback)
                    # else: True (approved without feedback)

                # Notify callbacks
                step_desc = step.get('sub_task', f'Step {step_num}')
                manager.start_step(step_num, step_desc)

                # Redo loop wraps the entire execution + review cycle
                max_redos = self.config.max_redos  # Use configurable max_redos
                redo_count = 0
                step_accepted = False

                while not step_accepted and redo_count <= max_redos:
                    if redo_count > 0:
                        logger.info("step_redo_initiated", step_num=step_num, redo_count=redo_count)

                    # Execute step (attempt loop)
                    success = False
                    attempt = 0
                    step_result = None
                    step_error = None
                    cmbagent = None

                    while attempt < self.config.max_n_attempts and not success:
                        attempt += 1

                        try:
                            logger.info("step_executing", step_num=step_num, attempt=attempt, max_attempts=self.config.max_n_attempts)

                            # Determine starter agent (matches standard ControlPhase)
                            # Only clear work dir on very first execution of step 1
                            clear_work_dir = (step_num == 1 and redo_count == 0)
                            starter_agent = "control" if step_num == 1 else "control_starter"

                            # Initialize fresh CMBAgent for each attempt (matches standard ControlPhase)
                            cmbagent = CMBAgent(
                                cache_seed=42,
                                work_dir=control_dir,
                                clear_work_dir=clear_work_dir,
                                agent_llm_configs=agent_llm_configs,
                                mode="planning_and_control_context_carryover",
                                api_keys=api_keys,
                                **manager.get_managed_cmbagent_kwargs()
                            )
                            cmbagent._callbacks = context.callbacks

                            # Configure AG2 HITL handoffs (if enabled)
                            if self.config.use_ag2_handoffs:
                                from cmbagent.handoffs import register_all_hand_offs, enable_websocket_for_hitl

                                hitl_config = {
                                    'mandatory_checkpoints': self.config.ag2_mandatory_checkpoints,
                                    'smart_approval': self.config.ag2_smart_approval,
                                    'smart_criteria': self.config.ag2_smart_criteria,
                                }

                                # Register handoffs with HITL config
                                register_all_hand_offs(cmbagent, hitl_config=hitl_config)

                                # Enable WebSocket for AG2 handoffs so they appear in UI
                                if approval_manager:
                                    try:
                                        enable_websocket_for_hitl(cmbagent, approval_manager, context.run_id)
                                    except Exception as e:
                                        logger.warning("websocket_ag2_handoff_enable_failed", error=str(e))
                                else:
                                    logger.warning("no_approval_manager_for_ag2_handoffs")

                            # Get agent for this step
                            if step_num == 1 and plan_steps:
                                agent_for_step = plan_steps[0].get('sub_task_agent')
                            else:
                                agent_for_step = current_context.get('agent_for_sub_task')

                            # Prepare step context (matches standard ControlPhase)
                            step_shared_context = copy.deepcopy(current_context)
                            step_shared_context['current_plan_step_number'] = step_num
                            step_shared_context['n_attempts'] = attempt - 1
                            step_shared_context['agent_for_sub_task'] = agent_for_step

                            # Build agent instructions: static config + accumulated HITL feedback
                            engineer_instructions = self.config.engineer_instructions or ""
                            researcher_instructions = self.config.researcher_instructions or ""

                            if self._accumulated_feedback:
                                safe_feedback = self._truncate_feedback(self._accumulated_feedback)
                                hitl_section = (
                                    "\n\n## Human-in-the-Loop Feedback\n"
                                    "The human reviewer has provided the following guidance. "
                                    "You MUST follow these instructions:\n\n"
                                    f"{safe_feedback}\n"
                                )
                                engineer_instructions += hitl_section
                                researcher_instructions += hitl_section

                            # Inject step-specific before-feedback (current step only)
                            current_step_before = [
                                f for f in self._step_feedback
                                if f['step'] == step_num and f['timing'] == 'before'
                            ]
                            if current_step_before:
                                step_guidance = "\n\n## Specific Guidance for This Step\n"
                                for fb in current_step_before:
                                    step_guidance += f"- {fb['feedback']}\n"
                                engineer_instructions += step_guidance
                                researcher_instructions += step_guidance

                            step_shared_context['engineer_append_instructions'] = engineer_instructions
                            step_shared_context['researcher_append_instructions'] = researcher_instructions

                            # Execute with control agent
                            cmbagent.solve(
                                task=context.task,
                                initial_agent=starter_agent,
                                max_rounds=self.config.max_rounds,
                                shared_context=step_shared_context,
                                step=step_num,
                            )

                            # Check for failures (matches standard ControlPhase logic)
                            n_failures = cmbagent.final_context.get('n_attempts', 0)
                            if n_failures >= self.config.max_n_attempts:
                                success = False
                                step_error = f"Max attempts ({n_failures}) exceeded"
                            else:
                                success = True
                                step_result = cmbagent.final_context

                                # Extract step summary (matches standard ControlPhase)
                                this_step_summary = None
                                for msg in cmbagent.chat_result.chat_history[::-1]:
                                    if 'name' in msg and agent_for_step:
                                        agent_clean = agent_for_step.removesuffix("_context").removesuffix("_agent")
                                        if msg['name'] in [agent_clean, f"{agent_clean}_nest", f"{agent_clean}_response_formatter"]:
                                            this_step_summary = msg['content']
                                            summary = f"### Step {step_num}\n{this_step_summary.strip()}"
                                            # On redo, replace previous summary for this step
                                            step_summaries = [
                                                s for s in step_summaries
                                                if not s.startswith(f"### Step {step_num}\n")
                                            ]
                                            step_summaries.append(summary)
                                            cmbagent.final_context['previous_steps_execution_summary'] = _truncate_step_summaries(
                                                step_summaries
                                            )
                                            break

                                # Update context for next step
                                current_context = copy.deepcopy(cmbagent.final_context)

                            if success:
                                logger.info("step_completed_successfully", step_num=step_num)
                            else:
                                logger.error("step_failed", step_num=step_num, error=step_error)

                        except Exception as e:
                            success = False
                            step_error = str(e)
                            logger.error("step_execution_error", step_num=step_num, error=step_error)

                        # On error, ask for human intervention if configured
                        if not success and self.config.approval_mode in ["on_error", "both"]:
                            action = await self._request_error_handling(
                                approval_manager,
                                context,
                                step,
                                step_num,
                                step_error,
                                attempt,
                                manager
                            )

                            if action == "retry":
                                logger.info("step_retry", step_num=step_num)
                                continue
                            elif action == "skip":
                                logger.info("step_skip_after_error", step_num=step_num)
                                skipped_steps.append(step_num)
                                success = True  # Treat as success to continue
                                break
                            elif action == "abort":
                                return manager.fail(f"Aborted by human at step {step_num}", None)

                    # -- END attempt loop --

                    # Check final success
                    if not success:
                        manager.fail_step(step_num, step_error or "Max attempts exceeded")
                        return manager.fail(
                            f"Step {step_num} failed after {self.config.max_n_attempts} attempts",
                            step_error
                        )

                    # After-step approval/review
                    if self.config.approval_mode in ["after_step", "both"]:
                        if not (self.config.auto_approve_successful_steps and success):
                            review_result = await self._request_step_review(
                                approval_manager,
                                context,
                                step,
                                step_num,
                                step_result,
                                manager
                            )

                            if review_result is False:  # Abort
                                return manager.fail(f"Step {step_num} review rejected by human", None)

                            elif review_result is None or (isinstance(review_result, dict) and review_result.get('redo')):
                                # Redo requested
                                redo_count += 1

                                # Capture redo feedback if provided
                                if isinstance(review_result, dict) and review_result.get('feedback'):
                                    redo_feedback = review_result['feedback']
                                    self._add_feedback(step_num, "redo requested", redo_feedback, "redo")
                                    logger.info("step_redo_with_feedback", step_num=step_num, feedback=redo_feedback)

                                if redo_count > max_redos:
                                    logger.warning("max_redos_reached", step_num=step_num, max_redos=max_redos)
                                    step_accepted = True
                                else:
                                    human_interventions.append({
                                        'step': step_num,
                                        'action': 'redo',
                                        'redo_count': redo_count,
                                        'feedback': review_result.get('feedback') if isinstance(review_result, dict) else None,
                                    })
                                    continue  # Re-enter redo loop

                            elif isinstance(review_result, dict):  # Continue with feedback
                                if 'feedback' in review_result:
                                    feedback = review_result['feedback']
                                    self._add_feedback(step_num, "notes", feedback, "after")
                                    logger.info("human_notes_received", step_num=step_num, feedback=feedback)
                                step_accepted = True
                            else:
                                step_accepted = True
                        else:
                            step_accepted = True
                    else:
                        step_accepted = True

                # -- END redo loop --

                # Record step result with chat history
                step_chat_history = []
                if cmbagent and hasattr(cmbagent, 'chat_result') and cmbagent.chat_result:
                    step_chat_history = cmbagent.chat_result.chat_history or []
                    all_chat_history.extend(step_chat_history)

                step_results.append({
                    'step': step_num,
                    'success': success,
                    'result': step_result,
                    'attempts': attempt,
                    'redos': redo_count,
                    'chat_history': step_chat_history,
                })

                # Save step context (filter non-picklable items)
                context_path = os.path.join(context_dir, f"context_step_{step_num}.pkl")

                # Filter out non-picklable items before saving
                filtered_context = {}
                for key, value in current_context.items():
                    if key.startswith('_'):
                        continue  # Skip private keys
                    try:
                        pickle.dumps(value)  # Test if picklable
                        filtered_context[key] = value
                    except (TypeError, pickle.PicklingError, AttributeError):
                        logger.debug("skipping_non_picklable_context_key", key=key)

                with open(context_path, 'wb') as f:
                    pickle.dump(filtered_context, f)

                # Save chat history
                chat_full_path = os.path.join(control_dir, "chats")
                os.makedirs(chat_full_path, exist_ok=True)
                chat_output_path = os.path.join(chat_full_path, f"chat_history_step_{step_num}.json")
                with open(chat_output_path, 'w') as f:
                    json.dump(step_chat_history, f, indent=2)

                # Display cost
                if cmbagent:
                    if not hasattr(cmbagent, 'groupchat'):
                        Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
                        cmbagent.groupchat = Dummy()
                    cmbagent.display_cost(name_append=f"step_{step_num}")

                manager.complete_step(step_num, "Step completed")

                logger.info("step_completed_in_control_phase", step_num=step_num)

            # Save final context (filter non-picklable items)
            context_file = os.path.join(context.work_dir, 'final_context.pkl')

            # Filter out non-picklable items before saving
            filtered_final_context = {}
            for key, value in current_context.items():
                if key.startswith('_'):
                    continue
                try:
                    pickle.dumps(value)
                    filtered_final_context[key] = value
                except (TypeError, pickle.PicklingError, AttributeError):
                    logger.debug("skipping_non_picklable_final_context_key", key=key)

            with open(context_file, 'wb') as f:
                pickle.dump(filtered_final_context, f)

            # Build output
            output_data = {
                'step_results': step_results,
                'final_context': current_context,
                'step_summaries': step_summaries,
                'human_interventions': human_interventions,
                'skipped_steps': skipped_steps,
                'step_feedback': self._step_feedback,
                'shared': {
                    'final_context': current_context,
                    'executed_steps': len(step_results),
                    'step_feedback': self._step_feedback,
                    'control_feedback': self._step_feedback,
                    'all_hitl_feedback': self._accumulated_feedback,
                    'execution_complete': True,
                }
            }

            self._status = PhaseStatus.COMPLETED

            return manager.complete(
                output_data=output_data,
                chat_history=all_chat_history,
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            import traceback
            return manager.fail(str(e), traceback.format_exc())

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required")
        if not context.work_dir:
            errors.append("Work directory is required")

        # Check for plan in both input_data and shared_state
        plan = (
            context.input_data.get('final_plan') or
            context.input_data.get('plan_steps') or
            context.shared_state.get('final_plan') or
            context.shared_state.get('plan_steps')
        )
        if not plan:
            errors.append("Plan is required (final_plan or plan_steps)")

        return errors

    def _extract_plan(self, context: PhaseContext) -> List[Dict]:
        """Extract plan from context."""
        # Try multiple keys in both input_data and shared_state
        for key in ['final_plan', 'plan_steps', 'plan']:
            plan = context.input_data.get(key) or context.shared_state.get(key)
            if plan and isinstance(plan, list):
                return plan
        return []

    def _add_feedback(self, step_num: int, label: str, feedback: str, timing: str):
        """Add feedback to both accumulated string and structured list.

        Args:
            step_num: Step number this feedback relates to
            label: Label for the feedback (e.g. "guidance", "redo requested", "notes")
            feedback: The actual feedback text
            timing: When this feedback was given ("before", "after", "redo")
        """
        entry = f"**Step {step_num} {label}:** {feedback}"
        if self._accumulated_feedback:
            self._accumulated_feedback += f"\n\n{entry}"
        else:
            self._accumulated_feedback = entry
        self._step_feedback.append({
            'step': step_num,
            'timing': timing,
            'feedback': feedback,
        })

    def _truncate_feedback(self, feedback: str, max_chars: int = 4000) -> str:
        """Truncate accumulated feedback to prevent context overflow.

        Keeps the most recent feedback (end of string) since it is
        most relevant to the current step being executed.
        """
        if not feedback or len(feedback) <= max_chars:
            return feedback

        truncated = feedback[-(max_chars):]
        # Find first complete section boundary to avoid mid-sentence cut
        boundary = truncated.find('\n\n**Step')
        if boundary > 0:
            truncated = truncated[boundary:]

        return f"[Earlier feedback truncated]\n{truncated}"

    async def _request_step_approval(
        self,
        approval_manager,
        context: PhaseContext,
        step: Dict,
        step_num: int,
        checkpoint_type: str,
        accumulated_context: Dict,
        manager: PhaseExecutionManager
    ) -> Optional[bool]:
        """
        Request human approval before executing a step.

        Returns:
            True: Approved
            False: Rejected
            None: Skipped
            dict: Approved with feedback
        """
        if not approval_manager:
            # Console fallback
            logger.info("step_approval_console_prompt", step_num=step_num, task=step.get('sub_task'))
            response = input("\nAction? (y=approve/n=reject/s=skip/[feedback text to approve with]): ").strip()

            lower = response.lower()
            if lower in ('y', 'yes'):
                return True
            elif lower in ('s', 'skip'):
                return None
            elif lower in ('n', 'no'):
                return False
            else:
                # Treat any other text as "approve with feedback"
                return {'approved': True, 'feedback': response}

        # Use approval manager
        message = self._build_step_approval_message(step, step_num, accumulated_context)

        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}",
            checkpoint_type=checkpoint_type,
            context_snapshot={
                'step': step,
                'step_num': step_num,
            },
            message=message,
            options=["approve", "reject", "skip"],
        )

        logger.info("step_approval_requested", step_num=step_num, message=message)
        logger.info("waiting_for_approval", step_num=step_num)

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        # Accept both "approved" and "approve"
        if resolved.resolution in ["approved", "approve"]:
            # Check for feedback
            if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
                return {'approved': True, 'feedback': resolved.user_feedback}
            return True
        elif resolved.resolution == "skip":
            return None
        else:
            return False

    async def _request_step_review(
        self,
        approval_manager,
        context: PhaseContext,
        step: Dict,
        step_num: int,
        step_result: Dict,
        manager: PhaseExecutionManager
    ) -> Optional[bool]:
        """Request human review after executing a step.

        Returns:
            True: Continue to next step
            False: Abort workflow
            None: Redo step (without feedback)
            dict with 'redo': Redo step with feedback
            dict with 'continue': Continue with feedback
        """
        if not approval_manager:
            logger.info("step_review_console_prompt", step_num=step_num, status="completed_successfully")
            response = input("\nAction? (c=continue/r=redo/a=abort/[feedback text]): ").strip()

            lower = response.lower()
            if lower in ('c', 'continue', 'y', 'yes'):
                return True
            elif lower in ('r', 'redo'):
                return None
            elif lower in ('a', 'abort', 'n', 'no'):
                return False
            else:
                # Treat any other input as "continue with feedback"
                return {'continue': True, 'feedback': response}

        message = self._build_step_review_message(step, step_num, step_result)

        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}_review",
            checkpoint_type="after_step",
            context_snapshot={
                'step': step,
                'step_num': step_num,
                'result': step_result,
            },
            message=message,
            options=["continue", "abort", "redo"],
        )

        logger.info("step_review_requested", step_num=step_num, message=message)
        logger.info("waiting_for_review", step_num=step_num)

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        if resolved.resolution == "continue":
            # Check for feedback
            if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
                return {'continue': True, 'feedback': resolved.user_feedback}
            return True
        elif resolved.resolution == "redo":
            # Capture redo feedback so agents know what to fix on re-execution
            redo_feedback = getattr(resolved, 'user_feedback', None) or ''
            if redo_feedback:
                return {'redo': True, 'feedback': redo_feedback}
            return None  # Redo without specific feedback
        else:
            return False

    async def _request_error_handling(
        self,
        approval_manager,
        context: PhaseContext,
        step: Dict,
        step_num: int,
        error: str,
        attempt: int,
        manager: PhaseExecutionManager
    ) -> str:
        """
        Request human decision on how to handle an error.

        Returns:
            "retry": Retry the step
            "skip": Skip the step
            "abort": Abort the workflow
        """
        if not approval_manager:
            logger.error("step_error_console_prompt", step_num=step_num, attempt=attempt, error=error)
            response = input("\nHow to proceed? (r=retry/s=skip/a=abort): ").strip().lower()

            if response == 'r' or response == 'retry':
                return "retry"
            elif response == 's' or response == 'skip':
                return "skip"
            else:
                return "abort"

        message = self._build_error_handling_message(step, step_num, error, attempt)

        approval_request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}_error",
            checkpoint_type="on_error",
            context_snapshot={
                'step': step,
                'step_num': step_num,
                'error': error,
                'attempt': attempt,
            },
            message=message,
            options=["retry", "skip", "abort"],
        )

        logger.error("step_error_intervention_required", step_num=step_num, message=message)
        logger.info("waiting_for_error_decision", step_num=step_num)

        resolved = await approval_manager.wait_for_approval_async(
            str(approval_request.id),
            timeout_seconds=1800,
        )

        return resolved.resolution

    def _build_step_approval_message(self, step: Dict, step_num: int, context: Dict) -> str:
        """Build message for step approval with context from previous steps."""
        parts = [
            f"**Step {step_num}**",
            "",
            f"**Task:** {step.get('sub_task', 'Unknown')}",
            "",
        ]

        if self.config.show_step_context and step_num > 1:
            prev_summary = context.get('previous_steps_execution_summary', '')
            if prev_summary:
                # Truncate to keep message readable
                summary_text = prev_summary[-500:] if len(prev_summary) > 500 else prev_summary
                parts.extend([
                    "**Previous Steps Summary:**",
                    summary_text,
                    "",
                ])

        if self._accumulated_feedback:
            truncated_fb = self._accumulated_feedback[-300:] if len(self._accumulated_feedback) > 300 else self._accumulated_feedback
            parts.extend([
                "**Accumulated Human Feedback:**",
                truncated_fb,
                "",
            ])

        parts.extend([
            "**Options:**",
            "- **Approve**: Execute this step",
            "- **Skip**: Skip this step and continue",
            "- **Reject**: Cancel the workflow",
            "",
            "You can also provide feedback text that will guide the agent during execution.",
        ])

        return "\n".join(parts)

    def _build_step_review_message(self, step: Dict, step_num: int, result: Dict) -> str:
        """Build message for step review with result details."""
        # Extract meaningful result info
        result_summary = ""
        if result and isinstance(result, dict):
            summary = result.get('previous_steps_execution_summary', '')
            if summary:
                # Get only this step's summary
                lines = summary.split(f"### Step {step_num}\n")
                if len(lines) > 1:
                    step_text = lines[-1].split("### Step")[0].strip()
                    if step_text:
                        result_summary = f"\n**Result Summary:**\n{step_text[:1000]}\n"

        return f"""**Step {step_num} Review**

**Task:** {step.get('sub_task', 'Unknown')}

**Status:** Completed successfully
{result_summary}
**Options:**
- **Continue**: Proceed to next step
- **Redo**: Re-execute this step (optionally provide feedback on what to change)
- **Abort**: Cancel the workflow
"""

    def _build_error_handling_message(self, step: Dict, step_num: int, error: str, attempt: int) -> str:
        """Build message for error handling."""
        return f"""**Step {step_num} Error**

**Task:** {step.get('sub_task', 'Unknown')}

**Attempt:** {attempt}/{self.config.max_n_attempts}

**Error:** {error}

**Options:**
- **Retry**: Attempt to execute the step again
- **Skip**: Skip this step and continue with the workflow
- **Abort**: Cancel the entire workflow
"""
