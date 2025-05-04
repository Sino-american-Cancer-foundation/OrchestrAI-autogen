import builtins
import warnings
from typing import Any, Dict, List, Literal, Mapping, Optional
from autogen_core import CancellationToken, Component, Image
from autogen_core.tools import (
    ImageResultContent,
    ParametersSchema,
    TextResultContent,
    ToolResult,
    ToolSchema,
    Workbench,
)
from mcp.types import CallToolResult, EmbeddedResource, ImageContent, ListToolsResult, TextContent, Prompt, ListPromptsResult
from pydantic import BaseModel
from typing_extensions import Self

from autogen_ext.tools.mcp import McpSessionActor, StdioServerParams, SseServerParams, McpServerParams

class McpsServerParams(BaseModel):
    server_id: str
    server_params: McpServerParams

class McpsWorkbenchConfig(BaseModel):
    server_params_list: List[McpsServerParams]

class McpsWorkbenchState(BaseModel):
    type: Literal["McpsWorkbenchState"] = "McpsWorkbenchState"
    server_configs: List[dict] = []


class McpsWorkbench(Workbench, Component[McpsWorkbenchConfig]):
    """
    A workbench that wraps multiple MCP servers and provides an interface
    to list and call tools provided by the servers.

    Args:
        server_params_list (List[McpsServerParams]): A list of parameters to connect to multiple MCP servers.
            Each server_params can be either a :class:`StdioServerParams` or :class:`SseServerParams`.

    Example:

        .. code-block:: python

            import asyncio

            from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams


            async def main() -> None:
                params_list = [
                    NamedMcpServerParams(
                        server_id="fetch_server",
                        server_params=StdioServerParams(
                            command="uvx",
                            args=["mcp-server-fetch"],
                            read_timeout_seconds=60,
                        )
                    ),
                    NamedMcpServerParams(
                        server_id="local_server",
                        server_params=SseServerParams(
                            url="http://localhost:8080",
                            timeout_seconds=60,
                        )
                    ),
                ]

                async with McpWorkbench(server_params_list=params_list) as workbench:
                    tools = await workbench.list_tools()
                    print(tools)
                    result = await workbench.call_tool(tools[0]["name"], {"url": "https://github.com/"})
                    print(result)


            asyncio.run(main())
    """

    component_provider_override = "probill.tools.mcp.McpsWorkbench"
    component_config_schema = McpsWorkbenchConfig

    def __init__(self, server_params_list: List[McpsServerParams]) -> None:
        self._server_params_list = server_params_list
        self._actors: Dict[str, McpSessionActor] = {}

    @property
    def server_params_list(self) -> List[McpsServerParams]:
        return self._server_params_list

    async def list_tools(self, server_id: Optional[str] = None) -> List[ToolSchema]:
        """
        List tools from all servers or a specific server.

        Args:
            server_id (Optional[str]): If provided, list tools from the specified server.
                                      If None, aggregate tools from all servers.

        Returns:
            List[ToolSchema]: A list of tool schemas.
        """
        if not self._actors:
            await self.start()

        schema: List[ToolSchema] = []
        target_actors = [self._actors[server_id]] if server_id else self._actors.values()

        for server_id, actor in self._actors.items():
            result_future = await actor.call("list_tools", None)
            list_tool_result = await result_future
            assert isinstance(
                list_tool_result, ListToolsResult
            ), f"list_tools must return a ListToolsResult, instead of: {str(type(list_tool_result))}"

            for tool in list_tool_result.tools:
                name = tool.name
                description = tool.description or ""
                parameters = ParametersSchema(
                    type="object",
                    properties=tool.inputSchema["properties"],
                    required=tool.inputSchema.get("required", []),
                    additionalProperties=tool.inputSchema.get("additionalProperties", False),
                )
                tool_schema = ToolSchema(
                    server_id=server_id,
                    name=name,
                    description=description,
                    parameters=parameters,
                )
                schema.append(tool_schema)
        return schema

    async def list_prompts(self, server_id: Optional[str] = None) -> List[Prompt]:
        """
        List prompts from all servers or a specific server.

        Args:
            server_id (Optional[str]): If provided, list prompts from the specified server.
                                      If None, aggregate prompts from all servers.

        Returns:
            List[str]: A list of prompt names.
        """
        if not self._actors:
            await self.start()

        prompts: List[str] = []
        target_actors = [self._actors[server_id]] if server_id else self._actors.values()

        for actor in target_actors:
            try:
                result_future = await actor.call("list_prompts", None)
                list_prompt_result = await result_future
                assert isinstance(
                    list_prompt_result, ListPromptsResult
                ), f"list_prompts must return a ListPromptsResult, instead of: {str(type(list_prompt_result))}"

                for prompt in list_prompt_result.prompts:
                    prompts.append(prompt.model_dump())
            except Exception as e:
                pass
        return prompts

    async def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        cancellation_token: CancellationToken | None = None,
        server_id: Optional[str] = None,
    ) -> ToolResult:
        """
        Call a tool on a specific server or the first available server with the tool.

        Args:
            name (str): The name of the tool to call.
            arguments (Mapping[str, Any], optional): The arguments for the tool.
            cancellation_token (CancellationToken, optional): Token to cancel the operation.
            server_id (Optional[str]): If provided, call the tool on the specified server.
                                      If None, find the first server with the tool.

        Returns:
            ToolResult: The result of the tool call.
        """
        if not self._actors:
            await self.start()

        if not cancellation_token:
            cancellation_token = CancellationToken()
        if not arguments:
            arguments = {}

        target_actor = None
        if server_id:
            target_actor = self._actors.get(server_id)
            if not target_actor:
                raise RuntimeError(f"Server with ID {server_id} not found.")
        else:
            tools = await self.list_tools()
            target_actor = next(
                (
                    # Try to get the actor for the tool's server_id
                    actor
                    for tool in tools
                    if tool.get("name") == name
                    if (actor := self._actors.get(tool.get("server_id"))) is not None
                ),
                None
            )
            if not target_actor:
                raise RuntimeError(f"Tool {name} not found on any server.")

        try:
            result_future = await target_actor.call("call_tool", {"name": name, "kargs": arguments})
            cancellation_token.link_future(result_future)
            result = await result_future
            assert isinstance(
                result, CallToolResult
            ), f"call_tool must return a CallToolResult, instead of: {str(type(result))}"
            result_parts: List[TextResultContent | ImageResultContent] = []
            is_error = result.isError
            for content in result.content:
                if isinstance(content, TextContent):
                    result_parts.append(TextResultContent(content=content.text))
                elif isinstance(content, ImageContent):
                    result_parts.append(TextResultContent(content="[Image]"))
                    result_parts.append(ImageResultContent(content=Image.from_base64(content.data)))
                elif isinstance(content, EmbeddedResource):
                    result_parts.append(TextResultContent(content=content.model_dump_json()))
                else:
                    raise ValueError(f"Unknown content type from server: {type(content)}")
        except Exception as e:
            error_message = self._format_errors(e)
            is_error = True
            result_parts = [TextResultContent(content=error_message)]
        return ToolResult(name=name, result=result_parts, is_error=is_error)

    def _format_errors(self, error: Exception) -> str:
        """Recursively format errors into a string."""
        error_message = ""
        if hasattr(builtins, "ExceptionGroup") and isinstance(error, builtins.ExceptionGroup):
            for sub_exception in error.exceptions:  # type: ignore
                error_message += self._format_errors(sub_exception)  # type: ignore
        else:
            error_message += f"{str(error)}\n"
        return error_message

    async def start(self) -> None:
        if self._actors:
            warnings.warn(
                "McpWorkbench is already started. No need to start again.",
                UserWarning,
                stacklevel=2,
            )
            return

        for server_config in self._server_params_list:
            server_params = server_config.server_params
            if isinstance(server_params, (StdioServerParams, SseServerParams)):
                actor = McpSessionActor(server_params)
                await actor.initialize()
                actor.name = server_config.server_id
                self._actors[server_config.server_id] = actor
            else:
                raise ValueError(f"Unsupported server params type: {type(server_params)}")

    async def stop(self) -> None:
        for actor in self._actors.values():
            await actor.close()
        self._actors.clear()

    async def reset(self) -> None:
        await self.stop()
        await self.start()

    async def save_state(self) -> Mapping[str, Any]:
        state = McpsWorkbenchState(
            server_configs=[params.model_dump() for params in self._server_params_list]
        )
        return state.model_dump()

    async def load_state(self, state: Mapping[str, Any]) -> None:
        state_model = McpsWorkbenchState(**state)
        self._server_params_list = [
            McpsServerParams.model_validate(config) for config in state_model.server_configs
        ]
        await self.reset()

    def _to_config(self) -> McpsWorkbenchConfig:
        return McpsWorkbenchConfig(server_params_list=self._server_params_list)

    @classmethod
    def _from_config(cls, config: McpsWorkbenchConfig) -> Self:
        return cls(server_params_list=config.server_params_list)