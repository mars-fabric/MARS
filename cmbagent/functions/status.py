"""Status tracking functionality."""

import os
import logging
import structlog
from typing import Literal
from autogen import register_function
from autogen.agentchat.group import ContextVariables, AgentTarget, ReplyResult
from IPython.display import Image as IPImage, display as ip_display
from ..cmbagent_utils import IMG_WIDTH, cmbagent_disable_display, cmbagent_debug
from .utils import load_docstrings, load_plots

logger = structlog.get_logger(__name__)


def record_status(
    current_status: Literal["in progress", "failed", "completed"],
    current_plan_step_number: int,
    current_sub_task: str,
    current_instructions: str,
    agent_for_sub_task: Literal["engineer", "researcher", "idea_maker", "idea_hater",
                                "camb_context", "classy_context", "aas_keyword_finder"],
    context_variables: ContextVariables,
    cmbagent_instance
) -> ReplyResult:
    """
    Updates the execution context and returns the current progress.
    Must be called **before calling the agent in charge of the next sub-task**.
    Must be called **after** each action taken.

    Args:
        current_status (str): The current status ("in progress", "failed", or "completed").
        current_plan_step_number (int): The current step number in the plan.
        current_sub_task (str): Description of the current sub-task.
        current_instructions (str): Instructions for the sub-task.
        agent_for_sub_task (str): The agent responsible for the sub-task in the current step. Stays the same for the whole step.
        context_variables (dict): Execution context dictionary.

    Returns:
        ReplyResult: Contains a formatted status message and updated context.
    """
    control = cmbagent_instance.get_agent_from_name('control')
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    admin = cmbagent_instance.get_agent_from_name('admin')

    if cmbagent_instance.mode == "chat":
        return _record_status_chat_mode(
            current_status, current_plan_step_number, current_sub_task, current_instructions,
            agent_for_sub_task, context_variables, cmbagent_instance, control, terminator, admin
        )
    else:
        return _record_status_default_mode(
            current_status, current_plan_step_number, current_sub_task, current_instructions,
            agent_for_sub_task, context_variables, cmbagent_instance, control, terminator, admin
        )


def _record_status_chat_mode(current_status, current_plan_step_number, current_sub_task, current_instructions,
                             agent_for_sub_task, context_variables, cmbagent_instance, control, terminator, admin):
    """Handle record_status for chat mode."""
    # Map statuses to icons
    status_icons = {
        "completed": "✅",
        "failed": "❌",
        "in progress": "⏳"
    }

    icon = status_icons.get(current_status, "")

    context_variables["current_plan_step_number"] = current_plan_step_number
    context_variables["current_sub_task"] = current_sub_task
    context_variables["agent_for_sub_task"] = agent_for_sub_task
    context_variables["current_instructions"] = current_instructions
    context_variables["current_status"] = current_status

    codes = os.path.join(cmbagent_instance.work_dir, context_variables['codebase_path'])
    docstrings = load_docstrings(codes)

    output_str = ""
    for module, info in docstrings.items():
        output_str += "-----------\n"
        output_str += f"Filename: {module}.py\n"
        output_str += f"File path: {info['file_path']}\n\n"

        if "error" in info:
            output_str += f"⚠️  Parse error: {info['error']}\n\n"

        output_str += "Available functions:\n"

        if info["functions"]:
            for func, doc in info["functions"].items():
                output_str += f"function name: {func}\n"
                output_str += "````\n"
                output_str += f"{doc or '(no docstring)'}\n"
                output_str += "````\n\n"
        else:
            output_str += "(none)\n\n"

    context_variables["current_codebase"] = output_str

    # Load image plots from the "data" directory.
    data_directory = os.path.join(cmbagent_instance.work_dir, context_variables['database_path'])
    image_files = load_plots(data_directory)

    # Retrieve the list of images that have been displayed so far.
    displayed_images = context_variables.get("displayed_images", [])

    # Identify new images that haven't been displayed before.
    new_images = [img for img in image_files if img not in displayed_images]

    # Display only the new images.
    for img_file in new_images:
        if not cmbagent_disable_display:
            ip_display(IPImage(filename=img_file, width=2 * IMG_WIDTH))
        else:
            logger.info("image_saved", path=img_file)

    # Update the context to include the newly displayed images.
    context_variables["displayed_images"] = displayed_images + new_images

    context_variables["transfer_to_engineer"] = False
    context_variables["transfer_to_researcher"] = False
    context_variables["transfer_to_camb_agent"] = False
    context_variables["transfer_to_camb_context"] = False
    context_variables["transfer_to_classy_context"] = False
    context_variables["transfer_to_planck_agent"] = False
    context_variables["transfer_to_cobaya_agent"] = False
    context_variables["transfer_to_perplexity"] = False
    context_variables["transfer_to_idea_maker"] = False
    context_variables["transfer_to_idea_hater"] = False
    context_variables["transfer_to_classy_sz_agent"] = False

    agent_to_transfer_to = None
    if "in progress" in context_variables["current_status"]:
        _set_transfer_flags(context_variables, agent_for_sub_task)
        agent_to_transfer_to = _get_agent_to_transfer(context_variables, cmbagent_instance)

    if "completed" in context_variables["current_status"]:
        if context_variables["current_plan_step_number"] == context_variables["number_of_steps_in_plan"]:
            agent_to_transfer_to = admin
        else:
            agent_to_transfer_to = admin

        context_variables["n_attempts"] = 0

    if "failed" in context_variables["current_status"]:
        n_attempts = context_variables.get("n_attempts", 0) + 1
        context_variables["n_attempts"] = n_attempts
        max_attempts = context_variables.get("max_n_attempts", 3)

        if n_attempts >= max_attempts:
            # Exceeded retries — treat as completed so we don't loop forever
            logger.warning("max_retries_exceeded_chat",
                           agent=context_variables["agent_for_sub_task"],
                           attempts=n_attempts)
            context_variables["current_status"] = "completed"
            agent_to_transfer_to = admin
        elif context_variables["agent_for_sub_task"] == "engineer":
            agent_to_transfer_to = cmbagent_instance.get_agent_from_name('engineer')
        elif context_variables["agent_for_sub_task"] == "researcher":
            # Route to 'researcher' (not 'researcher_response_formatter') so the
            # full chain runs again with fresh messages, avoiding the empty-message
            # edge case in MessageHistoryLimiter.
            agent_to_transfer_to = cmbagent_instance.get_agent_from_name('researcher')

    if cmbagent_debug:
        if agent_to_transfer_to is None:
            logger.debug("agent_transfer_target", target="None")
        else:
            logger.debug("agent_transfer_target", target=agent_to_transfer_to.name)

    return _create_reply_result(agent_to_transfer_to, control, context_variables, icon)


def _record_status_default_mode(current_status, current_plan_step_number, current_sub_task, current_instructions,
                                agent_for_sub_task, context_variables, cmbagent_instance, control, terminator, admin):
    """Handle record_status for default mode."""
    # Map statuses to icons
    status_icons = {
        "completed": "✅",
        "failed": "❌",
        "in progress": "⏳"
    }

    icon = status_icons.get(current_status, "")

    context_variables["current_plan_step_number"] = current_plan_step_number
    context_variables["current_sub_task"] = current_sub_task
    context_variables["agent_for_sub_task"] = agent_for_sub_task
    context_variables["current_instructions"] = current_instructions
    context_variables["current_status"] = current_status

    codes = os.path.join(cmbagent_instance.work_dir, context_variables['codebase_path'])
    docstrings = load_docstrings(codes)

    output_str = ""
    for module, info in docstrings.items():
        output_str += "-----------\n"
        output_str += f"Filename: {module}.py\n"
        output_str += f"File path: {info['file_path']}\n\n"

        if "error" in info:
            output_str += f"⚠️  Parse error: {info['error']}\n\n"

        output_str += "Available functions:\n"

        if info["functions"]:
            for func, doc in info["functions"].items():
                output_str += f"function name: {func}\n"
                output_str += "````\n"
                output_str += f"{doc or '(no docstring)'}\n"
                output_str += "````\n\n"
        else:
            output_str += "(none)\n\n"

    context_variables["current_codebase"] = output_str

    # Load image plots from the "data" directory.
    data_directory = os.path.join(cmbagent_instance.work_dir, context_variables['database_path'])
    image_files = load_plots(data_directory)

    # Retrieve the list of images that have been displayed so far.
    displayed_images = context_variables.get("displayed_images", [])

    # Identify new images that haven't been displayed before.
    new_images = [img for img in image_files if img not in displayed_images]

    # Display only the new images.
    for img_file in new_images:
        if not cmbagent_disable_display:
            ip_display(IPImage(filename=img_file, width=2 * IMG_WIDTH))
        else:
            logger.info("image_saved", path=img_file)

    # Update the context to include the newly displayed images.
    context_variables["displayed_images"] = displayed_images + new_images

    context_variables["transfer_to_engineer"] = False
    context_variables["transfer_to_researcher"] = False
    context_variables["transfer_to_camb_agent"] = False
    context_variables["transfer_to_cobaya_agent"] = False
    context_variables["transfer_to_perplexity"] = False
    context_variables["transfer_to_idea_maker"] = False
    context_variables["transfer_to_idea_hater"] = False
    context_variables["transfer_to_classy_sz_agent"] = False
    context_variables["transfer_to_camb_context"] = False
    context_variables["transfer_to_classy_context"] = False
    context_variables["transfer_to_planck_agent"] = False

    agent_to_transfer_to = None
    if "in progress" in context_variables["current_status"]:
        _set_transfer_flags(context_variables, agent_for_sub_task)
        agent_to_transfer_to = _get_agent_to_transfer(context_variables, cmbagent_instance)

        if cmbagent_instance.mode == "planning_and_control_context_carryover" and context_variables["current_plan_step_number"] != cmbagent_instance.step:
            agent_to_transfer_to = terminator

    if "completed" in context_variables["current_status"]:
        if context_variables["current_plan_step_number"] == context_variables["number_of_steps_in_plan"]:
            agent_to_transfer_to = terminator
        else:
            agent_to_transfer_to = control
            if cmbagent_instance.mode != "planning_and_control_context_carryover":
                context_variables["n_attempts"] = 0

    if "failed" in context_variables["current_status"]:
        n_attempts = context_variables.get("n_attempts", 0) + 1
        context_variables["n_attempts"] = n_attempts
        max_attempts = context_variables.get("max_n_attempts", 3)

        if n_attempts >= max_attempts:
            # Exceeded retries — treat as completed so we don't loop forever
            logger.warning("max_retries_exceeded_default",
                           agent=context_variables["agent_for_sub_task"],
                           attempts=n_attempts)
            context_variables["current_status"] = "completed"
            agent_to_transfer_to = terminator
        elif context_variables["agent_for_sub_task"] == "engineer":
            agent_to_transfer_to = cmbagent_instance.get_agent_from_name('engineer')
        elif context_variables["agent_for_sub_task"] == "researcher":
            # Route to 'researcher' (not 'researcher_response_formatter') so the
            # full chain runs again with fresh messages, avoiding the empty-message
            # edge case in MessageHistoryLimiter.
            agent_to_transfer_to = cmbagent_instance.get_agent_from_name('researcher')

    if cmbagent_debug:
        if agent_to_transfer_to is None:
            logger.debug("agent_transfer_target", target="None")
        else:
            logger.debug("agent_transfer_target", target=agent_to_transfer_to.name)

    return _create_reply_result(agent_to_transfer_to, control, context_variables, icon)


def _set_transfer_flags(context_variables, agent_for_sub_task):
    """Set transfer flags based on agent_for_sub_task."""
    agent_mapping = {
        "engineer": "transfer_to_engineer",
        "researcher": "transfer_to_researcher",
        "camb_agent": "transfer_to_camb_agent",
        "cobaya_agent": "transfer_to_cobaya_agent",
        "perplexity": "transfer_to_perplexity",
        "idea_maker": "transfer_to_idea_maker",
        "idea_hater": "transfer_to_idea_hater",
        "classy_sz_agent": "transfer_to_classy_sz_agent",
        "planck_agent": "transfer_to_planck_agent",
        "camb_context": "transfer_to_camb_context",
        "classy_context": "transfer_to_classy_context",
    }

    flag = agent_mapping.get(agent_for_sub_task)
    if flag:
        context_variables[flag] = True


def _get_agent_to_transfer(context_variables, cmbagent_instance):
    """Get the agent to transfer to based on context_variables flags."""
    agent_flags = [
        ("transfer_to_engineer", 'engineer'),
        ("transfer_to_researcher", 'researcher'),
        ("transfer_to_camb_agent", 'camb_agent'),
        ("transfer_to_cobaya_agent", 'cobaya_agent'),
        ("transfer_to_perplexity", 'perplexity'),
        ("transfer_to_idea_maker", 'idea_maker'),
        ("transfer_to_idea_hater", 'idea_hater'),
        ("transfer_to_classy_sz_agent", 'classy_sz_agent'),
        ("transfer_to_planck_agent", 'planck_agent'),
        ("transfer_to_camb_context", 'camb_context'),
        ("transfer_to_classy_context", 'classy_context'),
    ]

    for flag, agent_name in agent_flags:
        if context_variables.get(flag):
            return cmbagent_instance.get_agent_from_name(agent_name)

    return None


def _create_reply_result(agent_to_transfer_to, control, context_variables, icon):
    """Create the ReplyResult with formatted message."""
    message = f"""
**Step number:** {context_variables["current_plan_step_number"]} out of {context_variables["number_of_steps_in_plan"]}.\n
**Sub-task:** {context_variables["current_sub_task"]}\n
**Agent in charge of sub-task:** `{context_variables["agent_for_sub_task"]}`\n
**Instructions:**\n
{context_variables["current_instructions"]}\n
**Status:** {context_variables["current_status"]} {icon}
"""

    if agent_to_transfer_to is None:
        return ReplyResult(
            target=AgentTarget(control),
            message=message,
            context_variables=context_variables
        )
    else:
        return ReplyResult(
            target=AgentTarget(agent_to_transfer_to),
            message=message,
            context_variables=context_variables
        )


def record_status_starter(context_variables: ContextVariables, cmbagent_instance) -> ReplyResult:
    """
    Updates the execution context and returns the current progress.
    Must be called **before calling the agent in charge of the next sub-task**.
    Must be called **after** each action taken.

    Args:
        context_variables (dict): Execution context dictionary.

    Returns:
        ReplyResult: Contains a formatted status message and updated context.
    """
    current_status = "in progress"

    # Map statuses to icons
    status_icons = {
        "completed": "✅",
        "failed": "❌",
        "in progress": "⏳"
    }

    icon = status_icons.get(current_status, "")
    context_variables["current_status"] = current_status

    context_variables["transfer_to_engineer"] = False
    context_variables["transfer_to_researcher"] = False
    context_variables["transfer_to_camb_agent"] = False
    context_variables["transfer_to_cobaya_agent"] = False
    context_variables["transfer_to_perplexity"] = False
    context_variables["transfer_to_idea_maker"] = False
    context_variables["transfer_to_idea_hater"] = False
    context_variables["transfer_to_classy_sz_agent"] = False
    context_variables["transfer_to_camb_context"] = False
    context_variables["transfer_to_classy_context"] = False
    context_variables["transfer_to_planck_agent"] = False

    agent_to_transfer_to = None
    if "in progress" in context_variables["current_status"]:
        _set_transfer_flags(context_variables, context_variables["agent_for_sub_task"])
        agent_to_transfer_to = _get_agent_to_transfer(context_variables, cmbagent_instance)

    return ReplyResult(
        target=AgentTarget(agent_to_transfer_to),
        message=f"""
**Step number:** {context_variables["current_plan_step_number"]} out of {context_variables["number_of_steps_in_plan"]}.\n
**Sub-task:** {context_variables["current_sub_task"]}\n
**Agent in charge of sub-task:** `{context_variables["agent_for_sub_task"]}`\n
**Instructions:**\n
{context_variables["current_instructions"]}\n
**Status:** {context_variables["current_status"]} {icon}
""",
        context_variables=context_variables
    )


def setup_status_functions(cmbagent_instance):
    """Register status tracking functions with the appropriate agents."""
    control = cmbagent_instance.get_agent_from_name('control')
    control_starter = cmbagent_instance.get_agent_from_name('control_starter')

    # Create closures to bind cmbagent_instance
    def record_status_closure(
        current_status: Literal["in progress", "failed", "completed"],
        current_plan_step_number: int,
        current_sub_task: str,
        current_instructions: str,
        agent_for_sub_task: Literal["engineer", "researcher", "idea_maker", "idea_hater",
                                    "camb_context", "classy_context", "aas_keyword_finder"],
        context_variables: ContextVariables
    ) -> ReplyResult:
        return record_status(current_status, current_plan_step_number, current_sub_task,
                           current_instructions, agent_for_sub_task, context_variables, cmbagent_instance)

    def record_status_starter_closure(context_variables: ContextVariables) -> ReplyResult:
        return record_status_starter(context_variables, cmbagent_instance)

    register_function(
        record_status_closure,
        caller=control,
        executor=control,
        description=r"""
        Updates the context and returns the current progress.
        Must be called **before calling the agent in charge of the next sub-task**.
        Must be called **after** each action taken.

        Args:
            current_status (str): The current status ("in progress", "failed", or "completed").
            current_plan_step_number (int): The current step number in the plan.
            current_sub_task (str): Description of the current sub-task.
            current_instructions (str): Instructions for the sub-task.
            agent_for_sub_task (str): The agent responsible for the sub-task.
            context_variables (dict): context dictionary.

        Returns:
            ReplyResult: Contains a formatted status message and updated context.
        """,
    )

    register_function(
        record_status_starter_closure,
        caller=control_starter,
        executor=control_starter,
        description=r"""
        Updates the context and returns the current progress.
        Must be called **before calling the agent in charge of the next sub-task**.
        Must be called **after** each action taken.

        Args:
            context_variables (dict): context dictionary.

        Returns:
            ReplyResult: Contains a formatted status message and updated context.
        """,
    )
