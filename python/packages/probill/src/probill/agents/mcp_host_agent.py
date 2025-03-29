import asyncio
import logging
import json
from typing import Any, Dict, List, Optional, Sequence, AsyncGenerator

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import AgentEvent, ChatMessage, TextMessage
from autogen_agentchat.base import TaskResult, Response

from autogen_core import CancellationToken, Component, ComponentModel, FunctionCall

from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    LLMMessage,
    SystemMessage,
    UserMessage,
)
from autogen_ext.tools.mcp import (
    McpServerParams,
    SseMcpToolAdapter,
    StdioMcpToolAdapter,
    mcp_server_tools,
)
from pydantic import BaseModel
from typing_extensions import Self


class McpHostAgentConfig(BaseModel):
    """Configuration for the MCP Host Agent."""
    name: str
    model_client: ComponentModel
    description: str | None = None
    server_params: McpServerParams | None = None
    system_message: str | None = None
    reflect_on_tool_use: bool = False
    model_client_stream: bool = False

class McpHostAgent(AssistantAgent, Component[McpHostAgentConfig]):
    """
    McpHostAgent is an agent that can connect to MCP servers and manage tools, resources, and prompts.
    It acts as a host that can understand and utilize tools provided by MCP servers through either
    SseMcpToolAdapter or StdioMcpToolAdapter.

    Installation:
    .. code-block:: bash
        pip install "autogen-ext[mcp]"

    Args:
        name (str): The name of the agent
        model_client (ChatCompletionClient): The model client used by the agent
        description (str, optional): Description of the agent
        server_params (McpServerParams, optional): Parameters for connecting to the MCP server
    """

    component_type = "agent"
    component_config_schema = McpHostAgentConfig
    component_provider_override = "probill.agents.mcp_host_agent.McpHostAgent"

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        description: str | None = None,
        server_params: McpServerParams | None = None,
        system_message: str | None = None,
        reflect_on_tool_use: bool = False,
        model_client_stream: bool = False,
    ):
        super().__init__(
            name, 
            description or "An MCP host agent that can connect to MCP servers and manage their tools.",
        )
        self._model_client = model_client
        self._server_params = server_params
        self._tools: List[StdioMcpToolAdapter | SseMcpToolAdapter] = []
        self._chat_history: List[LLMMessage] = []
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self._initialized = False
        self._reflect_on_tool_use = reflect_on_tool_use
        self._model_client_stream = model_client_stream
        print("Initializing MCP Host Agent...", flush=True)
        if system_message:
            self._system_messages = [SystemMessage(content=system_message)]
        else:
            self._system_messages = [
                SystemMessage(content="You are an MCP host agent. Use the tools provided by the MCP server to assist the user.")
            ]

    async def _lazy_init(self) -> None:
        """Initialize the MCP connection and fetch tools on first use."""
        if self._initialized or not self._server_params:
            return
        try:
            print("Initializing MCP connection...", flush=True)
            print(f"Server params: {self._server_params}", flush=True)
            # Fetch all available tools from the MCP server
            self._tools = await mcp_server_tools(self._server_params)
            self._initialized = True
            self.logger.info(f"Initialized MCP connection with {len(self._tools)} tools")
        except Exception as e:
            print("Failed MCP connection...", flush=True)
            self.logger.error(f"Failed to initialize MCP connection: {e}")

    async def on_messages(self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken) -> Response:
        """Process incoming messages and generate a response."""
        print("Processing messages...", flush=True)
        await self._lazy_init()
        return await super().on_messages(messages, cancellation_token)

    async def on_messages_stream(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[AgentEvent | ChatMessage, None]:
        """Process incoming messages and generate responses as a stream."""
        print("Processing streaming messages...", flush=True)
        # Initialize MCP connection if needed
        await self._lazy_init()
        async for event in super().on_messages_stream(messages, cancellation_token):
            yield event

    def _to_config(self) -> McpHostAgentConfig:
        """Convert the agent to its configuration."""
        return McpHostAgentConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            description=self.description,
            server_params=self._server_params,
            system_message=self._system_messages[0].content if self._system_messages else None,
            reflect_on_tool_use=self._reflect_on_tool_use,
            model_client_stream=self._model_client_stream,
        )

    @classmethod
    def _from_config(cls, config: McpHostAgentConfig) -> Self:
        """Create an instance of McpHostAgent from its configuration."""
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            description=config.description,
            server_params=config.server_params,
            system_message=config.system_message,
            reflect_on_tool_use=config.reflect_on_tool_use,
            model_client_stream=config.model_client_stream,
        )