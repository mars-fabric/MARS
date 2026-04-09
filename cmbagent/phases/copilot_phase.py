"""
Copilot Phase - Flexible AI assistant that adapts to task complexity.

This module provides a CopilotPhase that:
1. Analyzes task complexity automatically
2. Routes simple tasks to one-shot execution
3. Routes complex tasks through planning + execution
4. Supports continuous interaction mode
5. Dynamically selects agents based on configuration

Uses PhaseExecutionManager for automatic:
- Callback invocation
- Database event logging
- DAG node management
- File tracking
- Pause/cancel handling
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import os
import copy
import json
import asyncio
import traceback
import logging

logger = logging.getLogger(__name__)

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult, PhaseStatus
from cmbagent.phases.control import _truncate_step_summaries
from cmbagent.phases.execution_manager import PhaseExecutionManager
from cmbagent.utils import get_model_config, CORE_AGENTS


@dataclass
class CopilotPhaseConfig(PhaseConfig):
    """
    Configuration for copilot phase.

    Attributes:
        available_agents: List of agents available for this copilot session
        enable_planning: Whether to auto-plan complex tasks
        complexity_threshold: Word count threshold for "complex" tasks
        continuous_mode: Keep running until user exits
        memory_enabled: Remember context across turns
        max_turns: Safety limit for continuous mode
        max_rounds: Max conversation rounds per execution
        max_plan_steps: Max steps in generated plans
        approval_mode: HITL approval mode (before_step, after_step, both, none)
        auto_approve_simple: Skip approval for simple one-shot tasks
        use_dynamic_routing: Use LLM-based control agent for routing (vs heuristics)
        lightweight_mode: Use minimal agent loading and reuse (RECOMMENDED for speed)
        control_model: Model to use for the control agent
        engineer_model: Model for engineer agent
        researcher_model: Model for researcher agent
        planner_model: Model for planner agent
    """
    phase_type: str = "copilot"

    # Agent configuration - only core agents by default
    available_agents: List[str] = field(default_factory=lambda: ["engineer", "researcher"])

    # Performance optimization - NEW
    lightweight_mode: bool = True  # Use lightweight copilot manager (5-7 agents instead of 49)

    # Task routing
    enable_planning: bool = True
    use_dynamic_routing: bool = True  # Use LLM-based copilot_control agent
    complexity_threshold: int = 50  # Words - fallback threshold for heuristic mode
    planning_keywords: List[str] = field(default_factory=lambda: [
        "step by step", "multiple", "first", "then", "finally",
        "implement", "create", "build", "develop", "design"
    ])

    # Execution mode
    continuous_mode: bool = False  # Single task by default
    memory_enabled: bool = True
    max_turns: int = 20
    max_rounds: int = 100
    max_plan_steps: int = 5
    max_n_attempts: int = 3

    # HITL settings
    approval_mode: str = "after_step"  # before_step, after_step, both, none
    auto_approve_simple: bool = True

    # Model selection - defaults to core models only
    control_model: str = field(default_factory=lambda: CORE_AGENTS.get('planner', 'gpt-4o'))  # For routing decisions
    engineer_model: str = field(default_factory=lambda: CORE_AGENTS.get('engineer', 'gpt-4o'))
    researcher_model: str = field(default_factory=lambda: CORE_AGENTS.get('researcher', 'gpt-4o'))
    planner_model: str = field(default_factory=lambda: CORE_AGENTS.get('planner', 'gpt-4o'))
    plan_reviewer_model: str = field(default_factory=lambda: CORE_AGENTS.get('plan_reviewer', 'gpt-4o'))

    # Instructions
    engineer_instructions: str = ""
    researcher_instructions: str = ""
    planner_instructions: str = ""


class CopilotPhase(Phase):
    """
    Flexible copilot phase that adapts to task complexity.

    This phase intelligently routes tasks:
    - Simple tasks → Direct one-shot execution
    - Complex tasks → Planning → HITL approval → Step execution

    Supports continuous mode for interactive sessions.

    Input Context:
        - task: The task description
        - work_dir: Working directory
        - api_keys: API credentials

    Output Context:
        - results: Execution results
        - plan: Generated plan (if planning was used)
        - turns: Number of interaction turns
        - mode_used: "one_shot" or "planned"
    """

    config_class = CopilotPhaseConfig

    def __init__(self, config: CopilotPhaseConfig = None):
        if config is None:
            config = CopilotPhaseConfig()
        super().__init__(config)
        self.config: CopilotPhaseConfig = config
        self._accumulated_feedback = ""
        self._conversation_history = []
        self._cmbagent_instance = None  # Reusable session
        self._cmbagent_work_dir = None

    @property
    def phase_type(self) -> str:
        return "copilot"

    @property
    def display_name(self) -> str:
        return "Copilot Assistant"

    def get_required_agents(self) -> List[str]:
        """Return agents needed based on configuration."""
        base_agents = ["admin", "executor", "executor_response_formatter"]

        # Add formatters and nest agents for available agents that need them
        if "engineer" in self.config.available_agents:
            base_agents.extend(["engineer_nest", "engineer_response_formatter"])
        if "researcher" in self.config.available_agents:
            base_agents.extend(["researcher_response_formatter", "researcher_executor"])

        if self.config.enable_planning:
            base_agents.extend(["planner", "plan_reviewer", "plan_setter", "planner_response_formatter"])

        base_agents.extend(self.config.available_agents)

        # Add control agents for step execution
        base_agents.extend(["control", "control_starter"])

        return list(set(base_agents))

    def _get_or_create_cmbagent_session(
        self,
        context: PhaseContext,
        clear_work_dir: bool = False
    ):
        """
        Get or create a reusable CMBAgent session.

        This initializes the CMBAgent once and reuses it across all copilot operations,
        avoiding expensive re-initialization for every task/turn.

        Args:
            context: Phase context with work_dir, api_keys, etc.
            clear_work_dir: Whether to clear the work directory (only on first init)

        Returns:
            CMBAgent instance
        """
        if self._cmbagent_instance is not None:
            # Reuse existing session
            return self._cmbagent_instance

        # First-time initialization
        from cmbagent.cmbagent import CMBAgent

        api_keys = context.api_keys or {}

        # Setup work directory
        copilot_dir = os.path.join(context.work_dir, "copilot")
        os.makedirs(copilot_dir, exist_ok=True)
        self._cmbagent_work_dir = copilot_dir

        # Build agent configs for all available agents
        agent_llm_configs = self._build_agent_configs(api_keys)

        # Add planning agents if enabled
        if self.config.enable_planning:
            agent_llm_configs['planner'] = get_model_config(self.config.planner_model, api_keys)
            agent_llm_configs['plan_reviewer'] = get_model_config(self.config.plan_reviewer_model, api_keys)

        # Add copilot_control for routing
        if self.config.use_dynamic_routing:
            agent_llm_configs['copilot_control'] = get_model_config(self.config.control_model, api_keys)

        logger.info("Initializing agent session...")

        # Create CMBAgent with all required agents
        self._cmbagent_instance = CMBAgent(
            cache_seed=42,
            work_dir=copilot_dir,
            clear_work_dir=clear_work_dir,
            agent_llm_configs=agent_llm_configs,
            agent_list=self.get_required_agents(),  # Use our filtered agent list
            api_keys=api_keys,
            skip_rag_agents=True,  # Copilot doesn't need RAG
            skip_executor=False,  # We need executor for code
        )

        # Store available agents for function registration
        if self.config.use_dynamic_routing:
            self._cmbagent_instance.copilot_available_agents = self.config.available_agents

        logger.info("Session initialized with %d agents", len(self._cmbagent_instance.agents))

        return self._cmbagent_instance

    def _cleanup_session(self):
        """Clean up the CMBAgent session when copilot ends."""
        if self._cmbagent_instance is not None:
            logger.info("Cleaning up session...")
            # Close any open resources
            if hasattr(self._cmbagent_instance, 'db_session') and self._cmbagent_instance.db_session:
                try:
                    self._cmbagent_instance.db_session.close()
                except:
                    pass
            self._cmbagent_instance = None
            self._cmbagent_work_dir = None

    async def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute copilot phase with adaptive task routing.

        Args:
            context: Input context with task and configuration

        Returns:
            PhaseResult with execution results
        """
        manager = PhaseExecutionManager(context, self)
        manager.start()

        self._status = PhaseStatus.RUNNING

        try:
            # Validate input
            validation_errors = self.validate_input(context)
            if validation_errors:
                raise ValueError(f"Input validation failed: {', '.join(validation_errors)}")

            # Initialize CMBAgent session once (reused for all operations)
            self._get_or_create_cmbagent_session(context, clear_work_dir=True)

            # Get approval manager for HITL
            approval_manager = context.shared_state.get('_approval_manager')

            # Initialize results tracking
            all_results = []
            turn = 0
            current_task = context.task
            current_context = copy.deepcopy(context.shared_state)

            # Main copilot loop
            while turn < self.config.max_turns:
                turn += 1
                manager.log_event("copilot_turn", {"turn": turn})

                # Check for cancellation
                manager.raise_if_cancelled()

                # Exit conditions
                if not current_task:
                    break
                if current_task.lower().strip() in ['exit', 'quit', 'done', 'bye']:
                    logger.info("Copilot session ended by user")
                    break

                logger.info("=" * 60)
                logger.info("COPILOT - Turn %d", turn)
                logger.info("=" * 60)
                logger.info("Task: %s...", current_task[:200])

                # Analyze task - use dynamic routing or fallback to heuristics
                if self.config.use_dynamic_routing:
                    routing_decision = await self._analyze_with_control_agent(
                        context, current_task, current_context, manager
                    )
                    complexity = "complex" if routing_decision.get('route_type') == 'planned' else "simple"
                    analysis = routing_decision.get('complexity_reasoning', 'Dynamic analysis')
                    primary_agent = routing_decision.get('primary_agent', 'engineer')
                    refined_task = routing_decision.get('refined_task', current_task)

                    # Handle clarify route
                    if routing_decision.get('route_type') == 'clarify':
                        questions = routing_decision.get('clarifying_questions', [])
                        if questions and approval_manager:
                            # Request clarification from user
                            clarified = await self._request_clarification(
                                questions, approval_manager, context, manager
                            )
                            if clarified:
                                current_task = clarified
                                continue  # Re-analyze with clarified task
                else:
                    complexity, analysis = self._analyze_complexity(current_task)
                    primary_agent = self._select_primary_agent(current_task)
                    refined_task = current_task

                logger.info("Complexity: %s (%s)", complexity, analysis)
                logger.info("Primary Agent: %s", primary_agent)

                # Route based on complexity
                if complexity == "simple" or not self.config.enable_planning:
                    # One-shot execution
                    logger.info("Routing to one-shot execution")
                    result = await self._execute_one_shot(
                        context, refined_task, current_context, manager,
                        primary_agent=primary_agent
                    )
                    mode_used = "one_shot"
                else:
                    # Planning + execution
                    logger.info("Routing to planning + execution")
                    result = await self._execute_with_planning(
                        context, refined_task, current_context,
                        approval_manager, manager
                    )
                    mode_used = "planned"

                # Store result
                all_results.append({
                    'turn': turn,
                    'task': current_task,
                    'mode': mode_used,
                    'complexity': complexity,
                    'result': result,
                })

                # Update context for next turn
                if result.get('final_context'):
                    current_context = copy.deepcopy(result['final_context'])

                # Store in conversation history
                self._conversation_history.append({
                    'turn': turn,
                    'task': current_task,
                    'result_summary': result.get('summary', ''),
                })

                # Check if continuous mode
                if not self.config.continuous_mode:
                    break

                # Get next task from user
                next_task = await self._get_next_task(
                    context, result, approval_manager, manager
                )

                if next_task is None:
                    break

                current_task = next_task

            # Build output
            output_data = {
                'results': all_results,
                'turns': turn,
                'conversation_history': self._conversation_history,
                'shared': {
                    'final_context': current_context,
                    'copilot_turns': turn,
                    'copilot_history': self._conversation_history,
                }
            }

            self._status = PhaseStatus.COMPLETED

            return manager.complete(
                output_data=output_data,
                chat_history=[],
            )

        except Exception as e:
            self._status = PhaseStatus.FAILED
            logger.error("Copilot phase failed: %s", e, exc_info=True)
            return manager.fail(str(e), traceback.format_exc())
        finally:
            # Clean up session when copilot ends
            self._cleanup_session()

    def validate_input(self, context: PhaseContext) -> List[str]:
        """Validate that required input is present."""
        errors = []
        if not context.task:
            errors.append("Task is required")
        if not context.work_dir:
            errors.append("Work directory is required")
        return errors

    def _analyze_complexity(self, task: str) -> Tuple[str, str]:
        """
        Analyze task complexity to determine routing.

        Returns:
            Tuple of (complexity: "simple"|"complex", analysis: str)
        """
        # Word count check
        word_count = len(task.split())

        # Keyword check
        task_lower = task.lower()
        has_planning_keywords = any(
            kw in task_lower for kw in self.config.planning_keywords
        )

        # Multiple sentence check
        sentence_count = task.count('.') + task.count('?') + task.count('!')

        # Determine complexity
        reasons = []

        if word_count > self.config.complexity_threshold:
            reasons.append(f"long task ({word_count} words)")

        if has_planning_keywords:
            reasons.append("planning keywords detected")

        if sentence_count > 3:
            reasons.append(f"multiple sentences ({sentence_count})")

        if len(reasons) >= 2:
            return "complex", "; ".join(reasons)
        elif len(reasons) == 1 and word_count > self.config.complexity_threshold * 1.5:
            return "complex", reasons[0]
        else:
            return "simple", "straightforward task"

    async def _analyze_with_control_agent(
        self,
        context: PhaseContext,
        task: str,
        current_context: Dict[str, Any],
        manager: PhaseExecutionManager
    ) -> Dict[str, Any]:
        """
        Use the copilot_control agent to dynamically analyze the task.

        This replaces simple heuristics with LLM-based analysis for:
        - Route type (one_shot, planned, clarify)
        - Agent selection
        - Complexity scoring
        - Task refinement

        Returns:
            Dictionary with routing decision fields
        """
        # Use shared CMBAgent session
        cmbagent = self._get_or_create_cmbagent_session(context)

        # Build agent info string for the prompt
        agent_info_lines = []
        for agent_name in self.config.available_agents:
            agent_info_lines.append(f"- **{agent_name}**: Available for tasks")
        available_agents_info = "\n".join(agent_info_lines) if agent_info_lines else "- engineer: Code and technical tasks\n- researcher: Research and analysis"

        try:
            # Build context for the control agent
            shared_context = copy.deepcopy(current_context)
            shared_context['available_agents_info'] = available_agents_info
            shared_context['copilot_context'] = json.dumps({
                'previous_turns': len(self._conversation_history),
                'accumulated_feedback': self._accumulated_feedback[:500] if self._accumulated_feedback else '',
                'enable_planning': self.config.enable_planning,
            }, indent=2)

            # Run the control agent
            cmbagent.solve(
                task=f"Analyze this task and decide how to route it:\n\n{task}",
                initial_agent='copilot_control',
                max_rounds=3,  # Quick decision
                shared_context=shared_context,
            )

            # Extract routing decision from context
            final_context = cmbagent.final_context
            routing_decision = final_context.get('copilot_routing_decision', {})

            if routing_decision:
                logger.info("Dynamic Routing Decision:")
                logger.info("  Route: %s", routing_decision.get('route_type', 'unknown'))
                logger.info("  Complexity: %s/100", routing_decision.get('complexity_score', 'N/A'))
                logger.info("  Primary Agent: %s", routing_decision.get('primary_agent', 'engineer'))
                logger.info("  Confidence: %.0f%%", routing_decision.get('confidence', 0) * 100)
                return routing_decision

        except Exception as e:
            logger.warning("Dynamic routing failed: %s", e)
            logger.info("Falling back to heuristic analysis")

        # Fallback: return heuristic-based decision
        complexity, reasoning = self._analyze_complexity(task)
        primary_agent = self._select_primary_agent(task)

        return {
            'route_type': 'planned' if complexity == 'complex' else 'one_shot',
            'complexity_score': 70 if complexity == 'complex' else 25,
            'complexity_reasoning': reasoning,
            'primary_agent': primary_agent,
            'supporting_agents': [],
            'agent_reasoning': 'Heuristic fallback',
            'estimated_steps': 3 if complexity == 'complex' else 1,
            'clarifying_questions': [],
            'refined_task': task,
            'confidence': 0.6,
        }

    async def _request_clarification(
        self,
        questions: List[str],
        approval_manager,
        context: PhaseContext,
        manager: PhaseExecutionManager
    ) -> Optional[str]:
        """
        Request clarification from the user when the task is ambiguous.

        Args:
            questions: List of clarifying questions to ask
            approval_manager: HITL approval manager
            context: Phase context
            manager: Execution manager

        Returns:
            Clarified task description, or None if user cancels
        """
        questions_str = "\n".join(f"- {q}" for q in questions)

        message = f"""## Clarification Needed

The copilot needs more information to properly handle your request.

**Questions:**
{questions_str}

Please provide more details or clarify your request.
"""

        request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_clarification",
            checkpoint_type="clarification",
            context_snapshot={
                'questions': questions,
                'requires_text_input': True,  # Flag for UI to show text input
                'input_placeholder': 'Enter your clarification...',
            },
            message=message,
            options=["submit", "cancel"],  # Changed from provide_info to submit
        )

        logger.info("Waiting for user clarification...")

        try:
            resolved = await approval_manager.wait_for_approval_async(
                str(request.id),
                timeout_seconds=1800,
            )

            if resolved.resolution == "cancel":
                return None

            # User feedback contains the clarification
            return resolved.user_feedback if hasattr(resolved, 'user_feedback') else None

        except Exception as e:
            logger.error("Clarification request failed: %s", e)
            return None

    async def _execute_one_shot(
        self,
        context: PhaseContext,
        task: str,
        current_context: Dict[str, Any],
        manager: PhaseExecutionManager,
        primary_agent: str = None
    ) -> Dict[str, Any]:
        """Execute task directly without planning (one-shot mode)."""
        # Use shared CMBAgent session
        cmbagent = self._get_or_create_cmbagent_session(context)

        # Use provided agent or select based on task
        if primary_agent is None:
            primary_agent = self._select_primary_agent(task)

        logger.info("Using agent: %s", primary_agent)

        # Build instructions with any accumulated feedback
        shared_context = copy.deepcopy(current_context)

        if self._accumulated_feedback:
            shared_context['engineer_append_instructions'] = (
                self.config.engineer_instructions +
                f"\n\n## Previous Feedback\n{self._accumulated_feedback}"
            )
            shared_context['researcher_append_instructions'] = (
                self.config.researcher_instructions +
                f"\n\n## Previous Feedback\n{self._accumulated_feedback}"
            )
        else:
            shared_context['engineer_append_instructions'] = self.config.engineer_instructions
            shared_context['researcher_append_instructions'] = self.config.researcher_instructions

        # Execute
        cmbagent.solve(
            task=task,
            initial_agent=primary_agent,
            max_rounds=self.config.max_rounds,
            shared_context=shared_context,
        )

        # Extract result
        final_context = cmbagent.final_context

        # Get summary from chat history
        summary = ""
        if hasattr(cmbagent, 'chat_result') and cmbagent.chat_result:
            for msg in reversed(cmbagent.chat_result.chat_history or []):
                if msg.get('role') == 'assistant' and msg.get('content'):
                    summary = msg['content'][:500]
                    break

        return {
            'success': True,
            'final_context': final_context,
            'summary': summary,
            'agent_used': primary_agent,
        }

    async def _execute_with_planning(
        self,
        context: PhaseContext,
        task: str,
        current_context: Dict[str, Any],
        approval_manager,
        manager: PhaseExecutionManager
    ) -> Dict[str, Any]:
        """Execute task with planning phase first."""
        from cmbagent.agents.planner_response_formatter.planner_response_formatter import save_final_plan

        # Use shared CMBAgent session
        cmbagent = self._get_or_create_cmbagent_session(context)

        # ============ PLANNING PHASE ============
        logger.info("--- Planning Phase ---")

        # Inject available agents into planner instructions
        available_agents_str = ", ".join(self.config.available_agents)
        planner_instructions = (
            f"{self.config.planner_instructions}\n\n"
            f"## Available Agents\n"
            f"You can ONLY assign tasks to these agents: {available_agents_str}\n"
            f"Do NOT use any other agents."
        )

        # Run planning
        cmbagent.solve(
            task=task,
            initial_agent='plan_setter',
            max_rounds=self.config.max_rounds,
            shared_context={
                'maximum_number_of_steps_in_plan': self.config.max_plan_steps,
                'planner_append_instructions': planner_instructions,
                'available_agents': self.config.available_agents,
                **current_context,
            }
        )

        planning_context = cmbagent.final_context

        # Extract plan
        plan = self._extract_plan(planning_context, self._cmbagent_work_dir)

        if not plan:
            return {
                'success': False,
                'error': 'Failed to generate plan',
                'final_context': planning_context,
            }

        logger.info("Generated plan with %d steps", len(plan))
        for i, step in enumerate(plan, 1):
            logger.info("  %d. [%s] %s...", i, step.get('sub_task_agent'), step.get('sub_task', '')[:60])

        # ============ HITL PLAN APPROVAL ============
        if approval_manager and self.config.approval_mode != "none":
            approved, plan = await self._request_plan_approval(
                plan, approval_manager, context, manager
            )
            if not approved:
                return {
                    'success': False,
                    'error': 'Plan rejected by user',
                    'plan': plan,
                    'final_context': planning_context,
                }

        # ============ EXECUTION PHASE ============
        logger.info("--- Execution Phase ---")

        step_results = []
        step_summaries = []
        execution_context = copy.deepcopy(planning_context)

        for step_num, step in enumerate(plan, 1):
            manager.raise_if_cancelled()

            step_agent = step.get('sub_task_agent', 'engineer')
            step_task = step.get('sub_task', '')

            logger.info("Step %d/%d: %s...", step_num, len(plan), step_task[:60])
            logger.info("  Agent: %s", step_agent)

            # Before-step approval
            if self.config.approval_mode in ["before_step", "both"]:
                if approval_manager:
                    proceed = await self._request_step_approval(
                        step, step_num, approval_manager, context, manager
                    )
                    if not proceed:
                        logger.info("  Skipped by user")
                        continue

            # Execute step using shared CMBAgent session
            starter_agent = "control" if step_num == 1 else "control_starter"

            step_shared = copy.deepcopy(execution_context)
            step_shared['current_plan_step_number'] = step_num
            step_shared['agent_for_sub_task'] = step_agent
            step_shared['engineer_append_instructions'] = self.config.engineer_instructions
            step_shared['researcher_append_instructions'] = self.config.researcher_instructions

            if self._accumulated_feedback:
                step_shared['engineer_append_instructions'] += (
                    f"\n\n## Human Feedback\n{self._accumulated_feedback}"
                )

            try:
                cmbagent.solve(
                    task=task,
                    initial_agent=starter_agent,
                    max_rounds=self.config.max_rounds,
                    shared_context=step_shared,
                    step=step_num,
                )

                step_result = cmbagent.final_context
                success = True

                # Extract step summary
                summary = self._extract_step_summary(cmbagent, step_agent, step_num)
                step_summaries.append(summary)

                execution_context = copy.deepcopy(step_result)
                execution_context['previous_steps_execution_summary'] = _truncate_step_summaries(step_summaries)

            except Exception as e:
                success = False
                step_result = {'error': str(e)}
                logger.error("  Error: %s", e)

            step_results.append({
                'step': step_num,
                'task': step_task,
                'agent': step_agent,
                'success': success,
                'result': step_result,
            })

            # After-step approval
            if self.config.approval_mode in ["after_step", "both"]:
                if approval_manager and success:
                    feedback = await self._request_step_review(
                        step, step_num, step_result, approval_manager, context, manager
                    )
                    if feedback:
                        self._accumulated_feedback += f"\n\nStep {step_num} feedback: {feedback}"

            logger.info("  %s", 'Completed' if success else 'Failed')

        # Build final summary
        final_summary = "\n\n".join(step_summaries) if step_summaries else "No results"

        return {
            'success': all(r['success'] for r in step_results),
            'plan': plan,
            'step_results': step_results,
            'final_context': execution_context,
            'summary': final_summary,
        }

    def _build_agent_configs(self, api_keys: Dict[str, str]) -> Dict[str, Any]:
        """Build agent LLM configs for available agents only."""
        configs = {}

        for agent in self.config.available_agents:
            if agent == 'engineer':
                configs['engineer'] = get_model_config(self.config.engineer_model, api_keys)
            elif agent == 'researcher':
                configs['researcher'] = get_model_config(self.config.researcher_model, api_keys)
            else:
                # Use engineer model as default for other agents
                configs[agent] = get_model_config(self.config.engineer_model, api_keys)

        return configs

    def _select_primary_agent(self, task: str) -> str:
        """Select the most appropriate agent for a one-shot task."""
        task_lower = task.lower()

        # Research-oriented keywords
        research_keywords = [
            'search', 'find', 'research', 'look up', 'what is', 'explain',
            'summarize', 'analyze', 'compare', 'review', 'investigate'
        ]

        if any(kw in task_lower for kw in research_keywords):
            if 'researcher' in self.config.available_agents:
                return 'researcher'

        # Default to engineer
        if 'engineer' in self.config.available_agents:
            return 'engineer'

        # Fallback to first available agent
        return self.config.available_agents[0] if self.config.available_agents else 'engineer'

    def _extract_plan(self, planning_context: Dict, planning_dir: str) -> List[Dict]:
        """Extract plan from planning context."""
        raw_plan = planning_context.get('final_plan', planning_context.get('plan'))

        if not raw_plan:
            # Try loading from file
            plan_file = os.path.join(planning_dir, 'final_plan.json')
            if os.path.exists(plan_file):
                with open(plan_file, 'r') as f:
                    plan_dict = json.load(f)
                return plan_dict.get('sub_tasks', [])
            return []

        # Handle different formats
        if hasattr(raw_plan, 'model_dump'):
            plan_dict = raw_plan.model_dump()
            return plan_dict.get('sub_tasks', [])
        elif hasattr(raw_plan, 'dict'):
            plan_dict = raw_plan.dict()
            return plan_dict.get('sub_tasks', [])
        elif isinstance(raw_plan, dict):
            return raw_plan.get('sub_tasks', raw_plan.get('steps', []))
        elif isinstance(raw_plan, list):
            return raw_plan

        return []

    def _extract_step_summary(self, cmbagent, agent_name: str, step_num: int) -> str:
        """Extract summary from step execution."""
        if not hasattr(cmbagent, 'chat_result') or not cmbagent.chat_result:
            return f"### Step {step_num}\nCompleted."

        for msg in reversed(cmbagent.chat_result.chat_history or []):
            if msg.get('name') and agent_name in msg.get('name', ''):
                return f"### Step {step_num}\n{msg.get('content', 'Completed.')[:500]}"

        return f"### Step {step_num}\nCompleted."

    async def _request_plan_approval(
        self,
        plan: List[Dict],
        approval_manager,
        context: PhaseContext,
        manager: PhaseExecutionManager
    ) -> Tuple[bool, List[Dict]]:
        """Request HITL approval for generated plan."""
        plan_display = self._format_plan_for_display(plan)

        message = f"""## Generated Plan

{plan_display}

**Options:**
- **Approve**: Execute this plan
- **Reject**: Cancel and provide different instructions
- **Modify**: Edit the plan before execution
"""

        request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_plan_approval",
            checkpoint_type="plan_approval",
            context_snapshot={'plan': plan},
            message=message,
            options=["approve", "reject", "modify"],
        )

        logger.info("Waiting for plan approval...")

        resolved = await approval_manager.wait_for_approval_async(
            str(request.id),
            timeout_seconds=1800,
        )

        if resolved.resolution in ["approved", "approve"]:
            if resolved.user_feedback:
                self._accumulated_feedback += f"\nPlan approval note: {resolved.user_feedback}"
            return True, plan
        elif resolved.resolution in ["modified", "modify"]:
            modified_plan = resolved.modifications.get('plan', plan)
            return True, modified_plan
        else:
            return False, plan

    async def _request_step_approval(
        self,
        step: Dict,
        step_num: int,
        approval_manager,
        context: PhaseContext,
        manager: PhaseExecutionManager
    ) -> bool:
        """Request approval before executing a step."""
        message = f"""## Step {step_num} Approval

**Task:** {step.get('sub_task', 'Unknown')}
**Agent:** {step.get('sub_task_agent', 'engineer')}

Approve execution of this step?
"""

        request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}",
            checkpoint_type="before_step",
            context_snapshot={'step': step, 'step_num': step_num},
            message=message,
            options=["approve", "skip"],
        )

        resolved = await approval_manager.wait_for_approval_async(
            str(request.id),
            timeout_seconds=1800,
        )

        return resolved.resolution in ["approved", "approve"]

    async def _request_step_review(
        self,
        step: Dict,
        step_num: int,
        result: Dict,
        approval_manager,
        context: PhaseContext,
        manager: PhaseExecutionManager
    ) -> Optional[str]:
        """Request review after step execution, return feedback if any."""
        message = f"""## Step {step_num} Review

**Task:** {step.get('sub_task', 'Unknown')}
**Status:** Completed

Provide feedback or continue to next step.
"""

        request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_step_{step_num}_review",
            checkpoint_type="after_step",
            context_snapshot={'step': step, 'step_num': step_num},
            message=message,
            options=["continue", "redo"],
        )

        resolved = await approval_manager.wait_for_approval_async(
            str(request.id),
            timeout_seconds=1800,
        )

        return resolved.user_feedback if hasattr(resolved, 'user_feedback') else None

    async def _get_next_task(
        self,
        context: PhaseContext,
        last_result: Dict,
        approval_manager,
        manager: PhaseExecutionManager
    ) -> Optional[str]:
        """Get next task from user in continuous mode."""
        if not approval_manager:
            # Console fallback
            logger.info("=" * 60)
            response = input("Next task (or 'exit' to quit): ").strip()
            return response if response else None

        # Format last result summary for context
        last_summary = last_result.get('summary', 'Task completed.')
        if isinstance(last_summary, dict):
            last_summary = last_summary.get('summary', 'Task completed.')

        message = f"""## Ready for Next Task

**Last Result:** {last_summary[:500] if last_summary else 'Completed'}

What would you like to do next? Enter your task below:
"""

        # Create request with requires_text_input flag for the UI
        request = approval_manager.create_approval_request(
            run_id=context.run_id,
            step_id=f"{context.phase_id}_next_task",
            checkpoint_type="chat_input",  # Special type for chat input
            context_snapshot={
                'last_result': last_summary,
                'turn': len(self._conversation_history),
                'requires_text_input': True,  # Flag for UI
                'input_placeholder': 'Enter your next task...',
            },
            message=message,
            options=["submit", "exit"],  # submit = has text, exit = end session
        )

        resolved = await approval_manager.wait_for_approval_async(
            str(request.id),
            timeout_seconds=3600,
        )

        if resolved.resolution == "exit" or resolved.resolution == "reject":
            return None

        # User feedback contains the next task
        next_task = resolved.user_feedback if hasattr(resolved, 'user_feedback') else None
        if next_task and next_task.lower().strip() in ['exit', 'quit', 'done', 'bye']:
            return None

        return next_task

    def _format_plan_for_display(self, plan: List[Dict]) -> str:
        """Format plan for human-readable display."""
        if not plan:
            return "(No steps)"

        lines = []
        for i, step in enumerate(plan, 1):
            agent = step.get('sub_task_agent', 'engineer')
            task = step.get('sub_task', 'Unknown task')
            lines.append(f"**Step {i}** [{agent}]: {task}")

            bullet_points = step.get('bullet_points', [])
            for bp in bullet_points[:3]:
                lines.append(f"   - {bp}")

        return "\n".join(lines)
