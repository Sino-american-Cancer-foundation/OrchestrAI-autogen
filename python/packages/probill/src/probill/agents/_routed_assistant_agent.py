import asyncio
import json
import logging
import warnings
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

# Imports from autogen_core
from autogen_core import CancellationToken, Component, ComponentBase, ComponentModel, FunctionCall, MessageContext
from autogen_core._routed_agent import RoutedAgent, rpc # Import RoutedAgent and rpc decorator
from autogen_core.memory import Memory, MemoryContent
from autogen_core.model_context import (
    ChatCompletionContext,
    UnboundedChatCompletionContext,
    BufferedChatCompletionContext,
    TokenLimitedChatCompletionContext,
)
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    CreateResult,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    ModelFamily,
    SystemMessage,
    RequestUsage,
)
from autogen_core.tools import BaseTool, FunctionTool

# Imports from autogen_agentchat (Updated to absolute imports)
from autogen_agentchat import EVENT_LOGGER_NAME
from autogen_agentchat.base import Handoff as HandoffBase
# Note: Response object is not directly returned by handlers, but the contained message is.
from autogen_agentchat.messages import (
    BaseChatMessage,
    HandoffMessage,
    MemoryQueryEvent, # Kept for logging/internal logic
    StructuredMessage,
    StructuredMessageFactory,
    TextMessage,
    ThoughtEvent, # Kept for logging/internal logic
    ToolCallExecutionEvent, # Kept for logging/internal logic
    ToolCallRequestEvent, # Kept for logging/internal logic
    ToolCallSummaryMessage,
)
from autogen_agentchat.state import AssistantAgentState
from autogen_agentchat.utils import remove_images

# Imports from Pydantic/Typing Extensions
from pydantic import BaseModel
from typing_extensions import Self

event_logger = logging.getLogger(EVENT_LOGGER_NAME)

# Re-use AssistantAgentConfig
class RoutedAssistantAgentConfig(BaseModel):
    """The declarative configuration for the assistant agent."""
    name: str
    model_client: ComponentModel
    tools: List[ComponentModel] | None
    handoffs: List[HandoffBase | str] | None = None
    model_context: ComponentModel | None = None
    memory: List[ComponentModel] | None = None
    description: str
    system_message: str | None = None
    reflect_on_tool_use: bool
    tool_call_summary_format: str
    metadata: Dict[str, str] | None = None
    structured_message_factory: ComponentModel | None = None


# Define the new class inheriting from RoutedAgent and ComponentBase
class RoutedAssistantAgent(RoutedAgent, ComponentBase[RoutedAssistantAgentConfig]):
    """
    An agent that combines the assistance capabilities of AssistantAgent
    with the message routing mechanism of RoutedAgent.

    This agent processes incoming messages based on registered handlers
    (using @rpc, @event, etc.) and leverages LLMs, tools, and memory
    similar to AssistantAgent.

    Note: Unlike AssistantAgent's on_messages_stream, the handlers in
    RoutedAssistantAgent follow a request-response pattern and do not
    yield intermediate events or support model client streaming directly
    through the handler return value. Intermediate events are logged instead.
    """
    component_type = "agent"
    component_config_schema = RoutedAssistantAgentConfig
    component_provider_override = "probill.agents.RoutedAssistantAgent" # Update provider override

    # Indent __init__ and all subsequent methods to be part of the class
    def __init__(
            self,
            name: str,
            model_client: ChatCompletionClient,
            *,
            tools: List[BaseTool[Any, Any] | Callable[..., Any] | Callable[..., Awaitable[Any]]] | None = None,
            handoffs: List[HandoffBase | str] | None = None,
            model_context: ChatCompletionContext | None = None,
            description: str = "An agent that provides assistance with ability to use tools, routing messages.", # Modified description
            system_message: (
                str | None
            ) = "You are a helpful AI assistant. Solve tasks using your tools. Reply with TERMINATE when the task has been completed.",
            reflect_on_tool_use: bool | None = None,
            tool_call_summary_format: str = "{result}",
            output_content_type: type[BaseModel] | None = None,
            output_content_type_format: str | None = None,
            memory: Sequence[Memory] | None = None,
            metadata: Dict[str, str] | None = None,
        ):
            # Call RoutedAgent's __init__ first
            # The super().__init__ call needs to happen within the AgentInstantiationContext
            # which is handled by the AgentRuntime when registering the agent.
            # We still need to initialize the Component part.
            Component.__init__(self) # Explicitly call Component's init if needed, though often handled by metaclass/inheritance
            RoutedAgent.__init__(self, description=description) # Call RoutedAgent's init

            # --- Copy relevant initialization logic from AssistantAgent ---
            self.name = name
            self._metadata = metadata or {}
            self._model_client = model_client
            self._output_content_type: type[BaseModel] | None = output_content_type
            self._output_content_type_format = output_content_type_format
            self._structured_message_factory: StructuredMessageFactory | None = None
            if output_content_type is not None:
                self._structured_message_factory = StructuredMessageFactory(
                    input_model=output_content_type, format_string=output_content_type_format
                )

            self._memory = None
            if memory is not None:
                if isinstance(memory, list):
                    self._memory = memory
                else:
                    raise TypeError(f"Expected Memory, List[Memory], or None, got {type(memory)}")

            self._system_messages: List[SystemMessage] = []
            if system_message is None:
                self._system_messages = []
            else:
                self._system_messages = [SystemMessage(content=system_message)]

            self._tools: List[BaseTool[Any, Any]] = []
            if tools is not None:
                if model_client.model_info["function_calling"] is False:
                    raise ValueError("The model does not support function calling.")
                for tool in tools:
                    if isinstance(tool, BaseTool):
                        self._tools.append(tool)
                    elif callable(tool):
                        doc = getattr(tool, "__doc__", "")
                        description = doc if doc is not None else ""
                        self._tools.append(FunctionTool(tool, description=description))
                    else:
                        raise ValueError(f"Unsupported tool type: {type(tool)}")
            tool_names = [tool.name for tool in self._tools]
            if len(tool_names) != len(set(tool_names)):
                raise ValueError(f"Tool names must be unique: {tool_names}")

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
            handoff_tool_names = [tool.name for tool in self._handoff_tools]
            if len(handoff_tool_names) != len(set(handoff_tool_names)):
                raise ValueError(f"Handoff names must be unique: {handoff_tool_names}")
            if any(name in tool_names for name in handoff_tool_names):
                raise ValueError(
                    f"Handoff names must be unique from tool names. "
                    f"Handoff names: {handoff_tool_names}; tool names: {tool_names}"
                )

            if model_context is not None:
                self._model_context = model_context
            else:
                self._model_context = UnboundedChatCompletionContext()

            if self._output_content_type is not None and reflect_on_tool_use is None:
                self._reflect_on_tool_use = True
            elif reflect_on_tool_use is None:
                self._reflect_on_tool_use = False
            else:
                self._reflect_on_tool_use = reflect_on_tool_use
            if self._reflect_on_tool_use and ModelFamily.is_claude(model_client.model_info["family"]):
                warnings.warn(
                    "Claude models may not work with reflection on tool use because Claude requires that any requests including a previous tool use or tool result must include the original tools definition."
                    "Consider setting reflect_on_tool_use to False. "
                    "As an alternative, consider calling the agent in a loop until it stops producing tool calls. "
                    "See [Single-Agent Team](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/teams.html#single-agent-team) "
                    "for more details.",
                    UserWarning,
                    stacklevel=2,
                )
            self._tool_call_summary_format = tool_call_summary_format

    # --- Define the primary message handler ---
    @rpc
    async def process_message(
        self,
        message: Union[TextMessage, HandoffMessage], # Add other expected input types if needed
        ctx: MessageContext,
        cancellation_token: CancellationToken = CancellationToken(), # Add cancellation token if needed by logic
    ) -> Union[TextMessage, StructuredMessage, ToolCallSummaryMessage, HandoffMessage, None]:
        """
        Handles incoming messages (e.g., TextMessage, HandoffMessage) by invoking
        the core AssistantAgent logic (LLM calls, tool use, reflection, handoff).

        Args:
            message: The incoming message to process.
            ctx: The message context.
            cancellation_token: Token to signal cancellation.

        Returns:
            The final response message (TextMessage, StructuredMessage, ToolCallSummaryMessage,
            or HandoffMessage), or None if no explicit response is generated.
        """
        # --- Adapt logic from AssistantAgent.on_messages_stream ---
        # This adaptation converts the generator logic into a sequential flow
        # returning the final message. Intermediate events are logged but not returned.

        # Gather all relevant state (already available as self attributes)
        agent_name = self.name
        model_context = self._model_context
        memory = self._memory
        system_messages = self._system_messages
        tools = self._tools
        handoff_tools = self._handoff_tools
        handoffs = self._handoffs
        model_client = self._model_client
        reflect_on_tool_use = self._reflect_on_tool_use
        tool_call_summary_format = self._tool_call_summary_format
        output_content_type = self._output_content_type
        format_string = self._output_content_type_format

        # STEP 1: Add new message to the model context
        # Note: RoutedAgent passes a single message, not a sequence.
        await self._add_messages_to_context(
            model_context=model_context,
            messages=[message], # Wrap the single message in a list
        )

        # STEP 2: Update model context with any relevant memory
        memory_events = await self._update_model_context_with_memory(
            memory=memory,
            model_context=model_context,
            agent_name=agent_name,
        )
        # Log memory events if needed
        for event in memory_events:
            event_logger.debug(f"Memory Query Event: {event.content}")


        # STEP 3: Run the first inference (non-streaming)
        model_result = await self._call_llm_single( # Use a non-generator version
            model_client=model_client,
            system_messages=system_messages,
            model_context=model_context,
            tools=tools,
            handoff_tools=handoff_tools,
            agent_name=agent_name,
            cancellation_token=cancellation_token,
            output_content_type=output_content_type,
        )

        # Log thought if present
        if model_result.thought:
            thought_event = ThoughtEvent(content=model_result.thought, source=agent_name)
            event_logger.debug(thought_event)

        # Add the assistant message to the model context
        await model_context.add_message(
            AssistantMessage(
                content=model_result.content,
                source=agent_name,
                thought=getattr(model_result, "thought", None),
            )
        )

        # STEP 4: Process the model output
        final_message = await self._process_model_result_single( # Use a non-generator version
            model_result=model_result,
            cancellation_token=cancellation_token,
            agent_name=agent_name,
            system_messages=system_messages,
            model_context=model_context,
            tools=tools,
            handoff_tools=handoff_tools,
            handoffs=handoffs,
            model_client=model_client,
            reflect_on_tool_use=reflect_on_tool_use,
            tool_call_summary_format=tool_call_summary_format,
            output_content_type=output_content_type,
            format_string=format_string,
        )

        return final_message


    # --- Helper methods adapted or copied from AssistantAgent ---

    # Need non-generator versions of _call_llm and _process_model_result
    @classmethod
    async def _call_llm_single(
        cls,
        model_client: ChatCompletionClient,
        system_messages: List[SystemMessage],
        model_context: ChatCompletionContext,
        tools: List[BaseTool[Any, Any]],
        handoff_tools: List[BaseTool[Any, Any]],
        agent_name: str,
        cancellation_token: CancellationToken,
        output_content_type: type[BaseModel] | None,
    ) -> CreateResult:
        """
        Perform a single model inference (non-streaming).
        """
        all_messages = await model_context.get_messages()
        llm_messages = cls._get_compatible_context(model_client=model_client, messages=system_messages + all_messages)
        all_tools = tools + handoff_tools

        model_result = await model_client.create(
            llm_messages,
            tools=all_tools,
            cancellation_token=cancellation_token,
            json_output=output_content_type,
        )
        return model_result

    @classmethod
    async def _process_model_result_single(
        cls,
        model_result: CreateResult,
        cancellation_token: CancellationToken,
        agent_name: str,
        system_messages: List[SystemMessage],
        model_context: ChatCompletionContext,
        tools: List[BaseTool[Any, Any]],
        handoff_tools: List[BaseTool[Any, Any]],
        handoffs: Dict[str, HandoffBase],
        model_client: ChatCompletionClient,
        reflect_on_tool_use: bool,
        tool_call_summary_format: str,
        output_content_type: type[BaseModel] | None,
        format_string: str | None = None,
    ) -> Union[TextMessage, StructuredMessage, ToolCallSummaryMessage, HandoffMessage, None]:
        """
        Handle final or partial responses from model_result (non-streaming).
        Returns the final message to be sent back.
        """

        # If direct text response (string)
        if isinstance(model_result.content, str):
            if output_content_type:
                content = output_content_type.model_validate_json(model_result.content)
                return StructuredMessage[output_content_type](  # type: ignore[valid-type]
                        content=content,
                        source=agent_name,
                        models_usage=model_result.usage,
                        format_string=format_string,
                    )
            else:
                return TextMessage(
                        content=model_result.content,
                        source=agent_name,
                        models_usage=model_result.usage,
                    )

        # Otherwise, we have function calls
        if not isinstance(model_result.content, list) or not all(
            isinstance(item, FunctionCall) for item in model_result.content
        ):
             # Handle cases where content is neither string nor list of FunctionCall (e.g. None or unexpected type)
             event_logger.warning(f"Unexpected model result content type: {type(model_result.content)}. Content: {model_result.content}")
             # Attempt to return a simple text message if possible, otherwise None
             try:
                 return TextMessage(content=str(model_result.content) if model_result.content is not None else "", source=agent_name, models_usage=model_result.usage)
             except Exception:
                 return None


        # Log ToolCallRequestEvent
        tool_call_req_event = ToolCallRequestEvent(
            content=model_result.content,
            source=agent_name,
            models_usage=model_result.usage,
        )
        event_logger.debug(tool_call_req_event)

        # Execute tool calls
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

        # Log ToolCallExecutionEvent
        tool_call_exec_event = ToolCallExecutionEvent(
            content=exec_results,
            source=agent_name,
        )
        event_logger.debug(tool_call_exec_event)
        await model_context.add_message(FunctionExecutionResultMessage(content=exec_results))

        # Check for handoff
        handoff_message = cls._check_and_handle_handoff_single( # Use non-Response version
            model_result=model_result,
            executed_calls_and_results=executed_calls_and_results,
            handoffs=handoffs,
            agent_name=agent_name,
        )
        if handoff_message:
            return handoff_message # Return the HandoffMessage directly

        # Reflect or summarize tool results
        if reflect_on_tool_use:
            final_message = await cls._reflect_on_tool_use_flow_single( # Use non-generator version
                system_messages=system_messages,
                model_client=model_client,
                model_context=model_context,
                agent_name=agent_name,
                output_content_type=output_content_type,
            )
            return final_message
        else:
            summary_message = cls._summarize_tool_use_single( # Use non-Response version
                executed_calls_and_results=executed_calls_and_results,
                handoffs=handoffs,
                tool_call_summary_format=tool_call_summary_format,
                agent_name=agent_name,
            )
            return summary_message


    # --- Copy/Adapt other static/class methods ---
    @staticmethod
    async def _add_messages_to_context(
        model_context: ChatCompletionContext,
        messages: Sequence[BaseChatMessage],
    ) -> None:
        """Add incoming messages to the model context."""
        # This is identical to AssistantAgent's version
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
    ) -> List[MemoryQueryEvent]: # Return type kept for potential logging
        """Update model context with memory and return loggable events."""
        # This is identical to AssistantAgent's version
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

    @staticmethod
    def _check_and_handle_handoff_single( # Renamed, returns HandoffMessage | None
        model_result: CreateResult,
        executed_calls_and_results: List[Tuple[FunctionCall, FunctionExecutionResult]],
        handoffs: Dict[str, HandoffBase],
        agent_name: str,
    ) -> Optional[HandoffMessage]:
        """Detect handoff calls and generate the HandoffMessage if needed."""
        # Adapted from AssistantAgent's version to return HandoffMessage directly
        handoff_reqs = [
            call for call in model_result.content if isinstance(call, FunctionCall) and call.name in handoffs
        ]
        if len(handoff_reqs) > 0:
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

            tool_calls: List[FunctionCall] = []
            tool_call_results: List[FunctionExecutionResult] = []
            selected_handoff_message = selected_handoff.message
            for exec_call, exec_result in executed_calls_and_results:
                if exec_call.name not in handoffs:
                    tool_calls.append(exec_call)
                    tool_call_results.append(exec_result)
                elif exec_call.name == selected_handoff.name:
                    selected_handoff_message = exec_result.content

            handoff_context: List[LLMMessage] = []
            if len(tool_calls) > 0:
                handoff_context.append(
                    AssistantMessage(
                        content=tool_calls,
                        source=agent_name,
                        thought=getattr(model_result, "thought", None),
                    )
                )
                handoff_context.append(FunctionExecutionResultMessage(content=tool_call_results))
            elif model_result.thought:
                 handoff_context.append(
                    AssistantMessage(
                        content=model_result.thought, # Use thought as content if no tool calls
                        source=agent_name,
                    )
                )

            return HandoffMessage(
                    content=selected_handoff_message,
                    target=selected_handoff.target,
                    source=agent_name,
                    context=handoff_context,
                )
        return None

    @classmethod
    async def _reflect_on_tool_use_flow_single( # Renamed, returns final message | None
        cls,
        system_messages: List[SystemMessage],
        model_client: ChatCompletionClient,
        model_context: ChatCompletionContext,
        agent_name: str,
        output_content_type: type[BaseModel] | None,
    ) -> Union[TextMessage, StructuredMessage, None]:
        """Perform reflection inference and return the final message."""
        # Adapted from AssistantAgent's version
        all_messages = system_messages + await model_context.get_messages()
        llm_messages = cls._get_compatible_context(model_client=model_client, messages=all_messages)

        reflection_result = await model_client.create(llm_messages, json_output=output_content_type)

        if not reflection_result or not isinstance(reflection_result.content, str):
             event_logger.warning("Reflection on tool use produced no valid text response.")
             return None # Or raise error? Returning None seems safer for handler.

        # Log thought if present
        if reflection_result.thought:
            thought_event = ThoughtEvent(content=reflection_result.thought, source=agent_name)
            event_logger.debug(thought_event)


        # Add to context
        await model_context.add_message(
            AssistantMessage(
                content=reflection_result.content,
                source=agent_name,
                thought=getattr(reflection_result, "thought", None),
            )
        )

        if output_content_type:
            content = output_content_type.model_validate_json(reflection_result.content)
            return StructuredMessage[output_content_type](  # type: ignore[valid-type]
                    content=content,
                    source=agent_name,
                    models_usage=reflection_result.usage,
                )
        else:
            return TextMessage(
                    content=reflection_result.content,
                    source=agent_name,
                    models_usage=reflection_result.usage,
                )

    @staticmethod
    def _summarize_tool_use_single( # Renamed, returns ToolCallSummaryMessage
        executed_calls_and_results: List[Tuple[FunctionCall, FunctionExecutionResult]],
        handoffs: Dict[str, HandoffBase],
        tool_call_summary_format: str,
        agent_name: str,
    ) -> ToolCallSummaryMessage:
        """Create a summary message of all non-handoff tool calls."""
        # Adapted from AssistantAgent's version
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
        tool_call_summary = "\\n".join(tool_call_summaries)
        return ToolCallSummaryMessage(
                content=tool_call_summary,
                source=agent_name,
            )

    @staticmethod
    async def _execute_tool_call(
        tool_call: FunctionCall,
        tools: List[BaseTool[Any, Any]],
        handoff_tools: List[BaseTool[Any, Any]],
        agent_name: str,
        cancellation_token: CancellationToken,
    ) -> Tuple[FunctionCall, FunctionExecutionResult]:
        """Execute a single tool call and return the result."""
        # This is identical to AssistantAgent's version
        try:
            all_tools = tools + handoff_tools
            if not all_tools:
                raise ValueError("No tools are available.")
            tool = next((t for t in all_tools if t.name == tool_call.name), None)
            if tool is None:
                raise ValueError(f"The tool '{tool_call.name}' is not available.")
            arguments: Dict[str, Any] = json.loads(tool_call.arguments) if tool_call.arguments else {}
            result = await tool.run_json(arguments, cancellation_token)
            result_as_str = tool.return_value_as_string(result)
            return (
                tool_call,
                FunctionExecutionResult(
                    content=result_as_str,
                    call_id=tool_call.id,
                    is_error=False,
                    name=tool_call.name,
                ),
            )
        except Exception as e:
            return (
                tool_call,
                FunctionExecutionResult(
                    content=f"Error: {e}",
                    call_id=tool_call.id,
                    is_error=True,
                    name=tool_call.name,
                ),
            )

    @staticmethod
    def _get_compatible_context(model_client: ChatCompletionClient, messages: List[LLMMessage]) -> Sequence[LLMMessage]:
        """Ensure messages are compatible with the client (e.g., remove images)."""
        # This is identical to AssistantAgent's version
        if model_client.model_info["vision"]:
            return messages
        else:
            return remove_images(messages)

    # --- Component Methods (Copied/Adapted from AssistantAgent) ---

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        """Types of messages this agent's handlers might produce."""
        # This should reflect the return types of the @rpc handlers
        message_types: List[type[BaseChatMessage]] = []
        if self._handoffs:
            message_types.append(HandoffMessage)
        if self._tools:
            message_types.append(ToolCallSummaryMessage)
        if self._output_content_type:
            # Need to handle the generic type properly for inspection
            structured_type = StructuredMessage[self._output_content_type] # type: ignore[name-defined]
            message_types.append(structured_type)
        # Always include TextMessage as a possible fallback/reflection result
        message_types.append(TextMessage)
        # Remove duplicates and return tuple
        return tuple(set(message_types))


    @property
    def model_context(self) -> ChatCompletionContext:
        """The model context in use by the agent."""
        # Identical to AssistantAgent
        return self._model_context

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """Reset the agent to its initialization state."""
        # Identical to AssistantAgent
        await self._model_context.clear()

    async def save_state(self) -> Mapping[str, Any]:
        """Save the current state of the agent."""
        # Identical to AssistantAgent
        model_context_state = await self._model_context.save_state()
        return AssistantAgentState(llm_context=model_context_state).model_dump()

    async def load_state(self, state: Mapping[str, Any]) -> None:
        """Load the state of the agent."""
        # Identical to AssistantAgent
        assistant_agent_state = AssistantAgentState.model_validate(state)
        await self._model_context.load_state(assistant_agent_state.llm_context)

    def _to_config(self) -> RoutedAssistantAgentConfig:
        """Convert the agent to a declarative config."""
        # Adapted from AssistantAgent (removed model_client_stream)
        return RoutedAssistantAgentConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            tools=[tool.dump_component() for tool in self._tools] if self._tools else None, # Handle empty list
            handoffs=list(self._handoffs.values()) if self._handoffs else None,
            model_context=self._model_context.dump_component(),
            memory=[memory.dump_component() for memory in self._memory] if self._memory else None,
            description=self.description,
            system_message=self._system_messages[0].content
            if self._system_messages and isinstance(self._system_messages[0].content, str)
            else None,
            reflect_on_tool_use=self._reflect_on_tool_use,
            tool_call_summary_format=self._tool_call_summary_format,
            structured_message_factory=self._structured_message_factory.dump_component()
            if self._structured_message_factory
            else None,
            metadata=self._metadata,
        )

    @classmethod
    def _from_config(cls, config: RoutedAssistantAgentConfig) -> Self:
        """Create an agent from a declarative config."""
        # Adapted from AssistantAgent (removed model_client_stream)
        if config.structured_message_factory:
            structured_message_factory = StructuredMessageFactory.load_component(config.structured_message_factory)
            format_string = structured_message_factory.format_string
            output_content_type = structured_message_factory.ContentModel
        else:
            format_string = None
            output_content_type = None

        # Instantiate the class using the config values
        # Note: The AgentRuntime handles the context for super().__init__
        instance = cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            tools=[BaseTool.load_component(tool) for tool in config.tools] if config.tools else None,
            handoffs=config.handoffs,
            model_context=ChatCompletionContext.load_component(config.model_context) if config.model_context else None,
            memory=[Memory.load_component(memory) for memory in config.memory] if config.memory else None,
            description=config.description,
            system_message=config.system_message,
            reflect_on_tool_use=config.reflect_on_tool_use,
            tool_call_summary_format=config.tool_call_summary_format,
            output_content_type=output_content_type,
            output_content_type_format=format_string,
            metadata=config.metadata,
        )
        return instance # Return the created instance


    # --- Override on_unhandled_message from RoutedAgent if needed ---
    # async def on_unhandled_message(self, message: Any, ctx: MessageContext) -> None:
    #     """Called when a message is received that does not have a matching message handler."""
    #     # Default implementation logs an info message. Can be customized.
    #     await super().on_unhandled_message(message, ctx)

# Ensure the rest of the file has correct indentation if applicable

