"""
External tools integration for CMBAgent.

This module provides integration with CrewAI and LangChain tools using
AG2's native Interoperability module.

Quick Start (New - AG2 Native Interoperability):
    >>> from cmbagent.external_tools.ag2_free_tools import load_all_free_tools
    >>> 
    >>> # Load all free tools using AG2 Interoperability
    >>> tools = load_all_free_tools()
    >>> print(f"Loaded {len(tools['langchain'])} LangChain tools")
    >>> print(f"Loaded {len(tools['crewai'])} CrewAI tools")

Quick Start (Legacy - Custom Adapter):
    >>> from cmbagent import CMBAgent
    >>> from cmbagent.external_tools.integration_helpers import register_external_tools_with_agents
    >>> 
    >>> cmbagent = CMBAgent(work_dir="./my_project", mode="planning_and_control")
    >>> register_external_tools_with_agents(cmbagent)
    >>> 
    >>> # Your agents now have 30+ external tools!
    >>> result = cmbagent.solve("Your task here", max_rounds=30)
"""

from .tool_adapter import (
    AG2ToolAdapter,
    convert_crewai_tool_to_ag2,
    convert_langchain_tool_to_ag2,
    convert_multiple_tools
)
from .tool_registry import ExternalToolRegistry, get_global_registry
from .crewai_tools import (
    get_crewai_free_tools,
    get_crewai_file_tools,
    get_crewai_web_tools,
    get_crewai_code_tools,
    get_crewai_search_tools,
)
from .langchain_tools import (
    get_langchain_free_tools,
    get_langchain_search_tools,
    get_langchain_file_tools,
    get_langchain_web_tools,
    get_langchain_code_tools,
)
from .news_tools import (
    announcements_noauth,
    curated_ai_sources_catalog,
    curated_ai_sources_search,
    newsapi_search,
    gnews_search,
    multi_engine_web_search,
    scrape_official_news_pages,
    verify_url,
    verify_reference_links,
)

# New AG2 native interoperability functions
try:
    from .ag2_free_tools import (
        AG2FreeToolsLoader,
        load_all_free_tools,
        load_langchain_free_tools,
        load_crewai_free_tools,
    )
    HAS_AG2_INTEROP = True
except ImportError:
    HAS_AG2_INTEROP = False

__all__ = [
    # Core components
    'AG2ToolAdapter',
    'ExternalToolRegistry',
    'get_global_registry',
    
    # Conversion functions
    'convert_crewai_tool_to_ag2',
    'convert_langchain_tool_to_ag2',
    'convert_multiple_tools',
    
    # CrewAI tool loaders
    'get_crewai_free_tools',
    'get_crewai_file_tools',
    'get_crewai_web_tools',
    'get_crewai_code_tools',
    'get_crewai_search_tools',
    
    # LangChain tool loaders
    'get_langchain_free_tools',
    'get_langchain_search_tools',
    'get_langchain_file_tools',
    'get_langchain_web_tools',
    'get_langchain_code_tools',

    # News and announcement tools
    'announcements_noauth',
    'curated_ai_sources_catalog',
    'curated_ai_sources_search',
    'newsapi_search',
    'gnews_search',
    'multi_engine_web_search',
    'scrape_official_news_pages',
    'verify_url',
    'verify_reference_links',
]

# Add AG2 native interop functions if available
if HAS_AG2_INTEROP:
    __all__.extend([
        'AG2FreeToolsLoader',
        'load_all_free_tools',
        'load_langchain_free_tools',
        'load_crewai_free_tools',
    ])