"""
Tool adapter to convert CrewAI and LangChain tools to AG2-compatible format.

This module provides adapters to bridge external tool frameworks with AG2 agents.
Uses AG2's native Interoperability module for robust cross-framework tool conversion.
"""

import logging
import structlog
import inspect
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps
import json

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Output size guard — prevents any single tool call from injecting a huge
# string into the group chat messages and blowing the context window.
# ---------------------------------------------------------------------------
_MAX_TOOL_OUTPUT_CHARS = 25_000   # ~6k tokens — preserves research content quality

# Directories that should NEVER appear in file-listing tool output
_DIR_EXCLUDE_PATTERNS = {
    '.venv', 'venv', '__pycache__', 'node_modules', '.git',
    '.tox', '.mypy_cache', '.pytest_cache', 'dist', 'build',
    '.eggs', '*.egg-info', '.cache', '.npm', '.yarn',
}


def _cap_tool_output(result: str, tool_name: str = "") -> str:
    """Truncate a tool result string to stay within context budget."""
    if not isinstance(result, str):
        result = str(result)
    if len(result) <= _MAX_TOOL_OUTPUT_CHARS:
        return result
    head = int(_MAX_TOOL_OUTPUT_CHARS * 0.70)
    tail = _MAX_TOOL_OUTPUT_CHARS - head
    return (
        result[:head]
        + f"\n\n... [output truncated from {len(result)} to {_MAX_TOOL_OUTPUT_CHARS} chars"
        + f" for tool '{tool_name}'] ...\n\n"
        + result[-tail:]
    )


def _filter_directory_output(result: str) -> str:
    """Remove lines referencing excluded directories from directory listing output."""
    if not isinstance(result, str):
        return result
    lines = result.splitlines()
    filtered = []
    for line in lines:
        line_lower = line.lower()
        if any(pat in line_lower for pat in _DIR_EXCLUDE_PATTERNS):
            continue
        filtered.append(line)
    return "\n".join(filtered)

try:
    from autogen.interop import Interoperability
    HAS_INTEROP = True
except ImportError:
    HAS_INTEROP = False
    logger.warning("interop_unavailable", fallback="using custom adapter")


class AG2ToolAdapter:
    """
    Adapter class to convert external tools to AG2-compatible functions.

    AG2 agents use the autogen.register_function API to register tools.
    This adapter converts CrewAI and LangChain tools to match that format.
    """

    def __init__(self, tool_name: str, tool_description: str, tool_function: Callable):
        """
        Initialize the tool adapter.

        Args:
            tool_name: Name of the tool
            tool_description: Description of what the tool does
            tool_function: The actual function to execute
        """
        self.name = tool_name
        self.description = tool_description
        self.function = tool_function

    def get_ag2_function(self) -> Callable:
        """
        Get the AG2-compatible function.

        Returns:
            A callable that can be registered with AG2 agents
        """
        @wraps(self.function)
        def ag2_wrapper(*args, **kwargs):
            """Wrapper function for AG2 compatibility."""
            try:
                result = self.function(*args, **kwargs)
                if isinstance(result, str):
                    tool_lower = self.name.lower()
                    if any(kw in tool_lower for kw in ('directory', 'list_dir', 'listdir')):
                        result = _filter_directory_output(result)
                    result = _cap_tool_output(result, self.name)
                return result
            except Exception as e:
                return f"Error executing {self.name}: {str(e)}"

        # Preserve function name and docstring
        ag2_wrapper.__name__ = self.name
        ag2_wrapper.__doc__ = self.description

        return ag2_wrapper


def convert_crewai_tool_to_ag2(crewai_tool) -> Union[Any, AG2ToolAdapter]:
    """
    Convert a CrewAI tool to AG2-compatible format.

    Uses AG2's native Interoperability module when available (recommended),
    falls back to custom adapter if not available.

    CrewAI tools typically have:
    - name: str
    - description: str
    - func: Callable or _run method

    Args:
        crewai_tool: A CrewAI tool instance

    Returns:
        AG2-compatible tool (native Interop or AG2ToolAdapter instance)

    Example:
        >>> from crewai_tools import SerperDevTool
        >>> crewai_tool = SerperDevTool()
        >>> ag2_tool = convert_crewai_tool_to_ag2(crewai_tool)
    """
    # Use native AG2 Interoperability if available (recommended)
    if HAS_INTEROP:
        try:
            interop = Interoperability()
            return interop.convert_tool(tool=crewai_tool, type="crewai")
        except Exception as e:
            logger.warning("native_interop_failed", tool=str(crewai_tool), framework="crewai", error=str(e))

    # Fallback to custom adapter
    # Extract tool properties
    tool_name = getattr(crewai_tool, 'name', crewai_tool.__class__.__name__)
    tool_description = getattr(crewai_tool, 'description', '')

    # Get the executable function
    if hasattr(crewai_tool, 'func'):
        tool_function = crewai_tool.func
    elif hasattr(crewai_tool, '_run'):
        tool_function = crewai_tool._run
    elif hasattr(crewai_tool, 'run'):
        tool_function = crewai_tool.run
    elif callable(crewai_tool):
        tool_function = crewai_tool
    else:
        raise ValueError(f"Cannot extract callable from CrewAI tool: {crewai_tool}")

    return AG2ToolAdapter(
        tool_name=tool_name,
        tool_description=tool_description,
        tool_function=tool_function
    )


def convert_langchain_tool_to_ag2(langchain_tool) -> Union[Any, AG2ToolAdapter]:
    """
    Convert a LangChain tool to AG2-compatible format.

    Uses AG2's native Interoperability module when available (recommended),
    falls back to custom adapter if not available.

    LangChain tools typically have:
    - name: str
    - description: str
    - func: Callable or _run/_arun method

    Args:
        langchain_tool: A LangChain tool instance

    Returns:
        AG2-compatible tool (native Interop or AG2ToolAdapter instance)

    Example:
        >>> from langchain_community.tools import WikipediaQueryRun
        >>> from langchain_community.utilities import WikipediaAPIWrapper
        >>> wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        >>> ag2_tool = convert_langchain_tool_to_ag2(wikipedia)
    """
    # Use native AG2 Interoperability if available (recommended)
    if HAS_INTEROP:
        try:
            interop = Interoperability()
            return interop.convert_tool(tool=langchain_tool, type="langchain")
        except Exception as e:
            logger.warning("native_interop_failed", tool=str(langchain_tool), framework="langchain", error=str(e))

    # Fallback to custom adapter
    # Extract tool properties
    tool_name = getattr(langchain_tool, 'name', langchain_tool.__class__.__name__)
    tool_description = getattr(langchain_tool, 'description', '')

    # Get the executable function
    if hasattr(langchain_tool, 'func'):
        tool_function = langchain_tool.func
    elif hasattr(langchain_tool, '_run'):
        # LangChain tools use _run for synchronous execution
        tool_function = langchain_tool._run
    elif hasattr(langchain_tool, 'run'):
        tool_function = langchain_tool.run
    elif callable(langchain_tool):
        tool_function = langchain_tool
    else:
        raise ValueError(f"Cannot extract callable from LangChain tool: {langchain_tool}")

    return AG2ToolAdapter(
        tool_name=tool_name,
        tool_description=tool_description,
        tool_function=tool_function
    )


def convert_multiple_tools(
    tools: List[Any],
    source_framework: str = 'auto'
) -> List[AG2ToolAdapter]:
    """
    Convert multiple tools from external frameworks to AG2 format.

    Args:
        tools: List of tool instances from CrewAI or LangChain
        source_framework: 'crewai', 'langchain', or 'auto' to detect automatically

    Returns:
        List of AG2ToolAdapter instances

    Example:
        >>> from crewai_tools import SerperDevTool, FileReadTool
        >>> tools = [SerperDevTool(), FileReadTool()]
        >>> ag2_tools = convert_multiple_tools(tools, source_framework='crewai')
    """
    converted_tools = []

    for tool in tools:
        if source_framework == 'auto':
            # Try to detect framework from tool type
            tool_class_name = tool.__class__.__module__

            if 'crewai' in tool_class_name.lower():
                converter = convert_crewai_tool_to_ag2
            elif 'langchain' in tool_class_name.lower():
                converter = convert_langchain_tool_to_ag2
            else:
                # Default to CrewAI converter
                logger.warning("framework_detection_failed", tool=str(tool), fallback="crewai")
                converter = convert_crewai_tool_to_ag2
        elif source_framework == 'crewai':
            converter = convert_crewai_tool_to_ag2
        elif source_framework == 'langchain':
            converter = convert_langchain_tool_to_ag2
        else:
            raise ValueError(f"Unknown framework: {source_framework}")

        try:
            converted_tool = converter(tool)
            converted_tools.append(converted_tool)
        except Exception as e:
            logger.warning("tool_conversion_failed", tool=str(tool), error=str(e))

    return converted_tools
