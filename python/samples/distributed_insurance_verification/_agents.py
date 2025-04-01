import asyncio
import json
import random
import traceback
from typing import Awaitable, Callable, Dict, List
from uuid import uuid4

from _types import GroupChatMessage, MessageChunk, RequestToSpeak, UIAgentConfig
from autogen_core import DefaultTopicId, MessageContext, RoutedAgent, message_handler
from autogen_core.models import (
    AssistantMessage, 
    ChatCompletionClient, 
    LLMMessage, 
    SystemMessage, 
    UserMessage,
    FunctionExecutionResult, 
    FunctionExecutionResultMessage
)
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.tools.mcp import SseServerParams
from autogen_ext.tools.mcp._session import create_mcp_server_session
from rich.console import Console
from rich.markdown import Markdown


TEAM_GOAL = """
Goal:
Accurately verify insurance eligibility and, if confirmed, update the patient's verified information into the EMR/EHR system.

Process:
Insurance eligibility verification should follow this structured two-phase workflow:

Phase 1 (Initial Verification via Portals):
1.1: Log into the provided insurance portal(s) using given credentials and analyze screenshots or portal data to determine preliminary eligibility.
1.2: If the patient is clearly eligible (without IPA involvement), update the EMR/EHR system accordingly.
1.3: If eligibility is unclear or IPA involvement exists, proceed to Phase 2.

Phase 2 (Verification via Phone Call):
2.1: If IPA involvement is detected, you should contact IPA directly for verification. Otherwise, contact the insurance provider by phone to verify eligibility.
2.2: If the patient is eligible, update the EMR/EHR system with the verified information.
2.3: If the patient is not eligible, inform the user clearly that the patient is not eligible for the requested service.

Note: Always evaluate what information you currently have, identify what additional steps and tools are necessary, or confirm if the verification task is already complete.
"""


class BaseGroupChatAgent(RoutedAgent):
    """A group chat participant using an LLM."""

    def __init__(
        self,
        description: str,
        group_chat_topic_type: str,
        model_client: ChatCompletionClient,
        system_message: str,
        ui_config: UIAgentConfig,
    ) -> None:
        super().__init__(description=description)
        self._group_chat_topic_type = group_chat_topic_type
        self._model_client = model_client
        self._system_message = SystemMessage(content=system_message)
        self._chat_history: List[LLMMessage] = []
        self._ui_config = ui_config
        self.console = Console()

    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        self._chat_history.extend(
            [
                UserMessage(content=f"Transferred to {message.body.source}", source="system"),
                message.body,
            ]
        )

    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        self._chat_history.append(
            UserMessage(content=f"Transferred to {self.id.type}, adopt the persona immediately.", source="system")
        )
        completion = await self._model_client.create([self._system_message] + self._chat_history)
        assert isinstance(completion.content, str)
        self._chat_history.append(AssistantMessage(content=completion.content, source=self.id.type))

        console_message = f"\n{'-'*80}\n**{self.id.type}**: {completion.content}"
        self.console.print(Markdown(console_message))

        await publish_message_to_ui_and_backend(
            runtime=self,
            source=self.id.type,
            user_message=completion.content,
            ui_config=self._ui_config,
            group_chat_topic_type=self._group_chat_topic_type,
        )


class McpSseGroupChatAgent(BaseGroupChatAgent):
    """A group chat participant using an LLM with MCP SSE tools."""

    def __init__(
        self,
        description: str,
        group_chat_topic_type: str,
        model_client: ChatCompletionClient,
        system_message: str,
        ui_config: UIAgentConfig,
        sse_url: str,
        sse_headers: Dict[str, str] = None,
        sse_timeout: float = 120.0,
    ) -> None:
        super().__init__(
            description=description,
            group_chat_topic_type=group_chat_topic_type,
            model_client=model_client,
            system_message=system_message,
            ui_config=ui_config,
        )
        self._sse_url = sse_url
        self._sse_headers = sse_headers or {}
        self._sse_timeout = sse_timeout
        self._mcp_session = None
        self._mcp_tools = []
        self._mcp_initialized = False

    async def _lazy_init(self, cancellation_token):
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
                        self._mcp_tools.append(tool)
                    except Exception as e:
                        self.console.print(f"Failed to process tool {tool.name}: {str(e)}")
                
                self.console.print(f"Initialized MCP session with {len(self._mcp_tools)} tools.")
                self._mcp_initialized = True
        except Exception as e:
            self.console.print(f"Failed to initialize MCP session: {str(e)}")
            raise RuntimeError(f"Failed to initialize MCP session: {str(e)}")

    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        # Initialize MCP session if not already initialized
        await self._lazy_init(ctx.cancellation_token)
        
        # Add system prompt about being transferred
        self._chat_history.append(
            UserMessage(content=f"Transferred to {self.id.type}, adopt the persona immediately.", source="system")
        )
        
        # Get tool schemas to pass to the model
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
        
        # Call the model
        console_message = f"\n{'-'*80}\n**{self.id.type}**:"
        self.console.print(Markdown(console_message))
        
        # Process the conversation turn by turn
        current_messages = [self._system_message] + self._chat_history
        final_response = None
        
        while True:
            response = await self._model_client.create(
                messages=current_messages,
                tools=tool_schemas,
                cancellation_token=ctx.cancellation_token,
            )
            
            if isinstance(response.content, str):
                # Final text response
                final_response = response.content
                current_messages.append(AssistantMessage(content=final_response, source=self.id.type))
                self._chat_history = current_messages  # Update full history
                break
                
            if isinstance(response.content, list) and len(response.content) > 0:
                # Tool calls - execute one by one
                tool_calls_message = AssistantMessage(content=response.content, source=self.id.type)
                current_messages.append(tool_calls_message)
                
                # Get all tool calls
                tool_calls = response.content
                for tool_call in tool_calls:
                    # Log the tool call
                    self.console.print(f"Tool call: {tool_call.name} with args: {tool_call.arguments}")
                    
                    # Execute the tool
                    result = await self._execute_tool(tool_call.name, json.loads(tool_call.arguments), ctx.cancellation_token)
                    
                    # Create execution result
                    execution_result = FunctionExecutionResult(
                        content=result if isinstance(result, str) else str(result),
                        call_id=tool_call.id,
                        name=tool_call.name,
                        is_error=False
                    )
                    
                    # Log the result
                    self.console.print(f"Tool result: {execution_result.content}")
                    
                    # Add to current messages
                    current_messages.append(FunctionExecutionResultMessage(content=[execution_result]))
            else:
                # No tool calls and no text response - something went wrong
                final_response = "The model did not provide a valid response."
                current_messages.append(AssistantMessage(content=final_response, source=self.id.type))
                self._chat_history = current_messages  # Update full history
                break
        
        # At this point we have a final response
        self.console.print(Markdown(final_response))
        
        # Publish the final response
        await publish_message_to_ui_and_backend(
            runtime=self,
            source=self.id.type,
            user_message=final_response,
            ui_config=self._ui_config,
            group_chat_topic_type=self._group_chat_topic_type,
        )

    async def _execute_tool(self, tool_name, arguments, cancellation_token):
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
                self.console.print(f"Executing tool: {tool_name} with arguments: {arguments}")
                
                try:
                    # Pass arguments directly as a dictionary
                    result = await session.call_tool(tool_name, arguments)
                    
                    if result.isError:
                        error_msg = f"Tool execution failed: {result.content}"
                        self.console.print(error_msg)
                        return error_msg
                    
                    return result.content
                except asyncio.CancelledError:
                    return "Tool execution was cancelled"
                except Exception as e:
                    tb = traceback.format_exc()
                    self.console.print(f"Detailed error in tool execution: {str(e)}\n{tb}")
                    return f"Error in tool execution: {str(e)}"
        except Exception as e:
            tb = traceback.format_exc()
            self.console.print(f"Detailed error creating MCP session: {str(e)}\n{tb}")
            return f"Error executing tool {tool_name}: {str(e)}"


class GroupChatManager(RoutedAgent):
    def __init__(
        self,
        model_client: ChatCompletionClient,
        participant_topic_types: List[str],
        participant_descriptions: List[str],
        ui_config: UIAgentConfig,
        max_rounds: int = 10,
        team_goal: str = TEAM_GOAL,
    ) -> None:
        super().__init__("Insurance verification team manager")
        self._model_client = model_client
        self._participant_topic_types = participant_topic_types
        self._participant_descriptions = participant_descriptions
        self._chat_history: List[UserMessage] = []
        self._max_rounds = max_rounds
        self._previous_participant_topic_type: str | None = None
        self._ui_config = ui_config
        self._team_goal = team_goal
        self._round = 0
        self.console = Console()

    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        assert isinstance(message.body, UserMessage)
        self._chat_history.append(message.body)

        # Check for termination
        if message.body.content and "TERMINATE" in message.body.content:
            message_text = "Task has been completed. Thank you for using the insurance verification team."
            await publish_message_to_ui(
                runtime=self, 
                source=self.id.type, 
                user_message=message_text, 
                ui_config=self._ui_config
            )
            self.console.print(Markdown(f"\n{'-'*80}\n**{self.id.type}**: {message_text}"))
            return
            
        # Increment round counter
        self._round += 1
        if self._round >= self._max_rounds:
            message_text = f"Maximum rounds ({self._max_rounds}) reached. Terminating conversation."
            await publish_message_to_ui(
                runtime=self, 
                source=self.id.type, 
                user_message=message_text, 
                ui_config=self._ui_config
            )
            self.console.print(Markdown(f"\n{'-'*80}\n**{self.id.type}**: {message_text}"))
            return

        # Format message history
        messages: List[str] = []
        for msg in self._chat_history:
            if isinstance(msg.content, str):
                messages.append(f"{msg.source}: {msg.content}")
            elif isinstance(msg.content, list):
                messages.append(f"{msg.source}: {', '.join(str(item) for item in msg.content)}")
        history = "\n".join(messages)
        
        # Format roles
        roles = "\n".join(
            [
                f"{topic_type}: {description}".strip()
                for topic_type, description in zip(
                    self._participant_topic_types, self._participant_descriptions, strict=True
                )
                if topic_type != self._previous_participant_topic_type
            ]
        )
        
        # Create selector prompt
        selector_prompt = f"""
        {self._team_goal}
        
        You are in a role play game. The following roles are available:
        {roles}.
        
        Read the following conversation. Then select the next role from {[topic_type for topic_type in self._participant_topic_types if topic_type != self._previous_participant_topic_type]} to play. Only return the role.

        {history}

        Read the above conversation. Then select the next role from {[topic_type for topic_type in self._participant_topic_types if topic_type != self._previous_participant_topic_type]} to play. Only return the role.
        """
        
        system_message = SystemMessage(content=selector_prompt)
        completion = await self._model_client.create([system_message], cancellation_token=ctx.cancellation_token)
        assert isinstance(completion.content, str)
        
        # Determine the next speaker
        selected_topic_type: str
        for topic_type in self._participant_topic_types:
            if topic_type.lower() in completion.content.lower():
                selected_topic_type = topic_type
                self._previous_participant_topic_type = selected_topic_type
                self.console.print(
                    Markdown(f"\n{'-'*80}\n**{self.id.type}**: Asking `{selected_topic_type}` to speak")
                )
                await self.publish_message(RequestToSpeak(), DefaultTopicId(type=selected_topic_type))
                return
        
        # If no match found, use the first agent
        selected_topic_type = self._participant_topic_types[0]
        self._previous_participant_topic_type = selected_topic_type
        self.console.print(
            Markdown(f"\n{'-'*80}\n**{self.id.type}**: Asking `{selected_topic_type}` to speak (default)")
        )
        await self.publish_message(RequestToSpeak(), DefaultTopicId(type=selected_topic_type))


class UIAgent(RoutedAgent):
    """Handles UI-related tasks and message processing for the distributed system."""

    def __init__(self, on_message_chunk_func: Callable[[MessageChunk], Awaitable[None]]) -> None:
        super().__init__("UI Agent")
        self._on_message_chunk_func = on_message_chunk_func

    @message_handler
    async def handle_message_chunk(self, message: MessageChunk, ctx: MessageContext) -> None:
        await self._on_message_chunk_func(message)


async def publish_message_to_ui(
    runtime: RoutedAgent | GrpcWorkerAgentRuntime,
    source: str,
    user_message: str,
    ui_config: UIAgentConfig,
) -> None:
    message_id = str(uuid4())
    
    # Stream the message to UI
    message_chunks = (
        MessageChunk(message_id=message_id, text=token + " ", author=source, finished=False)
        for token in user_message.split()
    )
    for chunk in message_chunks:
        await runtime.publish_message(
            chunk,
            DefaultTopicId(type=ui_config.topic_type),
        )
        await asyncio.sleep(random.uniform(ui_config.min_delay, ui_config.max_delay))

    await runtime.publish_message(
        MessageChunk(message_id=message_id, text=" ", author=source, finished=True),
        DefaultTopicId(type=ui_config.topic_type),
    )


async def publish_message_to_ui_and_backend(
    runtime: RoutedAgent | GrpcWorkerAgentRuntime,
    source: str,
    user_message: str,
    ui_config: UIAgentConfig,
    group_chat_topic_type: str,
) -> None:
    # Publish messages for ui
    await publish_message_to_ui(
        runtime=runtime,
        source=source,
        user_message=user_message,
        ui_config=ui_config,
    )

    # Publish message to backend
    await runtime.publish_message(
        GroupChatMessage(body=UserMessage(content=user_message, source=source)),
        topic_id=DefaultTopicId(type=group_chat_topic_type),
    )