from autogen_core import Component
from mcp import Tool
from pydantic import BaseModel
from typing_extensions import Self
import asyncio
import json
from typing import Dict, Any, List, Optional
from ._session import McpServerSession, ToolResponse, ResourceResponse, ResourceListResponse, PromptResponse, PromptListResponse
from ._config import StdioServerParams, SamplingConfig

from ._base import McpToolAdapter
from ._config import StdioServerParams


class StdioMcpToolAdapterConfig(BaseModel):
    """Configuration for the MCP tool adapter."""

    server_params: StdioServerParams
    tool: Tool


class StdioMcpToolAdapter(
    McpToolAdapter[StdioServerParams],
    Component[StdioMcpToolAdapterConfig],
):
    """Allows you to wrap an MCP tool running over STDIO and make it available to AutoGen.

    This adapter enables using MCP-compatible tools that communicate over standard input/output
    with AutoGen agents. Common use cases include wrapping command-line tools and local services
    that implement the Model Context Protocol (MCP).

    .. note::

        To use this class, you need to install `mcp` extra for the `autogen-ext` package.

        .. code-block:: bash

            pip install -U "autogen-ext[mcp]"


    Args:
        server_params (StdioServerParams): Parameters for the MCP server connection,
            including command to run and its arguments
        tool (Tool): The MCP tool to wrap

    See :func:`~autogen_ext.tools.mcp.mcp_server_tools` for examples.
    """

    component_config_schema = StdioMcpToolAdapterConfig
    component_provider_override = "autogen_ext.tools.mcp.StdioMcpToolAdapter"

    def __init__(self, server_params: StdioServerParams, tool: Tool) -> None:
        super().__init__(server_params=server_params, tool=tool)

    def _to_config(self) -> StdioMcpToolAdapterConfig:
        """
        Convert the adapter to its configuration representation.

        Returns:
            StdioMcpToolAdapterConfig: The configuration of the adapter.
        """
        return StdioMcpToolAdapterConfig(server_params=self._server_params, tool=self._tool)

    @classmethod
    def _from_config(cls, config: StdioMcpToolAdapterConfig) -> Self:
        """
        Create an instance of StdioMcpToolAdapter from its configuration.

        Args:
            config (StdioMcpToolAdapterConfig): The configuration of the adapter.

        Returns:
            StdioMcpToolAdapter: An instance of StdioMcpToolAdapter.
        """
        return cls(server_params=config.server_params, tool=config.tool)


class StdioMcpServerSession(McpServerSession):
    """MCP server session implementation for command-line tools."""
    
    def __init__(self, params: StdioServerParams):
        self.params = params
        self._process: Optional[asyncio.subprocess.Process] = None
        self._sampling_config = SamplingConfig()

    async def initialize(self) -> None:
        """Start the command-line process."""
        if not self._process:
            # Create subprocess with pipes for stdin/stdout
            self._process = await asyncio.create_subprocess_exec(
                *self.params.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.params.working_directory,
                env=self.params.environment
            )

    async def close(self) -> None:
        """Terminate the command-line process."""
        if self._process:
            self._process.terminate()
            try:
                await self._process.wait()
            except ProcessLookupError:
                pass  # Process already terminated
            self._process = None

    async def _send_command(self, command: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the process and get the response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("Process not initialized")

        message = {
            "command": command,
            "payload": payload
        }
        
        # Write command to stdin
        data = json.dumps(message).encode() + b"\n"
        self._process.stdin.write(data)
        await self._process.stdin.drain()

        # Read response from stdout
        response = await self._process.stdout.readline()
        if not response:
            raise RuntimeError("Process closed unexpectedly")
        
        try:
            return json.loads(response.decode())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {e}")

    async def list_tools(self) -> ToolResponse:
        """List available tools from the command-line process."""
        response = await self._send_command("list_tools", {})
        return ToolResponse(tools=response["tools"])

    async def get_resource(self, resource_id: str) -> ResourceResponse:
        """Get a resource by its ID from the command-line process."""
        response = await self._send_command("get_resource", {"resource_id": resource_id})
        return ResourceResponse(
            type=response["type"],
            content=response["content"],
            metadata=response["metadata"]
        )

    async def list_resources(self) -> ResourceListResponse:
        """List available resources from the command-line process."""
        response = await self._send_command("list_resources", {})
        return ResourceListResponse(resource_ids=response["resource_ids"])

    async def get_prompt(self, prompt_id: str) -> PromptResponse:
        """Get a prompt template by its ID from the command-line process."""
        response = await self._send_command("get_prompt", {"prompt_id": prompt_id})
        return PromptResponse(
            template=response["template"],
            variables=response["variables"],
            metadata=response["metadata"]
        )

    async def list_prompts(self) -> PromptListResponse:
        """List available prompts from the command-line process."""
        response = await self._send_command("list_prompts", {})
        return PromptListResponse(prompt_ids=response["prompt_ids"])

    async def update_sampling_config(self, temperature: float, top_p: float,
                                   frequency_penalty: float, presence_penalty: float,
                                   max_tokens: Optional[int]) -> None:
        """Update the sampling configuration."""
        config = {
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        }
        if max_tokens is not None:
            config["max_tokens"] = max_tokens

        await self._send_command("update_sampling", config)
        self._sampling_config = SamplingConfig(
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            max_tokens=max_tokens
        )

    async def invoke_tool(self, tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool through the command-line process."""
        return await self._send_command("invoke_tool", {
            "tool_id": tool_id,
            "parameters": params
        })