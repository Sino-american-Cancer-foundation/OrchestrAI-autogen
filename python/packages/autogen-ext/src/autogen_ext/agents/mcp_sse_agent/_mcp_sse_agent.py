import asyncio
import json
import logging
import traceback
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Sequence,
    Union,
    cast,
)

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    AgentEvent,
    ChatMessage,
    MultiModalMessage,
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
)
from autogen_core import EVENT_LOGGER_NAME, CancellationToken, Component, FunctionCall
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    LLMMessage,
    SystemMessage,
    UserMessage,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
)
from pydantic import BaseModel, Field
from typing_extensions import Self

from autogen_ext.tools.mcp import SseServerParams
from autogen_ext.tools.mcp._session import create_mcp_server_session


class McpSseAgentConfig(BaseModel):
    """Configuration for McpAgent"""
    
    name: str
    model_client: Any  # Changed from Component[Any] to Any
    description: str | None = None
    system_message: str = Field(
        default="You are a helpful AI assistant. Solve tasks using your tools. Reply with TERMINATE when the task has been completed."
    )
    sse_url: str
    sse_headers: Dict[str, Any] | None = None
    sse_timeout: float = 120.0
    mcp_tools: List[Any] = Field(default_factory=list)  # List of tools available in the MCP server
    
    class Config:
        arbitrary_types_allowed = True  # Allow arbitrary types for validation


class McpSseAgent(BaseChatAgent, Component[McpSseAgentConfig]):
    """
    An agent specialized in handling tasks through a Model Context Protocol (MCP) server.

    Installation:
    
    .. code-block:: bash
    
        pip install "autogen-ext[mcp]"
        
    Args:
        name (str): The name of the agent.
        model_client (ChatCompletionClient): The LLM client used for generating responses.
        sse_url (str): The URL of the SSE-based MCP server.
        description (str, optional): Description of the agent's purpose. Defaults to DEFAULT_DESCRIPTION.
        sse_headers (Dict[str, Any], optional): Headers to use when connecting to the SSE server.
        sse_timeout (float, optional): Timeout for SSE connections in seconds. Defaults to 120.0.
    """

    component_type = "agent"
    component_config_schema = McpSseAgentConfig
    component_provider_override = "autogen_ext.agents.mcp_sse_agent.McpSseAgent"

    DEFAULT_DESCRIPTION = "An agent specializing in using MCP server tool for task execution"

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        sse_url: str,
        description: str = DEFAULT_DESCRIPTION,
        sse_headers: Dict[str, Any] | None = None,
        sse_timeout: float = 120.0,
        system_message: (
            str | None
        ) = "You are a helpful AI assistant. Solve tasks using your tools. Reply with TERMINATE when the task has been completed."
    ) -> None:
        super().__init__(name, description)
        self._model_client = model_client
        self._sse_url = sse_url
        self._sse_headers = sse_headers or {}
        self._sse_timeout = sse_timeout
        self._chat_history: List[LLMMessage] = []
        
        # Initialize logger
        self.logger = logging.getLogger(EVENT_LOGGER_NAME + f".{self.name}.InsuranceAgent")
        
        # MCP session will be initialized lazily
        self._mcp_session = None
        self._mcp_tools = []
        self._mcp_initialized = False

        self.system_message = system_message

    @property
    def produced_message_types(self) -> Sequence[type[ChatMessage]]:
        """The types of messages that this agent can produce."""
        return (TextMessage,)

    async def _lazy_init(self, cancellation_token: CancellationToken) -> None:
        """Initialize MCP session and tools on first use."""
        if self._mcp_initialized:
            return

        # Set up the server parameters for SSE connection
        server_params = SseServerParams(
            url=self._sse_url,
            headers=self._sse_headers,
            timeout=self._sse_timeout,
        )
        
        # Create a session and get available tools
        try:
            async with create_mcp_server_session(server_params) as session:
                await session.initialize()
                
                # Get list of available tools from the server
                tools_response = await session.list_tools()
                
                # Process the tools for LLM use
                self._mcp_tools = []
                for tool in tools_response.tools:
                    try:
                        # Store the original tool
                        self._mcp_tools.append(tool)
                    except Exception as e:
                        self.logger.warning(f"Failed to process tool {tool.name}: {str(e)}")
                
                # from autogen_ext.tools.mcp._factory import mcp_server_tools
                # tools = await mcp_server_tools(server_params)
                # for tool in tools:
                #     comp = tool.dump_component().model_dump_json()
                #     print(comp)
                
                self.logger.info(f"Initialized MCP session with {len(self._mcp_tools)} tools.")
                self._mcp_initialized = True
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP session: {str(e)}")
            raise RuntimeError(f"Failed to initialize MCP session: {str(e)}")

    async def on_messages(self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken) -> Response:
        """Handle incoming messages and return a response."""
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                return message
        raise AssertionError("The stream should have returned the final result.")

    async def on_messages_stream(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[AgentEvent | ChatMessage | Response, None]:
        """Stream responses for incoming messages."""
        # First, make sure we have the MCP session initialized
        await self._lazy_init(cancellation_token)
        
        # Process incoming messages
        for chat_message in messages:
            if isinstance(chat_message, (TextMessage, MultiModalMessage)):
                self._chat_history.append(UserMessage(content=chat_message.content, source=chat_message.source))
            else:
                raise ValueError(f"Unexpected message type in InsuranceAgent: {chat_message}")
        
        # Add a system message if this is the first message
        if len(self._chat_history) == 1:
            self._chat_history.insert(0, SystemMessage(content=self.system_message))
        
        try:
            # Get tool list to pass to the model
            tool_schemas = []
            for tool in self._mcp_tools:
                # Ensure we have a valid JSON string
                input_schema = tool.inputSchema
                if isinstance(input_schema, dict):
                    input_schema_str = json.dumps(input_schema)
                else:
                    input_schema_str = input_schema
                
                # Parse the schema
                schema_dict = json.loads(input_schema_str)
                
                # Create a tool schema
                schema = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": schema_dict,
                }
                tool_schemas.append(schema)
            
            # Start the conversation
            response = await self._model_client.create(
                messages=self._chat_history,
                tools=tool_schemas,
                cancellation_token=cancellation_token,
            )
            
            # Keep track of all intermediate events
            all_inner_messages = []
            
            # Process the conversation turn by turn
            while True:
                if isinstance(response.content, str):
                    # Final text response: last one in the list, return it
                    self._chat_history.append(AssistantMessage(content=response.content, source=self.name))
                    yield Response(
                        chat_message=TextMessage(content=response.content, source=self.name),
                        inner_messages=all_inner_messages,
                    )
                    return
                    
                if isinstance(response.content, list) and len(response.content) > 0:
                    # Tool calls - execute one by one
                    for tool_call in response.content:
                        # Log the tool call
                        tool_call_msg = ToolCallRequestEvent(source=self.name, content=[tool_call])
                        all_inner_messages.append(tool_call_msg)
                        yield tool_call_msg
                        
                        # Execute the tool
                        result = await self._execute_tool(tool_call.name, json.loads(tool_call.arguments), cancellation_token)
                        
                        if isinstance(result, list):
                            # Convert list to string representation
                            result_str = str(result)
                        elif not isinstance(result, str):
                            # Convert any non-string to string
                            result_str = str(result)
                        else:
                            result_str = result

                        execution_result = FunctionExecutionResult(
                            content=result_str,  # Guaranteed to be a string
                            call_id=tool_call.id,
                            name=tool_call.name,
                            is_error=False
                        )
                        
                        # Log the result
                        tool_result_msg = ToolCallExecutionEvent(source=self.name, content=[execution_result])
                        all_inner_messages.append(tool_result_msg)
                        yield tool_result_msg
                        
                        # Update history
                        self._chat_history.append(AssistantMessage(content=[tool_call], source=self.name))
                        self._chat_history.append(FunctionExecutionResultMessage(content=[execution_result]))
                        
                        # Get next response
                        response = await self._model_client.create(
                            messages=self._chat_history,
                            tools=tool_schemas,
                            cancellation_token=cancellation_token,
                        )
                else:
                    # No tool calls and no text response - something went wrong
                    error_msg = "The model did not provide a valid response"
                    yield Response(
                        chat_message=TextMessage(content=error_msg, source=self.name),
                        inner_messages=all_inner_messages,
                    )
                    return
                
        except Exception as e:
            error_msg = f"InsuranceAgent encountered an error: {str(e)}\n{traceback.format_exc()}"
            self.logger.error(error_msg)
            self._chat_history.append(AssistantMessage(content=error_msg, source=self.name))
            yield Response(chat_message=TextMessage(content=error_msg, source=self.name))

    async def _execute_tool(
        self, tool_name: str, arguments: Dict[str, Any], cancellation_token: CancellationToken
    ) -> str:
        """Execute a tool call via the MCP server."""
        # Create server parameters
        server_params = SseServerParams(
            url=self._sse_url,
            headers=self._sse_headers,
            timeout=self._sse_timeout,
        )
        
        try:
            # Create a new session for this tool call
            async with create_mcp_server_session(server_params) as session:
                await session.initialize()
                
                # Execute the tool call
                self.logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")
                
                # IMPORTANT: Pass arguments as a dictionary, not a JSON string
                # Call the tool with proper error handling
                try:
                    # Pass arguments directly as a dictionary - do NOT convert to a string
                    result = await session.call_tool(tool_name, arguments)
                    
                    if result.isError:
                        error_msg = f"Tool execution failed: {result.content}"
                        self.logger.error(error_msg)
                        return error_msg
                    
                    return result.content
                except asyncio.CancelledError:
                    return "Tool execution was cancelled"
                except Exception as e:
                    tb = traceback.format_exc()
                    self.logger.error(f"Detailed error in tool execution: {str(e)}\n{tb}")
                    return f"Error in tool execution: {str(e)}"
        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(f"Detailed error creating MCP session: {str(e)}\n{tb}")
            return f"Error executing tool {tool_name}: {str(e)}"

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """Reset the agent's state."""
        self._chat_history.clear()
        # Keep MCP session initialized

    def _to_config(self) -> McpSseAgentConfig:
        """Convert to config for serialization."""
        return McpSseAgentConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            description=self.description,
            system_message=self.system_message,
            sse_url=self._sse_url,
            sse_headers=self._sse_headers,
            sse_timeout=self._sse_timeout,
            mcp_tools=[tool.dump_component() for tool in self._mcp_tools],
        )

    @classmethod
    def _from_config(cls, config: McpSseAgentConfig) -> Self:
        """Create from config for deserialization."""
        from autogen_core.models import ChatCompletionClient
        
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            description=config.description or cls.DEFAULT_DESCRIPTION,
            system_message=config.system_message,
            sse_url=config.sse_url,
            sse_headers=config.sse_headers,
            sse_timeout=config.sse_timeout,
            mcp_tools=[tool.load_component() for tool in config.mcp_tools],
        )