from ._config import McpServerParams, SseServerParams, StdioServerParams
from ._session import create_mcp_server_session
from ._sse import SseMcpToolAdapter
from ._stdio import StdioMcpToolAdapter
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class McpResource:
    """Represents an MCP resource with its metadata and content."""
    id: str
    type: str
    content: Any
    metadata: Dict[str, Any]

@dataclass
class McpPrompt:
    """Represents an MCP prompt template with variables."""
    id: str
    template: str
    variables: List[str]
    metadata: Dict[str, Any]

@dataclass
class McpSamplingConfig:
    """Represents sampling configuration for LLM responses."""
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: Optional[int] = None


class McpClient:
    """A comprehensive client for interacting with MCP servers."""
    
    def __init__(self, server_params: McpServerParams):
        self.server_params = server_params
        self._session = None
        self._tools = None
        self._resources = {}
        self._prompts = {}
        self._sampling_config = McpSamplingConfig()

    async def __aenter__(self):
        self._session = await create_mcp_server_session(self.server_params)
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def get_tools(self) -> List[Union[StdioMcpToolAdapter, SseMcpToolAdapter]]:
        """Get all available tools from the MCP server."""
        if not self._tools:
            tools_response = await self._session.list_tools()
            if isinstance(self.server_params, StdioServerParams):
                self._tools = [StdioMcpToolAdapter(server_params=self.server_params, tool=tool) 
                             for tool in tools_response.tools]
            elif isinstance(self.server_params, SseServerParams):
                self._tools = [SseMcpToolAdapter(server_params=self.server_params, tool=tool) 
                             for tool in tools_response.tools]
            else:
                raise ValueError(f"Unsupported server params type: {type(self.server_params)}")
        return self._tools

    async def get_resource(self, resource_id: str) -> McpResource:
        """Get a resource by its ID."""
        if resource_id not in self._resources:
            response = await self._session.get_resource(resource_id)
            self._resources[resource_id] = McpResource(
                id=resource_id,
                type=response.type,
                content=response.content,
                metadata=response.metadata
            )
        return self._resources[resource_id]

    async def list_resources(self) -> List[str]:
        """List all available resource IDs."""
        response = await self._session.list_resources()
        return response.resource_ids

    async def get_prompt(self, prompt_id: str) -> McpPrompt:
        """Get a prompt template by its ID."""
        if prompt_id not in self._prompts:
            response = await self._session.get_prompt(prompt_id)
            self._prompts[prompt_id] = McpPrompt(
                id=prompt_id,
                template=response.template,
                variables=response.variables,
                metadata=response.metadata
            )
        return self._prompts[prompt_id]

    async def list_prompts(self) -> List[str]:
        """List all available prompt template IDs."""
        response = await self._session.list_prompts()
        return response.prompt_ids

    def set_sampling_config(self, config: McpSamplingConfig) -> None:
        """Set the sampling configuration for LLM responses."""
        self._sampling_config = config

    def get_sampling_config(self) -> McpSamplingConfig:
        """Get the current sampling configuration."""
        return self._sampling_config


async def create_mcp_client(server_params: McpServerParams) -> McpClient:
    """Create a new MCP client instance.
    
    This is the recommended way to create an MCP client as it ensures proper
    initialization and cleanup of resources.
    
    Args:
        server_params (McpServerParams): Connection parameters for the MCP server.
            Can be either StdioServerParams for command-line tools or
            SseServerParams for HTTP/SSE services.
            
    Returns:
        McpClient: A new MCP client instance.
        
    Example:
        .. code-block:: python
        
            async with await create_mcp_client(server_params) as client:
                tools = await client.get_tools()
                resources = await client.list_resources()
                prompts = await client.list_prompts()
    """
    return await McpClient(server_params).__aenter__()


async def mcp_server_tools(
    server_params: McpServerParams,
) -> List[Union[StdioMcpToolAdapter, SseMcpToolAdapter]]:
    """Creates a list of MCP tool adapters that can be used with AutoGen agents.
    
    This function is maintained for backward compatibility. For new code, consider
    using create_mcp_client() instead.
    """
    async with await create_mcp_client(server_params) as client:
        return await client.get_tools()


