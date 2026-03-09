"""Planning workflow functionality."""

import logging
import structlog
from typing import Literal, List
from autogen import register_function
from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult, TerminateTarget
from IPython.display import Markdown, display

logger = structlog.get_logger(__name__)


def record_improved_task(improved_main_task: str, context_variables: ContextVariables, cmbagent_instance, cmbagent_disable_display: bool) -> ReplyResult:
    """Records the improved main task."""
    planner = cmbagent_instance.get_agent_from_name('planner')
    context_variables["improved_main_task"] = improved_main_task

    if not cmbagent_disable_display:
        display(Markdown(improved_main_task))
    else:
        logger.info("improved_task_recorded", task_preview=improved_main_task[:200])

    return ReplyResult(
        target=AgentTarget(planner),  ## transfer to planner
        message="Improved main task has been logged. Now, suggest a plan, planner!",
        context_variables=context_variables
    )


def record_plan(plan_suggestion: str, number_of_steps_in_plan: int, context_variables: ContextVariables, cmbagent_instance) -> ReplyResult:
    """
    Records a suggested plan and updates relevant execution context.

    This function logs a full plan suggestion into the `context_variables` dictionary. If no feedback
    remains to be given (i.e., `context_variables["feedback_left"] == 0`), the most recent plan
    suggestion is marked as the final plan. The function also updates the total number of steps in
    the plan.

    The function ensures that the plan is properly stored and transferred to the `plan_reviewer` agent
    for further evaluation.

    Args:
        plan_suggestion (str): The complete plan suggestion to be recorded. Unaltered, as it is, preserve capitalization and ponctuation.
        number_of_steps_in_plan (int): The total number of **Steps** in the suggested plan, which you read off from the plan suggestion.
        context_variables (dict): A dictionary maintaining execution context, including previous plans,
            feedback tracking, and finalized plans.
    """
    plan_reviewer = cmbagent_instance.get_agent_from_name('plan_reviewer')
    terminator = cmbagent_instance.get_agent_from_name('terminator')

    logger.debug("record_plan_called",
                 feedback_left=context_variables.get('feedback_left', 'MISSING'),
                 num_plans=len(context_variables.get('plans', [])))

    context_variables["plans"].append(plan_suggestion)
    context_variables["proposed_plan"] = plan_suggestion
    context_variables["number_of_steps_in_plan"] = number_of_steps_in_plan

    if context_variables["feedback_left"] <= 0:
        context_variables["final_plan"] = context_variables["plans"][-1]
        return ReplyResult(
            target=AgentTarget(terminator),  ## transfer to control
            message="Planning stage complete. Exiting.",
            context_variables=context_variables
        )
    else:
        return ReplyResult(
            target=AgentTarget(plan_reviewer),  ## transfer to plan reviewer
            message="Plan has been logged.",
            context_variables=context_variables
        )


def record_plan_constraints(needed_agents: List[Literal["engineer", "researcher", "idea_maker", "idea_hater",
                                                         "camb_agent", "camb_context", "classy_context",
                                                         "classy_sz_agent", "planck_agent", "aas_keyword_finder"]],
                            context_variables: ContextVariables, cmbagent_instance) -> ReplyResult:
    """Records the constraints on the plan."""
    planner = cmbagent_instance.get_agent_from_name('planner')

    # Filter out any agents that are not loaded in this cmbagent instance
    valid_agents = []
    skipped_agents = []
    for a in needed_agents:
        if cmbagent_instance.get_agent_from_name(a) is not None:
            valid_agents.append(a)
        else:
            skipped_agents.append(a)
            logger.warning("record_plan_constraints_skipping_unloaded_agent", agent=a)

    if skipped_agents:
        logger.warning("record_plan_constraints_agents_not_loaded", skipped=skipped_agents)

    needed_agents = valid_agents
    context_variables["needed_agents"] = needed_agents

    if not needed_agents:
        logger.error("record_plan_constraints_no_valid_agents", original_agents=skipped_agents)
        return ReplyResult(
            target=AgentTarget(planner),
            message="No valid agents could be loaded for the plan. Proceeding with available agents only.",
            context_variables=context_variables
        )

    str_to_append = f"The plan must strictly involve only the following agents: {', '.join(needed_agents)}\n"

    str_to_append += r"""
**AGENT ROLES**
Here are the descriptions of the agents that are needed to carry out the plan:
"""
    for agent in set(needed_agents):
        agent_object = cmbagent_instance.get_agent_from_name(agent)
        str_to_append += f'- {agent}: {agent_object.description}'

    str_to_append += "\n"
    str_to_append += r"""
You must not invoke any other agent than the ones listed above.
"""
    context_variables["planner_append_instructions"] += str_to_append
    context_variables["plan_reviewer_append_instructions"] += str_to_append

    return ReplyResult(
        target=AgentTarget(planner),
        message="Plan constraints have been logged.",
        context_variables=context_variables
    )


def record_review(plan_review: str, context_variables: ContextVariables, cmbagent_instance) -> ReplyResult:
    """Record reviews of the plan."""
    planner = cmbagent_instance.get_agent_from_name('planner')
    terminator = cmbagent_instance.get_agent_from_name('terminator')

    logger.debug("record_review_called",
                 feedback_left_before=context_variables.get('feedback_left', 'MISSING'))

    context_variables["reviews"].append(plan_review)
    context_variables["feedback_left"] -= 1

    # Guard against going negative
    if context_variables["feedback_left"] < 0:
        context_variables["feedback_left"] = 0

    context_variables["recommendations"] = plan_review

    logger.debug("record_review_updated",
                 feedback_left_after=context_variables.get('feedback_left', 'MISSING'))

    # If no feedback left, terminate instead of going back to planner
    if context_variables["feedback_left"] <= 0:
        logger.debug("record_review_terminating", target="terminator")
        context_variables["final_plan"] = context_variables.get("proposed_plan", context_variables["plans"][-1] if context_variables["plans"] else "")
        return ReplyResult(
            target=AgentTarget(terminator),
            message="Planning stage complete after review. Exiting.",
            context_variables=context_variables
        )

    logger.debug("record_review_continuing", target="planner")
    return ReplyResult(
        target=AgentTarget(planner),  ## transfer back to planner
        message=f"""
Recommendations have been logged.
Number of feedback rounds left: {context_variables["feedback_left"]}.
Now, update the plan accordingly, planner!""",
        context_variables=context_variables
    )


def setup_planning_functions(cmbagent_instance, cmbagent_disable_display: bool):
    """Register planning-related functions with the appropriate agents."""
    task_recorder = cmbagent_instance.get_agent_from_name('task_recorder')
    plan_recorder = cmbagent_instance.get_agent_from_name('plan_recorder')
    plan_setter = cmbagent_instance.get_agent_from_name('plan_setter')
    review_recorder = cmbagent_instance.get_agent_from_name('review_recorder')

    # Create closures to bind cmbagent_instance
    def record_improved_task_closure(improved_main_task: str, context_variables: ContextVariables) -> ReplyResult:
        return record_improved_task(improved_main_task, context_variables, cmbagent_instance, cmbagent_disable_display)

    def record_plan_closure(plan_suggestion: str, number_of_steps_in_plan: int, context_variables: ContextVariables) -> ReplyResult:
        return record_plan(plan_suggestion, number_of_steps_in_plan, context_variables, cmbagent_instance)

    def record_plan_constraints_closure(needed_agents: List[Literal["engineer", "researcher", "idea_maker", "idea_hater",
                                                                     "camb_agent", "camb_context", "classy_context",
                                                                     "classy_sz_agent", "planck_agent", "aas_keyword_finder"]],
                                       context_variables: ContextVariables) -> ReplyResult:
        return record_plan_constraints(needed_agents, context_variables, cmbagent_instance)

    def record_review_closure(plan_review: str, context_variables: ContextVariables) -> ReplyResult:
        return record_review(plan_review, context_variables, cmbagent_instance)

    # Register task recording
    task_recorder._add_single_function(record_improved_task_closure)

    # Register plan recording
    register_function(
        record_plan_closure,
        caller=plan_recorder,
        executor=plan_recorder,
        description=r"""
        Records a suggested plan and updates relevant execution context.

        This function logs a full plan suggestion into the `context_variables` dictionary. If no feedback
        remains to be given (i.e., `context_variables["feedback_left"] == 0`), the most recent plan
        suggestion is marked as the final plan. The function also updates the total number of steps in
        the plan.

        The function ensures that the plan is properly stored and transferred to the `plan_reviewer` agent
        for further evaluation.

        Args:
            plan_suggestion (str): The complete plan suggestion to be recorded.
            number_of_steps_in_plan (int): The total number of **Steps** in the suggested plan.
            context_variables (dict): A dictionary maintaining execution context, including previous plans,
                feedback tracking, and finalized plans.
        """,
    )

    # Register plan constraints
    plan_setter._add_single_function(record_plan_constraints_closure)

    # Register review recording
    register_function(
        record_review_closure,
        caller=review_recorder,
        executor=review_recorder,
        description=r"""
        Records the reviews of the plan.
        """,
    )
