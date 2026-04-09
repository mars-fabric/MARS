"""
MCP Tool Integration - Integrates MCP tools with AG2 agents.

This module wraps MCP tools so they can be registered and used by AG2 agents.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional
import inspect

from .client_manager import MCPClientManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output size guard — same limit as the rest of the cmbagent tool pipeline.
# ---------------------------------------------------------------------------
_MAX_TOOL_OUTPUT_CHARS = 25_000   # ≈ 6 k tokens

# Try to import AG2/AutoGen
try:
    from autogen import ConversableAgent
    HAS_AUTOGEN = True
except ImportError:
    HAS_AUTOGEN = False
    logger.warning("autogen not available - AG2 integration disabled")


class MCPToolIntegration:
    """
    Integrates MCP tools with AG2 agents.
    
    Creates wrapper functions for MCP tools and registers them with AG2 agents.
    """
    
    def __init__(self, mcp_manager: MCPClientManager):
        """
        Initialize tool integration.
        
        Args:
            mcp_manager: MCPClientManager instance with active connections
        """
        self.mcp_manager = mcp_manager
        self.registered_tools: Dict[str, Dict] = {}
    
    def register_tools_with_agent(
        self,
        agent: 'ConversableAgent',
        server_filter: Optional[str] = None
    ) -> int:
        """
        Register all MCP tools with an AG2 agent.
        
        Args:
            agent: AG2 ConversableAgent instance
            server_filter: Optional server name to filter tools (default: all servers)
            
        Returns:
            Number of tools registered
        """
        if not HAS_AUTOGEN:
            logger.error("Cannot register tools - autogen not available")
            return 0
        
        # Get tools to register
        if server_filter:
            tools = self.mcp_manager.get_tools_by_server(server_filter)
        else:
            tools = self.mcp_manager.get_all_tools()
        
        registered_count = 0
        
        for tool in tools:
            try:
                # Create wrapper function
                tool_func = self._create_tool_wrapper(
                    server_name=tool['server_name'],
                    tool_name=tool['name'],
                    description=tool.get('description', ''),
                    input_schema=tool.get('inputSchema', {})
                )
                
                # Register with agent for LLM and execution
                agent.register_for_llm(
                    name=f"{tool['server_name']}_{tool['name']}",
                    description=tool.get('description', '')
                )(tool_func)
                
                agent.register_for_execution(
                    name=f"{tool['server_name']}_{tool['name']}"
                )(tool_func)
                
                # Track registration
                self.registered_tools[f"{tool['server_name']}_{tool['name']}"] = tool
                registered_count += 1
                
                logger.debug(f"Registered MCP tool: {tool['server_name']}.{tool['name']}")
                
            except Exception as e:
                logger.error(f"Failed to register tool {tool['name']}: {e}")
        
        logger.info(f"Registered {registered_count} MCP tools with agent {agent.name}")
        return registered_count
    
    def _create_tool_wrapper(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        input_schema: Dict
    ) -> Callable:
        """
        Create a wrapper function for an MCP tool.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool
            description: Tool description
            input_schema: JSON schema for tool inputs
            
        Returns:
            Callable wrapper function
        """
        # Extract parameters from input schema
        properties = input_schema.get('properties', {})
        required = input_schema.get('required', [])
        
        # Create function signature dynamically
        def tool_wrapper(**kwargs) -> str:
            """
            Wrapper function that calls the MCP tool.
            
            This function is called by AG2 agents when they use the tool.
            """
            try:
                # Call MCP tool asynchronously
                result = asyncio.run(
                    self.mcp_manager.call_tool(
                        server_name=server_name,
                        tool_name=tool_name,
                        arguments=kwargs
                    )
                )
                
                if result['status'] == 'success':
                    # Format result for agent
                    return self._format_tool_result(result['result'])
                else:
                    error_msg = f"Tool call failed: {result.get('error', 'Unknown error')}"
                    logger.error(f"{server_name}.{tool_name} error: {error_msg}")
                    return error_msg
                    
            except Exception as e:
                error_msg = f"Exception calling tool: {str(e)}"
                logger.error(f"{server_name}.{tool_name} exception: {error_msg}")
                return error_msg
        
        # Set function metadata
        tool_wrapper.__name__ = f"{server_name}_{tool_name}"
        tool_wrapper.__doc__ = description or f"MCP tool: {server_name}.{tool_name}"
        
        # Add parameter annotations for AG2
        annotations = {}
        for param_name, param_info in properties.items():
            # Map JSON schema types to Python types
            param_type = self._json_type_to_python(param_info.get('type', 'string'))
            annotations[param_name] = param_type
        annotations['return'] = str
        tool_wrapper.__annotations__ = annotations
        
        return tool_wrapper
    
    def _json_type_to_python(self, json_type: str) -> type:
        """
        Convert JSON schema type to Python type.
        
        Args:
            json_type: JSON schema type string
            
        Returns:
            Python type
        """
        type_map = {
            'string': str,
            'number': float,
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
        }
        return type_map.get(json_type, str)
    
    def _format_tool_result(self, result: Any) -> str:
        """
        Format MCP tool result for AG2 agent consumption.
        
        Args:
            result: Raw result from MCP tool
            
        Returns:
            Formatted string result, capped at _MAX_TOOL_OUTPUT_CHARS
        """
        if isinstance(result, list):
            # MCP returns list of content items
            formatted_parts = []
            for item in result:
                if hasattr(item, 'text'):
                    formatted_parts.append(item.text)
                elif isinstance(item, dict):
                    if 'text' in item:
                        formatted_parts.append(item['text'])
                    else:
                        formatted_parts.append(json.dumps(item, ensure_ascii=False, default=str))
                else:
                    formatted_parts.append(str(item))
            text = '\n'.join(formatted_parts)
        elif isinstance(result, dict):
            # If result is dict, format as compact JSON
            if 'text' in result:
                text = result['text']
            else:
                try:
                    text = json.dumps(result, ensure_ascii=False, default=str)
                except (TypeError, ValueError):
                    text = str(result)
        else:
            text = str(result)

        # Hard cap to stay within context budget
        if len(text) > _MAX_TOOL_OUTPUT_CHARS:
            head = int(_MAX_TOOL_OUTPUT_CHARS * 0.70)
            tail = _MAX_TOOL_OUTPUT_CHARS - head
            text = (
                text[:head]
                + "\n\n... [MCP tool output truncated: "
                + f"{len(text)} → {_MAX_TOOL_OUTPUT_CHARS} chars] ...\n\n"
                + text[-tail:]
            )
        return text
    
    def get_registered_tool_names(self) -> list:
        """Get list of registered tool names."""
        return list(self.registered_tools.keys())
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """Get information about a registered tool."""
        return self.registered_tools.get(tool_name)
