"""
LangChain free tools integration for CMBAgent.

This module provides access to LangChain's free tools that don't require API keys.
"""

import logging
import structlog
from typing import List
from .tool_adapter import AG2ToolAdapter, convert_langchain_tool_to_ag2
from .ag2_free_tools import _build_safe_duckduckgo_tool

logger = structlog.get_logger(__name__)


def get_langchain_free_tools() -> List[AG2ToolAdapter]:
    """
    Get all available free LangChain tools.

    Returns:
        List of AG2ToolAdapter instances for free LangChain tools

    Example:
        >>> from cmbagent.external_tools import get_langchain_free_tools
        >>> tools = get_langchain_free_tools()
    """
    tools = []

    # Wikipedia tool (free)
    try:
        from langchain_community.tools import WikipediaQueryRun
        from langchain_community.utilities import WikipediaAPIWrapper

        wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
        tools.append(convert_langchain_tool_to_ag2(wikipedia))
    except ImportError as e:
        logger.warning("tool_import_failed", tool="Wikipedia", error=str(e))

    # ArXiv tool (free)
    try:
        from langchain_community.tools import ArxivQueryRun
        from langchain_community.utilities import ArxivAPIWrapper

        arxiv = ArxivQueryRun(api_wrapper=ArxivAPIWrapper())
        tools.append(convert_langchain_tool_to_ag2(arxiv))
    except ImportError as e:
        logger.warning("tool_import_failed", tool="ArXiv", error=str(e))

    # DuckDuckGo Search tool (free)
    try:
        tools.append(_build_safe_duckduckgo_tool())
    except ImportError as e:
        logger.warning("tool_import_failed", tool="DuckDuckGo search", error=str(e))

    # Python REPL tool (free)
    try:
        from langchain_community.tools import PythonREPLTool

        python_repl = PythonREPLTool()
        tools.append(convert_langchain_tool_to_ag2(python_repl))
    except ImportError as e:
        logger.warning("tool_import_failed", tool="Python REPL", error=str(e))

    # File management tools (free)
    try:
        from langchain_community.tools import (
            ReadFileTool,
            WriteFileTool,
            ListDirectoryTool,
        )

        tools.extend([
            convert_langchain_tool_to_ag2(ReadFileTool()),
            convert_langchain_tool_to_ag2(WriteFileTool()),
            convert_langchain_tool_to_ag2(ListDirectoryTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="file management", error=str(e))

    # Shell tool (free but use with caution)
    try:
        from langchain_community.tools import ShellTool

        shell = ShellTool()
        tools.append(convert_langchain_tool_to_ag2(shell))
    except ImportError as e:
        logger.warning("tool_import_failed", tool="Shell", error=str(e))

    # JSON tool (free)
    try:
        from langchain_community.tools.json.tool import JsonSpec
        from langchain_community.tools import JsonGetValueTool, JsonListKeysTool

        # Note: JsonSpec requires a dict to work with
        # Users will need to provide their own JSON data
        # These are just the tool definitions
        tools.extend([
            convert_langchain_tool_to_ag2(JsonListKeysTool()),
            convert_langchain_tool_to_ag2(JsonGetValueTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="JSON", error=str(e))

    # Requests tools (free)
    try:
        from langchain_community.tools import (
            RequestsGetTool,
            RequestsPostTool,
            RequestsPatchTool,
            RequestsPutTool,
            RequestsDeleteTool,
        )

        tools.extend([
            convert_langchain_tool_to_ag2(RequestsGetTool()),
            convert_langchain_tool_to_ag2(RequestsPostTool()),
            convert_langchain_tool_to_ag2(RequestsPatchTool()),
            convert_langchain_tool_to_ag2(RequestsPutTool()),
            convert_langchain_tool_to_ag2(RequestsDeleteTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="Requests", error=str(e))

    return tools


def get_langchain_search_tools() -> List[AG2ToolAdapter]:
    """
    Get LangChain search and research tools.

    Returns:
        List of search-related tools
    """
    tools = []

    try:
        from langchain_community.tools import (
            WikipediaQueryRun,
            ArxivQueryRun,
            DuckDuckGoSearchRun,
        )
        from langchain_community.utilities import (
            WikipediaAPIWrapper,
            ArxivAPIWrapper,
        )

        tools.extend([
            convert_langchain_tool_to_ag2(WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())),
            convert_langchain_tool_to_ag2(ArxivQueryRun(api_wrapper=ArxivAPIWrapper())),
            _build_safe_duckduckgo_tool(),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="search tools", error=str(e))

    return tools


def get_langchain_file_tools() -> List[AG2ToolAdapter]:
    """
    Get LangChain file operation tools.

    Returns:
        List of file-related tools
    """
    tools = []

    try:
        from langchain_community.tools import (
            ReadFileTool,
            WriteFileTool,
            ListDirectoryTool,
        )

        tools.extend([
            convert_langchain_tool_to_ag2(ReadFileTool()),
            convert_langchain_tool_to_ag2(WriteFileTool()),
            convert_langchain_tool_to_ag2(ListDirectoryTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="file tools", error=str(e))

    return tools


def get_langchain_web_tools() -> List[AG2ToolAdapter]:
    """
    Get LangChain web/HTTP request tools.

    Returns:
        List of web-related tools
    """
    tools = []

    try:
        from langchain_community.tools import (
            RequestsGetTool,
            RequestsPostTool,
            RequestsPatchTool,
            RequestsPutTool,
            RequestsDeleteTool,
        )

        tools.extend([
            convert_langchain_tool_to_ag2(RequestsGetTool()),
            convert_langchain_tool_to_ag2(RequestsPostTool()),
            convert_langchain_tool_to_ag2(RequestsPatchTool()),
            convert_langchain_tool_to_ag2(RequestsPutTool()),
            convert_langchain_tool_to_ag2(RequestsDeleteTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="web tools", error=str(e))

    return tools


def get_langchain_code_tools() -> List[AG2ToolAdapter]:
    """
    Get LangChain code execution tools.

    Returns:
        List of code-related tools
    """
    tools = []

    try:
        from langchain_community.tools import (
            PythonREPLTool,
            ShellTool,
        )

        tools.extend([
            convert_langchain_tool_to_ag2(PythonREPLTool()),
            convert_langchain_tool_to_ag2(ShellTool()),
        ])
    except ImportError as e:
        logger.warning("tool_import_failed", tool="code tools", error=str(e))

    return tools
