import asyncio
import logging
import warnings
import json
import ast
import traceback
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
    Literal
)

from autogen_core.model_context import (
    ChatCompletionContext,
    UnboundedChatCompletionContext,
)

from autogen_core.memory import Memory

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.state import AssistantAgentState
from autogen_agentchat.messages import (
    UserMessage,
    AgentEvent,
    ChatMessage,
    HandoffMessage,
    MemoryQueryEvent,
    ModelClientStreamingChunkEvent,
    TextMessage,
    ThoughtEvent,
    ToolCallRequestEvent,
    ToolCallSummaryMessage,
    MultiModalMessage,
    ToolCallExecutionEvent,
    BaseAgentEvent,
    BaseChatMessage,
)

from autogen_agentchat.base import TaskResult, Response, Handoff as HandoffBase
from autogen_agentchat.utils import content_to_str, remove_images
from autogen_core import CancellationToken, Component, ComponentModel, FunctionCall, Image as agImage
from autogen_core.tools import BaseTool, Workbench, ImageResultContent, TextResultContent
import base64

from autogen_core import Image
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    CreateResult,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    ModelFamily,
    SystemMessage,
    UserMessage,
)

from autogen_ext.tools.mcp import (
    McpServerParams,
    SseMcpToolAdapter,
    StdioMcpToolAdapter,
    mcp_server_tools,
    StdioServerParams,  # Add explicit imports
    SseServerParams,    # Add explicit imports
)
from pydantic import BaseModel
from typing_extensions import Self
from autogen_agentchat.messages import StructuredMessage
from probill.tools.mcp import McpsWorkbench
# Define the server params checking function directly in this file to avoid circular imports
def check_and_create_server_params(server_params: Any) -> Any:
    """
    Determine the type of server_params and create the appropriate object if it's a dict.
    
    Args:
        server_params: Can be StdioServerParams, SseServerParams, dict, or None
        
    Returns:
        The correct server_params object based on the input type
    """
    # If already correct type, return as is
    if server_params is None:
        return None
    elif hasattr(server_params, '__class__') and server_params.__class__.__name__ in ('StdioServerParams', 'SseServerParams', 'McpServerParams'):
        return server_params
    elif isinstance(server_params, dict):
        # Determine server_params type from dict and create appropriate object
        if "command" in server_params:  # StdioServerParams
            return StdioServerParams(
                command=server_params["command"],
                args=server_params.get("args", []),
                env=server_params.get("env", {}),
                read_timeout_seconds=server_params.get("read_timeout_seconds", 5.0)
            )
        elif "url" in server_params:  # SseServerParams
            return SseServerParams(
                url=server_params["url"],
                headers=server_params.get("headers"),
                timeout=server_params.get("timeout", 5.0),
                sse_read_timeout=server_params.get("sse_read_timeout", 300.0)
            )
        else:
            raise ValueError(f"Cannot determine server_params type from dict: {server_params}")
    else:
        raise TypeError(f"Unsupported server_params type: {type(server_params)}")

event_logger = logging.getLogger("probill.events")
UserContent = Union[str, List[Union[str, Image]]]

class MCPToolExecutionResult(FunctionExecutionResult):
    """MCP tool execution result contains the output of a function call."""

    content: List[str | agImage]
    """The output of the MCP tool call."""

    name: str
    """The name of the MCP tool that was called."""

    call_id: str
    """The ID of the MCP tool call. Note this ID may be empty for some models."""

    is_error: bool | None = None
    """Whether the MCP tool call resulted in an error."""

    def to_text(self) -> str:
        return content_to_str(self.content)
        
    def to_model_text(self, image_placeholder: str | None = "[image]") -> str:
        """Convert the content of the message to a string-only representation.
        If an image is present, it will be replaced with the image placeholder
        by default, otherwise it will be a base64 string when set to None.
        """
        text = ""
        for c in self.content:
            if isinstance(c, str):
                text += c
            elif isinstance(c, agImage):
                if image_placeholder is not None:
                    text += f" {image_placeholder}"
                else:
                    # Use the to_base64 method when available
                    if hasattr(c, 'to_base64'):
                        text += f" {c.to_base64()}"
                    else:
                        text += " [image data not available]"
        return text

    class ConfigDict:
        arbitrary_types_allowed = True

class MCPToolExecutionResultMessage(BaseChatMessage):
    """MCP tool execution result message contains the output of multiple function calls."""
    content: List[str | agImage]
    type: Literal["MultiModalMessage", "TextMessage"]
    is_multi_modal_message: bool = False

    def __init__(self, results: List[MCPToolExecutionResult], **kwargs):
        content_items = []
        message_type = "TextMessage"
        is_multi_modal = False
        
        for result in results:
            for item in result.content:
                content_items.append(item)
                if isinstance(item, agImage):
                    message_type = "MultiModalMessage"   
                    is_multi_modal = True             
                            
        # Set type if not provided in kwargs
        if 'type' not in kwargs:
            kwargs['type'] = message_type
            
        # Call super().__init__ first before setting instance attributes
        super().__init__(content=content_items, **kwargs)
        self.is_multi_modal_message = is_multi_modal

    def to_oai_type(self, model_client_vision: bool = False) -> LLMMessage:
        """Convert the content of the message to a LLMMessage."""
        if self.type == "MultiModalMessage" and model_client_vision:
            # If the model client supports vision, convert to LLMMessage
            return MultiModalMessage(
                content=self.content,
                source=self.source,
            )
        else:
            # Otherwise, convert to LLMMessage with text content
            return TextMessage(
                content=self.to_model_text(),
                source=self.source,
            )
    
    def to_model_message(self) -> UserMessage:
        """Convert the content of the message to a UserMessage."""
        return UserMessage(content=self.content, source=self.source)
    
    def to_model_text(self, image_placeholder: str | None = "[image]") -> str:
        """Convert the content of the message to a string-only representation.
        If an image is present, it will be replaced with the image placeholder
        by default, otherwise it will be a base64 string when set to None.
        """
        text = ""
        for c in self.content:
            if isinstance(c, str):
                text += c
            elif isinstance(c, agImage):
                if image_placeholder is not None:
                    text += f" {image_placeholder}"
                else:
                    # Use the to_base64 method when available
                    if hasattr(c, 'to_base64'):
                        text += f" {c.to_base64()}"
                    else:
                        text += " [image data not available]"
        return text

    def to_compatible_message(self):
        # Convert each MCPToolExecutionResult to plain text content
        results = []
        for result in self.content:
            # If the content is multimodal, convert to text format
            results.append(FunctionExecutionResult(content=content_to_str(result.content), call_id=result.call_id, name=result.name,is_error=result.is_error))
        # Return a FunctionExecutionResultMessage with the text content
        return FunctionExecutionResultMessage(content=results)

    def to_text(self, iterm: bool = False) -> str:
        results: List[str] = []
        for result in self.content:
            results.append(result.to_text())
        return "\n".join(results)
    
    class ConfigDict:
        arbitrary_types_allowed = True

class MCPToolCallExecutionEvent(ToolCallExecutionEvent):
    """An event signaling the execution of MCP tool calls."""

    content: List[MCPToolExecutionResult]

    """The MCP tool call results."""

    def to_text(self) -> str:
        return content_to_str(self.content)


class McpHostAgentConfig(BaseModel):
    """Configuration for the MCP Host Agent."""
    name: str
    model_client: ComponentModel
    description: str | None = None
    workbench: ComponentModel | None = None
    system_message: str | None = None
    reflect_on_tool_use: bool = False
    model_client_stream: bool = False
    handoffs: List[HandoffBase | str] | None = None
    model_context: ComponentModel | None = None
    memory: List[ComponentModel] | None = None
    tool_call_summary_format: str
    metadata: Dict[str, str] | None = None

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
        mcp_servers (List[McpServerParams], optional): List of parameters for connecting to multiple MCP servers
        server_params (McpServerParams, optional): Parameters for connecting to a single MCP server (deprecated)
    """

    component_type = "agent"
    component_config_schema = McpHostAgentConfig
    component_provider_override = "probill.agents.McpHostAgent"

    def __init__(
        self,
        *args,
        **kwargs
    ):
        super().__init__(
            *args,
            **kwargs
        )
        # if self._system_message is None:
        #     self._system_messages = [
        #         SystemMessage(content="You are an MCP host agent. Use the tools provided by the MCP server to assist the user.")
        #     ]

    @classmethod
    async def _process_model_result(
        cls,
        model_result: CreateResult,
        inner_messages: List[BaseAgentEvent | BaseChatMessage],
        cancellation_token: CancellationToken,
        agent_name: str,
        system_messages: List[SystemMessage],
        model_context: ChatCompletionContext,
        workbench: Workbench,
        handoff_tools: List[BaseTool[Any, Any]],
        handoffs: Dict[str, HandoffBase],
        model_client: ChatCompletionClient,
        model_client_stream: bool,
        reflect_on_tool_use: bool,
        tool_call_summary_format: str,
        output_content_type: type[BaseModel] | None,
        format_string: str | None = None,
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        """
        Handle final or partial responses from model_result, including tool calls, handoffs,
        and reflection if needed.
        """

        # If direct text response (string)
        if isinstance(model_result.content, str):
            if output_content_type:
                content = output_content_type.model_validate_json(model_result.content)
                yield Response(
                    chat_message=StructuredMessage[output_content_type](  # type: ignore[valid-type]
                        content=content,
                        source=agent_name,
                        models_usage=model_result.usage,
                        format_string=format_string,
                    ),
                    inner_messages=inner_messages,
                )
            else:
                yield Response(
                    chat_message=TextMessage(
                        content=model_result.content,
                        source=agent_name,
                        models_usage=model_result.usage,
                    ),
                    inner_messages=inner_messages,
                )
            return

        # Otherwise, we have function calls
        assert isinstance(model_result.content, list) and all(
            isinstance(item, FunctionCall) for item in model_result.content
        )

        # STEP 4A: Yield ToolCallRequestEvent
        tool_call_msg = ToolCallRequestEvent(
            content=model_result.content,
            source=agent_name,
            models_usage=model_result.usage,
        )
        event_logger.debug(tool_call_msg)
        inner_messages.append(tool_call_msg)
        yield tool_call_msg

        # STEP 4B: Execute tool calls
        executed_calls_and_results = await asyncio.gather(
            *[
                cls._execute_tool_call(
                    tool_call=call,
                    workbench=workbench,
                    handoff_tools=handoff_tools,
                    agent_name=agent_name,
                    cancellation_token=cancellation_token,
                )
                for call in model_result.content
            ]
        )
        exec_results = [result for _, result in executed_calls_and_results]

        # Yield ToolCallExecutionEvent
        tool_call_result_msg = MCPToolCallExecutionEvent(
            content=exec_results,
            source=agent_name,
        )
        event_logger.debug(tool_call_result_msg)
        mcp_msg = MCPToolExecutionResultMessage(results=exec_results, source=agent_name)
        await model_context.add_message(mcp_msg.to_model_message())
        inner_messages.append(tool_call_result_msg)

        if mcp_msg.is_multi_modal_message:
            # If the model client supports vision, convert to LLMMessage
            tool_call_result_msg = mcp_msg.to_oai_type(model_client_vision=True)
            yield TextMessage(
                content="M",
                source=agent_name,
            )
        else:
            # Otherwise, convert to LLMMessage with text content
            tool_call_result_msg = mcp_msg.to_oai_type(model_client_vision=False)
            yield TextMessage(
                content="T",
                source=agent_name,
            )
        yield tool_call_result_msg
        # for result in exec_results:
        #     new_messages = []
        #     if result.is_multi_modal_message:
        #         sub_content = []
        #         for item in result.content:
        #             sub_content.append(item)
        #             if isinstance(item, Image):
        #                 yield MultiModalMessage(source=agent_name,content=[content_to_str(sub_content), item])
        #                 sub_content = []
        #             else:
        #                 sub_content.append(item)
        #         if len(sub_content) > 0:
        #             yield TextMessage(source=agent_name,content=content_to_str(sub_content))
        #     else: 
        #         yield TextMessage(source=agent_name,content=content_to_str(result.content))

            # new_messages.extend(new_message)


        # STEP 4C: Check for handoff
        handoff_output = cls._check_and_handle_handoff(
            model_result=model_result,
            executed_calls_and_results=executed_calls_and_results,
            inner_messages=inner_messages,
            handoffs=handoffs,
            agent_name=agent_name,
        )
        if handoff_output:
            yield handoff_output
            return
        
        # STEP 4D: Reflect or summarize tool results
        if reflect_on_tool_use:
            async for reflection_response in cls._reflect_on_tool_use_flow(
                system_messages=system_messages,
                model_client=model_client,
                model_client_stream=model_client_stream,
                model_context=model_context,
                agent_name=agent_name,
                inner_messages=inner_messages,
                output_content_type=False,
            ):
                yield reflection_response
        else:
            yield cls._summarize_tool_use(
                executed_calls_and_results=executed_calls_and_results,
                inner_messages=inner_messages,
                handoffs=handoffs,
                tool_call_summary_format=tool_call_summary_format,
                agent_name=agent_name,
            )

    @staticmethod
    async def _execute_tool_call(
        tool_call: FunctionCall,
        workbench: Workbench,
        handoff_tools: List[BaseTool[Any, Any]],
        agent_name: str,
        cancellation_token: CancellationToken,
    ) -> Tuple[FunctionCall, FunctionExecutionResult]:
        """Execute a single tool call and return the result."""
        # Load the arguments from the tool call.
        try:
            arguments = json.loads(tool_call.arguments)
        except json.JSONDecodeError as e:
            return (
                tool_call,
                FunctionExecutionResult(
                    content=f"Error: {e}",
                    call_id=tool_call.id,
                    is_error=True,
                    name=tool_call.name,
                ),
            )

        # Check if the tool call is a handoff.
        # TODO: consider creating a combined workbench to handle both handoff and normal tools.
        for handoff_tool in handoff_tools:
            if tool_call.name == handoff_tool.name:
                # Run handoff tool call.
                result = await handoff_tool.run_json(arguments, cancellation_token)
                result_as_str = handoff_tool.return_value_as_string(result)
                return (
                    tool_call,
                    FunctionExecutionResult(
                        content=result_as_str,
                        call_id=tool_call.id,
                        is_error=False,
                        name=tool_call.name,
                    ),
                )

        # Handle normal tool call using workbench.
        result = await workbench.call_tool(
            name=tool_call.name,
            arguments=arguments,
            cancellation_token=cancellation_token,
        )

        return (
            tool_call,
            MCPToolExecutionResult(
                source=agent_name,
                content=[item.content for item in result.result],
                call_id=tool_call.id,
                is_error=False,
                name=tool_call.name,
            ),
        )
    
    @classmethod
    def _to_config(self) -> McpHostAgentConfig:
        """Convert the MCP tool agent to a declarative config."""
        tool_components = []
        if self._tools is not None:
            for tool in self._tools:
                if not isinstance(tool, (StdioMcpToolAdapter, SseMcpToolAdapter)):
                    tool_components.append(tool.dump_component())
        
        # Create config matching the structure expected by _from_config
        return McpHostAgentConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            workbench=self._workbench.dump_component() if hasattr(self, "_workbench") and self._workbench else None,
            handoffs=list(self._handoffs.values()) if self._handoffs else None,
            memory=[memory.dump_component() for memory in self._memory] if self._memory else None,
            description=self.description,
            system_message=self._system_messages[0].content
            if self._system_messages and isinstance(self._system_messages[0].content, str)
            else None,
            model_client_stream=self._model_client_stream,
            reflect_on_tool_use=self._reflect_on_tool_use,
            tool_call_summary_format=self._tool_call_summary_format,
            metadata=self._metadata,
        )

    @classmethod
    def _from_config(cls, config: McpHostAgentConfig) -> Self:
        """Create an MCP tool agent from a declarative config."""
        # Process mcp_servers to ensure they are the correct type
        # return super()._from_config(config)        
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            workbench=Workbench.load_component(config.workbench),
            handoffs=config.handoffs,
            model_context=None,
            memory=[Memory.load_component(memory) for memory in config.memory] if config.memory else None,
            description=config.description,
            system_message=config.system_message,
            model_client_stream=config.model_client_stream,
            reflect_on_tool_use=config.reflect_on_tool_use,
            tool_call_summary_format=config.tool_call_summary_format,
            metadata=config.metadata,
        )