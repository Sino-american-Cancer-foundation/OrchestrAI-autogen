from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from ._config import McpServerParams, SseServerParams, StdioServerParams

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

@dataclass
class ToolResponse:
    """Response from a tool invocation."""
    tools: List[Dict[str, Any]]

@dataclass
class ResourceResponse:
    """Response containing resource data."""
    type: str
    content: Any
    metadata: Dict[str, Any]

@dataclass
class ResourceListResponse:
    """Response containing list of available resources."""
    resource_ids: List[str]

@dataclass
class PromptResponse:
    """Response containing prompt template data."""
    template: str
    variables: List[str]
    metadata: Dict[str, Any]

@dataclass
class PromptListResponse:
    """Response containing list of available prompts."""
    prompt_ids: List[str]


class McpServerSession(ABC):
    """Abstract base class for MCP server sessions."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the session with the server."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the session."""
        pass

    @abstractmethod
    async def list_tools(self) -> ToolResponse:
        """List available tools on the server."""
        pass

    @abstractmethod
    async def get_resource(self, resource_id: str) -> ResourceResponse:
        """Get a resource by its ID."""
        pass

    @abstractmethod
    async def list_resources(self) -> ResourceListResponse:
        """List available resources on the server."""
        pass

    @abstractmethod
    async def get_prompt(self, prompt_id: str) -> PromptResponse:
        """Get a prompt template by its ID."""
        pass

    @abstractmethod
    async def list_prompts(self) -> PromptListResponse:
        """List available prompts on the server."""
        pass

    @abstractmethod
    async def update_sampling_config(self, temperature: float, top_p: float,
                                   frequency_penalty: float, presence_penalty: float,
                                   max_tokens: Optional[int]) -> None:
        """Update the sampling configuration for LLM responses."""
        pass


class StdioMcpServerSession(McpServerSession):
    """MCP server session for command-line tools."""

    async def initialize(self) -> None:
        # Implementation for stdio session initialization
        pass

    async def close(self) -> None:
        # Implementation for stdio session cleanup
        pass

    async def list_tools(self) -> ToolResponse:
        # Implementation for listing tools via stdio
        pass

    async def get_resource(self, resource_id: str) -> ResourceResponse:
        # Implementation for getting resources via stdio
        pass

    async def list_resources(self) -> ResourceListResponse:
        # Implementation for listing resources via stdio
        pass

    async def get_prompt(self, prompt_id: str) -> PromptResponse:
        # Implementation for getting prompts via stdio
        pass

    async def list_prompts(self) -> PromptListResponse:
        # Implementation for listing prompts via stdio
        pass

    async def update_sampling_config(self, temperature: float, top_p: float,
                                   frequency_penalty: float, presence_penalty: float,
                                   max_tokens: Optional[int]) -> None:
        # Implementation for updating sampling config via stdio
        pass


class SseMcpServerSession(McpServerSession):
    """MCP server session for HTTP/SSE services."""

    async def initialize(self) -> None:
        # Implementation for SSE session initialization
        pass

    async def close(self) -> None:
        # Implementation for SSE session cleanup
        pass

    async def list_tools(self) -> ToolResponse:
        # Implementation for listing tools via SSE
        pass

    async def get_resource(self, resource_id: str) -> ResourceResponse:
        # Implementation for getting resources via SSE
        pass

    async def list_resources(self) -> ResourceListResponse:
        # Implementation for listing resources via SSE
        pass

    async def get_prompt(self, prompt_id: str) -> PromptResponse:
        # Implementation for getting prompts via SSE
        pass

    async def list_prompts(self) -> PromptListResponse:
        # Implementation for listing prompts via SSE
        pass

    async def update_sampling_config(self, temperature: float, top_p: float,
                                   frequency_penalty: float, presence_penalty: float,
                                   max_tokens: Optional[int]) -> None:
        # Implementation for updating sampling config via SSE
        pass


async def create_mcp_server_session(params: Any) -> McpServerSession:
    """Create a new MCP server session.

    Args:
        params: Connection parameters for the MCP server.
            Can be either StdioServerParams for command-line tools or
            SseServerParams for HTTP/SSE services.

    Returns:
        An initialized MCP server session.

    Raises:
        ValueError: If the server parameters type is not supported.
    """
    from ._config import StdioServerParams, SseServerParams

    if isinstance(params, StdioServerParams):
        return StdioMcpServerSession()
    elif isinstance(params, SseServerParams):
        return SseMcpServerSession()
    else:
        raise ValueError(f"Unsupported server params type: {type(params)}")