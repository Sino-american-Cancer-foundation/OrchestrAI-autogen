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

from autogen_agentchat.agents import BaseChatAgent
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
    ToolCallExecutionEvent
)

from autogen_agentchat.base import TaskResult, Response, Handoff as HandoffBase
from autogen_agentchat.utils import content_to_str, remove_images
from autogen_core import CancellationToken, Component, ComponentModel, FunctionCall, RoutedAgent
from autogen_core.tools import BaseTool, FunctionTool

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
)

from autogen_ext.tools.mcp import (
    McpServerParams,
    SseMcpToolAdapter,
    StdioMcpToolAdapter,
    mcp_server_tools,
)
from pydantic import BaseModel
from typing_extensions import Self

event_logger = logging.getLogger("probill.events")
UserContent = Union[str, List[Union[str, Image]]]

class MCPToolExecutionResult(FunctionExecutionResult):
    """MCP tool execution result contains the output of a function call."""

    content: List[Union[str, Image]]
    """The output of the MCP tool call."""

    name: str
    """The name of the MCP tool that was called."""

    call_id: str
    """The ID of the MCP tool call. Note this ID may be empty for some models."""

    is_error: bool | None = None
    """Whether the MCP tool call resulted in an error."""

    is_multi_modal_message: bool | None = None
    """Whether the MCP tool call resulted a multi modal message."""

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
            elif isinstance(c, Image):
                if image_placeholder is not None:
                    text += f" {image_placeholder}"
                else:
                    text += f" {c.to_base64()}"
        return text
    
    class ConfigDict:
        arbitrary_types_allowed = True

class MCPToolExecutionResultMessage(MultiModalMessage):
    """MCP tool execution result message contains the output of multiple function calls."""

    content: List[MCPToolExecutionResult]
    # type: Literal["FunctionExecutionResultMessage"] = "FunctionExecutionResultMessage"

    def to_model_text(self, image_placeholder: str | None = "[image]") -> str:
        """Convert the content of the message to a string-only representation.
        If an image is present, it will be replaced with the image placeholder
        by default, otherwise it will be a base64 string when set to None.
        """
        text = ""
        for result in self.content:
            for c in result:
                if isinstance(c, str):
                    text += c
                elif isinstance(c, Image):
                    if image_placeholder is not None:
                        text += f" {image_placeholder}"
                    else:
                        text += f" {c.to_base64()}"
        return text

    def to_campatible_messgae(self):
        # Convert each MCPToolExecutionResult to plain text content
        results = []
        for result in self.content:
            # If the content is multimodal, convert to text format
            results.append(FunctionExecutionResult(content=content_to_str(result.content), call_id=result.call_id, name=result.name,is_error=result.is_error))
        # Return a FunctionExecutionResultMessage with the text content
        return FunctionExecutionResultMessage(content=results)

    def to_text(self, iterm: bool = False) -> str:
        result: List[str] = []
        for result in self.content:
            for c in result:
                if isinstance(c, str):
                    result.append(c)
                else:
                    if iterm:
                        # iTerm2 image rendering protocol: https://iterm2.com/documentation-images.html
                        image_data = c.to_base64()
                        result.append(f"\033]1337;File=inline=1:{image_data}\a\n")
                    else:
                        result.append("<image>")
        return "\n".join(result)
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
    server_params: McpServerParams | None = None
    system_message: str | None = None
    reflect_on_tool_use: bool = False
    model_client_stream: bool = False
    tools: List[ComponentModel] | None
    handoffs: List[HandoffBase | str] | None = None
    model_context: ComponentModel | None = None
    memory: List[ComponentModel] | None = None
    tool_call_summary_format: str
    metadata: Dict[str, str] | None = None

class McpHostAgent(BaseChatAgent, Component[McpHostAgentConfig], RoutedAgent):
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
    component_provider_override = "probill.agents.McpHostAgent"

    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        *,
        tools: List[BaseTool[Any, Any] | Callable[..., Any] | Callable[..., Awaitable[Any]]] | None = None,
        handoffs: List[HandoffBase | str] | None = None,
        model_context: ChatCompletionContext | None = None,
        description: str | None = None,
        server_params: McpServerParams | None = None,
        system_message: str | None = None,
        reflect_on_tool_use: bool = False,
        model_client_stream: bool = False,
        tool_call_summary_format: str = "{result}",
        memory: Sequence[Memory] | None = None,
        metadata: Dict[str, str] | None = None,        
    ):
        super().__init__(
            name=name, 
            description=description or "An MCP host agent that can connect to MCP servers and manage their tools.",
        )
        self._metadata = metadata or {}
        self._model_client = model_client
        self._model_client_stream = model_client_stream
        self._memory = None        
        if memory is not None:
            if isinstance(memory, list):
                self._memory = memory
            else:
                raise TypeError(f"Expected Memory, List[Memory], or None, got {type(memory)}")

        self._system_messages: List[SystemMessage] = []
        if system_message is None:
            self._system_messages = [
                SystemMessage(content="You are an MCP host agent. Use the tools provided by the MCP server to assist the user.")
            ]
        else:
            self._system_messages = [SystemMessage(content=system_message)]

        self._server_params = server_params
        self._tools: List[StdioMcpToolAdapter | SseMcpToolAdapter] = []

        # Handoff tools.
        self._handoff_tools: List[BaseTool[Any, Any]] = []
        self._handoffs: Dict[str, HandoffBase] = {}
        if handoffs is not None:
            if model_client.model_info["function_calling"] is False:
                raise ValueError("The model does not support function calling, which is needed for handoffs.")
            for handoff in handoffs:
                if isinstance(handoff, str):
                    handoff = HandoffBase(target=handoff)
                if isinstance(handoff, HandoffBase):
                    self._handoff_tools.append(handoff.handoff_tool)
                    self._handoffs[handoff.name] = handoff
                else:
                    raise ValueError(f"Unsupported handoff type: {type(handoff)}")

        if model_context is not None:
            self._model_context = model_context
        else:
            self._model_context = UnboundedChatCompletionContext()

        self._chat_history: List[LLMMessage] = []
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self._initialized = False
        self._reflect_on_tool_use = reflect_on_tool_use
        self._model_client_stream = model_client_stream
        self._tool_call_summary_format = tool_call_summary_format
        self._is_running = False        

    async def _lazy_init(self) -> None:
        """Initialize the MCP connection and fetch tools on first use."""
        if self._initialized or not self._server_params:
            return
        try:
            # Fetch all available tools from the MCP server
            self._tools = await mcp_server_tools(self._server_params)
            self._initialized = True

            tool_names = [tool.name for tool in self._tools]
            # Check if handoff tool names are unique.
            handoff_tool_names = [tool.name for tool in self._handoff_tools]
            if len(handoff_tool_names) != len(set(handoff_tool_names)):
                raise ValueError(f"Handoff names must be unique: {handoff_tool_names}")
            # Check if handoff tool names not in tool names.
            if any(name in tool_names for name in handoff_tool_names):
                raise ValueError(
                    f"Handoff names must be unique from tool names. "
                    f"Handoff names: {handoff_tool_names}; tool names: {tool_names}"
                )

            self.logger.info(f"Initialized MCP connection with {len(self._tools)} tools")
        except Exception as e:
            print("Failed MCP connection...", flush=True)
            self.logger.error(f"Failed to initialize MCP connection: {e}")

    @property
    def produced_message_types(self) -> Sequence[type[ChatMessage]]:
        message_types: List[type[ChatMessage]] = [TextMessage]
        if self._handoffs:
            message_types.append(HandoffMessage)
        if self._tools:
            message_types.append(ToolCallSummaryMessage)
        return tuple(message_types)

    @property
    def model_context(self) -> ChatCompletionContext:
        """
        The model context in use by the agent.
        """
        return self._model_context

    async def on_messages(self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken) -> Response:
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                return message
        raise AssertionError("The stream should have returned the final result.")

    async def on_messages_stream(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[AgentEvent | ChatMessage | Response, None]:
        """
        Process the incoming messages with the assistant agent and yield events/responses as they happen.
        """
        await self._lazy_init()
        # Gather all relevant state here
        agent_name = self.name
        model_context = self._model_context
        memory = self._memory
        system_messages = self._system_messages
        tools = self._tools
        handoff_tools = self._handoff_tools
        handoffs = self._handoffs
        model_client = self._model_client
        model_client_stream = self._model_client_stream
        reflect_on_tool_use = self._reflect_on_tool_use
        tool_call_summary_format = self._tool_call_summary_format

        # STEP 1: Add new user/handoff messages to the model context
        await self._add_messages_to_context(
            model_context=model_context,
            messages=messages,
        )

        # STEP 2: Update model context with any relevant memory
        inner_messages: List[AgentEvent | ChatMessage] = []
        for event_msg in await self._update_model_context_with_memory(
            memory=memory,
            model_context=model_context,
            agent_name=agent_name,
        ):
            inner_messages.append(event_msg)
            yield event_msg

        # STEP 3: Run the first inference
        model_result = None
        async for inference_output in self._call_llm(
            model_client=model_client,
            model_client_stream=model_client_stream,
            system_messages=system_messages,
            model_context=model_context,
            tools=tools,
            handoff_tools=handoff_tools,
            agent_name=agent_name,
            cancellation_token=cancellation_token,
        ):
            if isinstance(inference_output, CreateResult):
                model_result = inference_output
            else:
                # Streaming chunk event
                yield inference_output

        assert model_result is not None, "No model result was produced."

        # --- NEW: If the model produced a hidden "thought," yield it as an event ---
        if model_result.thought:
            thought_event = ThoughtEvent(content=model_result.thought, source=agent_name)
            yield thought_event
            inner_messages.append(thought_event)

        # Add the assistant message to the model context (including thought if present)
        await model_context.add_message(
            AssistantMessage(
                content=model_result.content,
                source=agent_name,
                thought=getattr(model_result, "thought", None),
            )
        )

        # STEP 4: Process the model output
        async for output_event in self._process_model_result(
            model_result=model_result,
            inner_messages=inner_messages,
            cancellation_token=cancellation_token,
            agent_name=agent_name,
            system_messages=system_messages,
            model_context=model_context,
            tools=tools,
            handoff_tools=handoff_tools,
            handoffs=handoffs,
            model_client=model_client,
            model_client_stream=model_client_stream,
            reflect_on_tool_use=reflect_on_tool_use,
            tool_call_summary_format=tool_call_summary_format,
        ):
            yield output_event

    @staticmethod
    async def _add_messages_to_context(
        model_context: ChatCompletionContext,
        messages: Sequence[ChatMessage],
    ) -> None:
        """
        Add incoming messages to the model context.
        """
        for msg in messages:
            if isinstance(msg, HandoffMessage):
                for llm_msg in msg.context:
                    await model_context.add_message(llm_msg)
            await model_context.add_message(msg.to_model_message())

    @staticmethod
    async def _update_model_context_with_memory(
        memory: Optional[Sequence[Memory]],
        model_context: ChatCompletionContext,
        agent_name: str,
    ) -> List[MemoryQueryEvent]:
        """
        If memory modules are present, update the model context and return the events produced.
        """
        events: List[MemoryQueryEvent] = []
        if memory:
            for mem in memory:
                update_context_result = await mem.update_context(model_context)
                if update_context_result and len(update_context_result.memories.results) > 0:
                    memory_query_event_msg = MemoryQueryEvent(
                        content=update_context_result.memories.results,
                        source=agent_name,
                    )
                    events.append(memory_query_event_msg)
        return events

    @classmethod
    async def _call_llm(
        cls,
        model_client: ChatCompletionClient,
        model_client_stream: bool,
        system_messages: List[SystemMessage],
        model_context: ChatCompletionContext,
        tools: List[BaseTool[Any, Any]],
        handoff_tools: List[BaseTool[Any, Any]],
        agent_name: str,
        cancellation_token: CancellationToken,
    ) -> AsyncGenerator[Union[CreateResult, ModelClientStreamingChunkEvent], None]:
        """
        Perform a model inference and yield either streaming chunk events or the final CreateResult.
        """
        all_messages = await model_context.get_messages()
        llm_messages = cls._get_compatible_context(model_client=model_client, messages=system_messages + all_messages)

        all_tools = tools + handoff_tools

        if model_client_stream:
            model_result: Optional[CreateResult] = None
            async for chunk in model_client.create_stream(
                llm_messages, tools=all_tools, cancellation_token=cancellation_token
            ):
                if isinstance(chunk, CreateResult):
                    model_result = chunk
                elif isinstance(chunk, str):
                    yield ModelClientStreamingChunkEvent(content=chunk, source=agent_name)
                else:
                    raise RuntimeError(f"Invalid chunk type: {type(chunk)}")
            if model_result is None:
                raise RuntimeError("No final model result in streaming mode.")
            yield model_result
        else:
            model_result = await model_client.create(
                llm_messages, tools=all_tools, cancellation_token=cancellation_token
            )
            yield model_result

    @classmethod
    async def _process_model_result(
        cls,
        model_result: CreateResult,
        inner_messages: List[AgentEvent | ChatMessage],
        cancellation_token: CancellationToken,
        agent_name: str,
        system_messages: List[SystemMessage],
        model_context: ChatCompletionContext,
        tools: List[BaseTool[Any, Any]],
        handoff_tools: List[BaseTool[Any, Any]],
        handoffs: Dict[str, HandoffBase],
        model_client: ChatCompletionClient,
        model_client_stream: bool,
        reflect_on_tool_use: bool,
        tool_call_summary_format: str,
    ) -> AsyncGenerator[AgentEvent | ChatMessage | Response, None]:
        """
        Handle final or partial responses from model_result, including tool calls, handoffs,
        and reflection if needed.
        """

        # If direct text response (string)
        if isinstance(model_result.content, str):
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
                    tools=tools,
                    handoff_tools=handoff_tools,
                    agent_name=agent_name,
                    cancellation_token=cancellation_token,
                )
                for call in model_result.content
            ]
        )
        exec_results = [result for _, result in executed_calls_and_results]

        # Yield ToolCallExecutionEvent
        tool_call_result_msg = MCPToolCallExecutionEvent(content=exec_results, source=agent_name)
        await model_context.add_message(MCPToolExecutionResultMessage(content=exec_results, source=agent_name))
        inner_messages.append(tool_call_result_msg)

        event_logger.debug(tool_call_result_msg)
        
        for result in exec_results:
            new_messages = []
            if result.is_multi_modal_message:
                sub_content = []
                for item in result.content:
                    sub_content.append(item)
                    if isinstance(item, Image):
                        yield MultiModalMessage(source=agent_name,content=[content_to_str(sub_content), item])
                        sub_content = []
                    else:
                        sub_content.append(item)
                if len(sub_content) > 0:
                    yield TextMessage(source=agent_name,content=content_to_str(sub_content))
            else: 
                yield TextMessage(source=agent_name,content=content_to_str(result.content))

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
    def _check_and_handle_handoff(
        model_result: CreateResult,
        executed_calls_and_results: List[Tuple[FunctionCall, MCPToolExecutionResult]],
        inner_messages: List[AgentEvent | ChatMessage],
        handoffs: Dict[str, HandoffBase],
        agent_name: str,
    ) -> Optional[Response]:
        """
        Detect handoff calls, generate the HandoffMessage if needed, and return a Response.
        If multiple handoffs exist, only the first is used.
        """
        handoff_reqs = [
            call for call in model_result.content if isinstance(call, FunctionCall) and call.name in handoffs
        ]
        if len(handoff_reqs) > 0:
            # We have at least one handoff function call
            selected_handoff = handoffs[handoff_reqs[0].name]

            if len(handoff_reqs) > 1:
                warnings.warn(
                    (
                        f"Multiple handoffs detected. Only the first is executed: "
                        f"{[handoffs[c.name].name for c in handoff_reqs]}. "
                        "Disable parallel tool calls in the model client to avoid this warning."
                    ),
                    stacklevel=2,
                )

            # Collect normal tool calls (not handoff) into the handoff context
            tool_calls: List[FunctionCall] = []
            tool_call_results: List[FunctionExecutionResult] = []
            # Collect the results returned by handoff_tool. By default, the message attribute will returned.
            selected_handoff_message = selected_handoff.message
            for exec_call, exec_result in executed_calls_and_results:
                if exec_call.name not in handoffs:
                    tool_calls.append(exec_call)
                    tool_call_results.append(exec_result)
                elif exec_call.name == selected_handoff.name:
                    selected_handoff_message = exec_result.content

            handoff_context: List[LLMMessage] = []
            if len(tool_calls) > 0:
                # Include the thought in the AssistantMessage if model_result has it
                handoff_context.append(
                    AssistantMessage(
                        content=tool_calls,
                        source=agent_name,
                        thought=getattr(model_result, "thought", None),
                    )
                )
                handoff_context.append(FunctionExecutionResultMessage(content=tool_call_results))

            # Return response for the first handoff
            return Response(
                chat_message=HandoffMessage(
                    content=selected_handoff_message,
                    target=selected_handoff.target,
                    source=agent_name,
                    context=handoff_context,
                ),
                inner_messages=inner_messages,
            )
        return None

    @classmethod
    async def _reflect_on_tool_use_flow(
        cls,
        system_messages: List[SystemMessage],
        model_client: ChatCompletionClient,
        model_client_stream: bool,
        model_context: ChatCompletionContext,
        agent_name: str,
        inner_messages: List[AgentEvent | ChatMessage],
    ) -> AsyncGenerator[Response | ModelClientStreamingChunkEvent | ThoughtEvent, None]:
        """
        If reflect_on_tool_use=True, we do another inference based on tool results
        and yield the final text response (or streaming chunks).
        """
        all_messages = system_messages + await model_context.get_messages()
        llm_messages = cls._get_compatible_context(model_client=model_client, messages=all_messages)

        if model_client_stream:
            async for chunk in model_client.create_stream(llm_messages):
                if isinstance(chunk, CreateResult):
                    reflection_result = chunk
                elif isinstance(chunk, str):
                    yield ModelClientStreamingChunkEvent(content=chunk, source=agent_name)
                else:
                    raise RuntimeError(f"Invalid chunk type: {type(chunk)}")
        else:
            reflection_result = await model_client.create(llm_messages)

        if not reflection_result or not isinstance(reflection_result.content, str):
            raise RuntimeError("Reflect on tool use produced no valid text response.")

        # --- NEW: If the reflection produced a thought, yield it ---
        if reflection_result.thought:
            thought_event = ThoughtEvent(content=reflection_result.thought, source=agent_name)
            yield thought_event
            inner_messages.append(thought_event)

        # Add to context (including thought if present)
        await model_context.add_message(
            AssistantMessage(
                content=reflection_result.content,
                source=agent_name,
                thought=getattr(reflection_result, "thought", None),
            )
        )

        yield Response(
            chat_message=TextMessage(
                content=reflection_result.content,
                source=agent_name,
                models_usage=reflection_result.usage,
            ),
            inner_messages=inner_messages,
        )

    @staticmethod
    def _summarize_tool_use(
        executed_calls_and_results: List[Tuple[FunctionCall, MCPToolExecutionResult]],
        inner_messages: List[AgentEvent | ChatMessage],
        handoffs: Dict[str, HandoffBase],
        tool_call_summary_format: str,
        agent_name: str,
    ) -> Response:
        """
        If reflect_on_tool_use=False, create a summary message of all tool calls.
        """
        # Filter out calls which were actually handoffs
        normal_tool_calls = [(call, result) for call, result in executed_calls_and_results if call.name not in handoffs]
        tool_call_summaries: List[str] = []
        for tool_call, tool_call_result in normal_tool_calls:
            tool_call_summaries.append(
                tool_call_summary_format.format(
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    result=tool_call_result.content,
                )
            )
        tool_call_summary = "\n".join(tool_call_summaries)
        return Response(
            chat_message=ToolCallSummaryMessage(
                content=tool_call_summary,
                source=agent_name,
            ),
            inner_messages=inner_messages,
        )

    @staticmethod
    async def _execute_tool_call(
        tool_call: FunctionCall,
        tools: List[BaseTool[Any, Any]],
        handoff_tools: List[BaseTool[Any, Any]],
        agent_name: str,
        cancellation_token: CancellationToken,
    ) -> Tuple[FunctionCall, MCPToolExecutionResult]:
        """Execute a single tool call and return the result."""
        try:
            all_tools = tools + handoff_tools
            if not all_tools:
                raise ValueError("No tools are available.")
            tool = next((t for t in all_tools if t.name == tool_call.name), None)
            if tool is None:
                raise ValueError(f"The tool '{tool_call.name}' is not available.")
            arguments: Dict[str, Any] = json.loads(tool_call.arguments) if tool_call.arguments else {}
            results = await tool.run_json(arguments, cancellation_token)

            content = []
            is_multi_modal_message = False

            for result in results:
                if result.type == "image":
                    content.append(Image.from_base64(result.data))
                    is_multi_modal_message = True
                elif result.type == "text":
                    content.append(result.text)

            return (
                tool_call,
                MCPToolExecutionResult(
                    source=agent_name,
                    content=content,
                    is_multi_modal_message=is_multi_modal_message,
                    call_id=tool_call.id,
                    is_error=False,
                    name=tool_call.name,
                ),
            )
        except Exception as e:
            return (
                tool_call,
                MCPToolExecutionResult(
                    content=[f"Error: {e}"],
                    call_id=tool_call.id,
                    is_error=True,
                    name=tool_call.name,
                ),
            )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """Reset the assistant agent to its initialization state."""
        await self._model_context.clear()

    async def save_state(self) -> Mapping[str, Any]:
        """Save the current state of the assistant agent."""
        model_context_state = await self._model_context.save_state()
        return AssistantAgentState(llm_context=model_context_state).model_dump()

    async def load_state(self, state: Mapping[str, Any]) -> None:
        """Load the state of the assistant agent"""
        assistant_agent_state = AssistantAgentState.model_validate(state)
        # Load the model context state.
        await self._model_context.load_state(assistant_agent_state.llm_context)

    @staticmethod
    def _get_compatible_context(model_client: ChatCompletionClient, messages: List[LLMMessage]) -> Sequence[LLMMessage]:
        """Ensure that the messages are compatible with the underlying client, by removing images if needed."""
        if model_client.model_info["vision"]:
            return messages
        else:
            str_messages: List[LLMMessage] = []
            for message in messages:
                if isinstance(message, UserMessage) and isinstance(message.content, list):
                    str_messages.append(UserMessage(content=content_to_str(message.content), source=message.source))
                elif isinstance(message, MCPToolExecutionResultMessage):
                    str_messages.append(message.to_campatible_messgae())
                else:
                    str_messages.append(message)
            return str_messages

    def _to_config(self) -> McpHostAgentConfig:
        """Convert the MCP tool agent to a declarative config."""
        tool_to_dump = []
        if self._tools is not None:
            for tool in self._tools:
                if not isinstance(tool, (StdioMcpToolAdapter, SseMcpToolAdapter)):
                    tool_to_dump.append(tool)        
        return McpHostAgentConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            tools=[tool.dump_component() for tool in tool_to_dump],
            handoffs=list(self._handoffs.values()) if self._handoffs else None,
            model_context=self._model_context.dump_component(),
            memory=[memory.dump_component() for memory in self._memory] if self._memory else None,
            description=self.description,
            system_message=self._system_messages[0].content
            if self._system_messages and isinstance(self._system_messages[0].content, str)
            else None,
            model_client_stream=self._model_client_stream,
            reflect_on_tool_use=self._reflect_on_tool_use,
            tool_call_summary_format=self._tool_call_summary_format,
            metadata=self._metadata,
            server_params=self._server_params           
        )

    @classmethod
    def _from_config(cls, config: McpHostAgentConfig) -> Self:
        """Create an MCP tool agent from a declarative config."""
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            tools=[BaseTool.load_component(tool) for tool in config.tools] if config.tools else None,
            handoffs=config.handoffs,
            model_context=None,
            memory=[Memory.load_component(memory) for memory in config.memory] if config.memory else None,
            description=config.description,
            system_message=config.system_message,
            model_client_stream=config.model_client_stream,
            reflect_on_tool_use=config.reflect_on_tool_use,
            tool_call_summary_format=config.tool_call_summary_format,
            metadata=config.metadata,
            server_params=config.server_params        
        )