"""Main coordinator for registering all functions to agents."""

import json
import logging
import structlog
from functools import wraps
from ..cmbagent_utils import cmbagent_disable_display
from .ideas import setup_idea_functions
from .keywords import setup_keyword_functions
from .planning import setup_planning_functions
from .execution_control import setup_execution_control_functions
from .status import setup_status_functions
from .copilot import setup_copilot_functions

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Tool output safety wrapper — caps any tool return value so a single call
# (e.g. DirectoryReadTool scanning into .venv / node_modules) cannot inject
# hundreds of thousands of tokens into the group-chat messages.
#
# This wrapper is applied at the executor-registration chokepoint so that
# ALL tools (Interop, CrewAI, LangChain, news, raw callables) pass through
# a single output gate before their return value enters the group chat.
# ---------------------------------------------------------------------------
_MAX_TOOL_OUTPUT_CHARS = 25_000   # ≈ 6 k tokens — preserves research content quality

_DIR_BLACKLIST_FRAGMENTS = (
    '.venv', 'venv/', '__pycache__', 'node_modules', '.git/',
    '.tox', '.mypy_cache', '.pytest_cache', '/dist/', '/build/',
    '.eggs', '.egg-info', '.cache', '.npm', '.yarn',
)


def _cap_output(result_str: str, tool_name: str = "") -> str:
    """Truncate a string result to _MAX_TOOL_OUTPUT_CHARS with 70/30 head/tail."""
    if len(result_str) <= _MAX_TOOL_OUTPUT_CHARS:
        return result_str
    head = int(_MAX_TOOL_OUTPUT_CHARS * 0.70)
    tail = _MAX_TOOL_OUTPUT_CHARS - head
    return (
        result_str[:head]
        + f"\n\n... [output truncated: {len(result_str)} → {_MAX_TOOL_OUTPUT_CHARS} chars"
        + (f" for '{tool_name}'" if tool_name else "")
        + "] ...\n\n"
        + result_str[-tail:]
    )


def _safe_tool_wrapper(tool_func, tool_name: str = ""):
    """Return a version of *tool_func* whose output is size-capped.

    Handles both ``str`` and ``dict`` returns (news tools return dicts that
    AG2 serialises to str via ``str()``).  By converting here we ensure
    compact JSON and a hard char cap before the value enters the chat.
    """
    @wraps(tool_func)
    def _wrapped(*args, **kwargs):
        result = tool_func(*args, **kwargs)

        # --- Convert dict/list to compact JSON string early ---------------
        if isinstance(result, (dict, list)):
            try:
                result = json.dumps(result, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                result = str(result)

        if not isinstance(result, str):
            result = str(result)

        # --- Filter noisy directory entries --------------------------------
        name_lower = tool_name.lower()
        is_dir_tool = any(kw in name_lower for kw in (
            'directory', 'list_dir', 'listdir', 'read_directory',
        ))
        if is_dir_tool:
            lines = result.splitlines()
            lines = [
                l for l in lines
                if not any(bl in l.lower() for bl in _DIR_BLACKLIST_FRAGMENTS)
            ]
            result = "\n".join(lines)

        # --- Hard cap ------------------------------------------------------
        result = _cap_output(result, tool_name)
        return result

    # Preserve AG2 metadata needed for registration
    _wrapped.__name__ = getattr(tool_func, '__name__', tool_name or 'tool')
    _wrapped.__doc__ = getattr(tool_func, '__doc__', '')
    # Carry forward any annotations (AG2 uses these for parameter schemas)
    if hasattr(tool_func, '__annotations__'):
        _wrapped.__annotations__ = tool_func.__annotations__
    return _wrapped


def register_functions_to_agents(cmbagent_instance):
    """
    This function registers the functions to the agents.
    """
    task_recorder = cmbagent_instance.get_agent_from_name('task_recorder')
    task_improver = cmbagent_instance.get_agent_from_name('task_improver')
    planner = cmbagent_instance.get_agent_from_name('planner')
    planner_response_formatter = cmbagent_instance.get_agent_from_name('planner_response_formatter')
    plan_recorder = cmbagent_instance.get_agent_from_name('plan_recorder')
    plan_reviewer = cmbagent_instance.get_agent_from_name('plan_reviewer')
    reviewer_response_formatter = cmbagent_instance.get_agent_from_name('reviewer_response_formatter')
    review_recorder = cmbagent_instance.get_agent_from_name('review_recorder')
    researcher = cmbagent_instance.get_agent_from_name('researcher')
    researcher_response_formatter = cmbagent_instance.get_agent_from_name('researcher_response_formatter')
    web_surfer = cmbagent_instance.get_agent_from_name('web_surfer')
    retrieve_assistant = cmbagent_instance.get_agent_from_name('retrieve_assistant')
    engineer = cmbagent_instance.get_agent_from_name('engineer')
    engineer_response_formatter = cmbagent_instance.get_agent_from_name('engineer_response_formatter')

    executor = cmbagent_instance.get_agent_from_name('executor')
    executor_response_formatter = cmbagent_instance.get_agent_from_name('executor_response_formatter')
    terminator = cmbagent_instance.get_agent_from_name('terminator')
    control = cmbagent_instance.get_agent_from_name('control')
    admin = cmbagent_instance.get_agent_from_name('admin')
    perplexity = cmbagent_instance.get_agent_from_name('perplexity')
    aas_keyword_finder = cmbagent_instance.get_agent_from_name('aas_keyword_finder')
    plan_setter = cmbagent_instance.get_agent_from_name('plan_setter')
    idea_maker = cmbagent_instance.get_agent_from_name('idea_maker')
    installer = cmbagent_instance.get_agent_from_name('installer')
    idea_saver = cmbagent_instance.get_agent_from_name('idea_saver')
    control_starter = cmbagent_instance.get_agent_from_name('control_starter')
    camb_context = cmbagent_instance.get_agent_from_name('camb_context')
    classy_context = cmbagent_instance.get_agent_from_name('classy_context')
    plot_judge = cmbagent_instance.get_agent_from_name('plot_judge')
    plot_debugger = cmbagent_instance.get_agent_from_name('plot_debugger')

    if not cmbagent_instance.skip_rag_agents:
        classy_sz = cmbagent_instance.get_agent_from_name('classy_sz_agent')
        classy_sz_response_formatter = cmbagent_instance.get_agent_from_name('classy_sz_response_formatter')
        camb = cmbagent_instance.get_agent_from_name('camb_agent')
        camb_response_formatter = cmbagent_instance.get_agent_from_name('camb_response_formatter')
        planck = cmbagent_instance.get_agent_from_name('planck_agent')

    # =============================================================================
    # AG2 FREE TOOLS INTEGRATION - Load all free tools from LangChain and CrewAI
    # =============================================================================
    if getattr(cmbagent_instance, 'enable_ag2_free_tools', True):
        try:
            from cmbagent.external_tools.ag2_free_tools import AG2FreeToolsLoader

            logger.info("loading_ag2_free_tools")

            # Initialize the loader
            loader = AG2FreeToolsLoader()

            # Load all free tools (both LangChain and CrewAI)
            all_tools = loader.load_all_free_tools()
            combined_tools = loader.get_combined_tool_list()

            if combined_tools:
                logger.info("ag2_free_tools_loaded", tool_count=len(combined_tools))

                # List of agents that should have access to external tools
                agents_for_tools = [a for a in [
                    planner, researcher, web_surfer, retrieve_assistant, engineer, executor, control, admin,
                    task_recorder, task_improver, plan_recorder, plan_reviewer,
                    review_recorder, installer, idea_maker, idea_saver,
                    camb_context, classy_context, plot_judge, plot_debugger,
                ] if a is not None]

                # Add RAG agents if available
                if not cmbagent_instance.skip_rag_agents:
                    agents_for_tools.extend([classy_sz, camb, planck])

                # Register tools with all agents
                for agent in agents_for_tools:
                    try:
                        for tool in combined_tools:
                            agent.register_for_llm()(tool)
                    except Exception as e:
                        logger.warning("agent_tool_registration_failed", agent=agent.name, error=str(e))

                # Register tools for execution with executor.
                #
                # AG2 Interop Tool objects (Wikipedia, ArXiv, CrewAI tools, etc.)
                # are registered as-is to preserve their internal metadata and
                # AG2's name-matching between register_for_llm ↔ register_for_execution.
                # Their output is capped at the message level by MessageContentTruncator.
                #
                # Raw callables (news tools, duckduckgo, etc.) are wrapped with
                # _safe_tool_wrapper to convert dict→compact JSON + size cap at source.
                try:
                    from autogen.tools.tool import Tool as _AG2Tool
                except ImportError:
                    _AG2Tool = None

                try:
                    for tool in combined_tools:
                        if _AG2Tool is not None and isinstance(tool, _AG2Tool):
                            # AG2 Tool objects: register natively
                            executor.register_for_execution()(tool)
                        else:
                            # Raw callables: wrap for dict→JSON + size cap
                            tool_name = getattr(tool, '__name__', getattr(tool, 'name', str(tool)))
                            wrapped = _safe_tool_wrapper(tool, tool_name)
                            executor.register_for_execution()(wrapped)
                    logger.info("tools_registered_for_execution", tool_count=len(combined_tools), executor="executor")
                except Exception as e:
                    logger.warning("executor_tool_registration_failed", error=str(e))
            else:
                logger.warning("no_ag2_tools_loaded", hint="Install dependencies with: pip install -e '.[external-tools]'")

        except ImportError as e:
            logger.warning("ag2_free_tools_unavailable", error=str(e), hint="pip install -e '.[external-tools]'")
        except Exception as e:
            logger.warning("ag2_free_tools_load_error", error=str(e), action="continuing_without_external_tools")
    else:
        logger.info("ag2_free_tools_disabled")

    # =============================================================================
    # END AG2 FREE TOOLS INTEGRATION
    # =============================================================================

    # =============================================================================
    # MCP CLIENT INTEGRATION - Connect to external MCP servers
    # =============================================================================
    if getattr(cmbagent_instance, 'enable_mcp_client', False) and cmbagent_instance.mcp_tool_integration:
        try:
            logger.info("registering_mcp_tools")

            # Get all discovered MCP tools
            mcp_tools = cmbagent_instance.mcp_client_manager.get_all_tools()

            if mcp_tools:
                logger.info("mcp_tools_discovered", tool_count=len(mcp_tools))

                # Group by server for display
                tools_by_server = {}
                for tool in mcp_tools:
                    server = tool['server_name']
                    if server not in tools_by_server:
                        tools_by_server[server] = []
                    tools_by_server[server].append(tool['name'])

                for server_name, tool_names in tools_by_server.items():
                    logger.debug("mcp_server_tools", server=server_name, tool_count=len(tool_names))

                # List of agents that should have access to MCP tools
                agents_for_mcp = [a for a in [
                    planner, researcher, web_surfer, retrieve_assistant, engineer, executor, control, admin,
                    task_recorder, task_improver, plan_recorder, plan_reviewer,
                    review_recorder, installer, idea_maker, idea_saver,
                    camb_context, classy_context, plot_judge, plot_debugger,
                ] if a is not None]

                # Add RAG agents if available
                if not cmbagent_instance.skip_rag_agents:
                    agents_for_mcp.extend([classy_sz, camb, planck])

                # Register MCP tools with all agents
                total_registered = 0
                for agent in agents_for_mcp:
                    try:
                        count = cmbagent_instance.mcp_tool_integration.register_tools_with_agent(agent)
                        total_registered += count
                    except Exception as e:
                        logger.warning("mcp_agent_tool_registration_failed", agent=agent.name, error=str(e))

                logger.info("mcp_tools_registered", agent_count=len(agents_for_mcp))
            else:
                logger.warning("no_mcp_tools_discovered", hint="Check server configuration")

        except Exception as e:
            logger.warning("mcp_tools_registration_error", error=str(e), action="continuing_without_mcp_tools")
    elif getattr(cmbagent_instance, 'enable_mcp_client', False):
        logger.warning("mcp_client_not_initialized", hint="Check MCP configuration and dependencies")
    # =============================================================================
    # END MCP CLIENT INTEGRATION
    # =============================================================================

    # Register all modular functions
    setup_idea_functions(cmbagent_instance)
    setup_keyword_functions(cmbagent_instance)
    setup_planning_functions(cmbagent_instance, cmbagent_disable_display)
    setup_execution_control_functions(cmbagent_instance)
    setup_status_functions(cmbagent_instance)

    # Register copilot functions (only if copilot_control agent exists)
    try:
        available_agents = getattr(cmbagent_instance, 'copilot_available_agents', None)
        setup_copilot_functions(cmbagent_instance, available_agents)
    except Exception as e:
        # Copilot control agent not present - skip silently
        pass
