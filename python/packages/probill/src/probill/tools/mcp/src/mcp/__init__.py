"""
Model Context Protocol (MCP) client implementation.

This module provides a flexible and extensible implementation of the Model Context Protocol,
enabling seamless communication between LLM applications and integrations.
"""

from ._base import McpToolAdapter
from ._config import (
    McpServerParams,
    SseServerParams,
    StdioServerParams,
    ResourceConfig,
    PromptConfig,
    SamplingConfig,
)
from ._factory import create_mcp_client, mcp_server_tools
from ._session import (
    McpServerSession,
    ToolResponse,
    ResourceResponse,
    ResourceListResponse,
    PromptResponse,
    PromptListResponse,
)
from ._sse import SseMcpToolAdapter
from ._stdio import StdioMcpToolAdapter

__all__ = [
    # Base classes
    "McpToolAdapter",
    "McpServerSession",
    
    # Configuration
    "McpServerParams",
    "SseServerParams",
    "StdioServerParams",
    "ResourceConfig",
    "PromptConfig",
    "SamplingConfig",
    
    # Response types
    "ToolResponse",
    "ResourceResponse",
    "ResourceListResponse",
    "PromptResponse",
    "PromptListResponse",
    
    # Implementations
    "SseMcpToolAdapter",
    "StdioMcpToolAdapter",
    
    # Factory functions
    "create_mcp_client",
    "mcp_server_tools",
]
