import os
import asyncio
import random
import json
import uuid
import websockets
import base64
from typing import Dict, List, Callable, Awaitable, Optional, Any

from autogen_core import (
    AgentId, DefaultTopicId, MessageContext, RoutedAgent, ClosureAgent, 
    ClosureContext, message_handler, TypeSubscription
)
from autogen_core.models import (
    AssistantMessage as LLMAssistantMessage, 
    UserMessage as LLMUserMessage,
    SystemMessage, ChatCompletionClient
)
from autogen_ext.tools.mcp import McpWorkbench

from _types import (
    MessageChunk, UserMessage, AssistantMessage, GroupChatMessage, CallRequest,
    UIAgentConfig
)
from _utils import is_call_id

### THIS COULD BE ANY THRID-PARTY AGENT/TEAM ###
class DomainAgent(RoutedAgent):
    """A domain agent with specific knowledge loaded from a file."""
    
    def __init__(
        self,
        description: str,
        system_message: str,
        model_client: ChatCompletionClient,
        ui_config: UIAgentConfig,
        knowledge_file: str = "prompts/domain_knowledge.txt"
    ) -> None:
        super().__init__(description=description)
        
        # Load domain knowledge
        current_dir = os.path.dirname(os.path.abspath(__file__))
        knowledge_file = os.path.join(current_dir, knowledge_file)
        domain_knowledge = ""
        try:
            with open(knowledge_file, 'r', encoding='utf-8') as file:
                domain_knowledge = file.read().strip()
        except FileNotFoundError:
            print(f"Warning: Knowledge file {knowledge_file} not found.")
        
        # Combine system message with domain knowledge
        full_system_message = f"{system_message}\n\nDomain Knowledge:\n{domain_knowledge}"
        full_system_message = f"\n\nDomain Knowledge:\n{domain_knowledge}"
        print(f"--- Domain knowledge loaded: {domain_knowledge[:50]}...")
        self._system_message = SystemMessage(content=full_system_message)
        
        self._model_client = model_client
        self._chat_history: List[LLMUserMessage | LLMAssistantMessage] = []
        self._ui_config = ui_config
    
    @message_handler
    async def handle_message(self, message: UserMessage, ctx: MessageContext) -> AssistantMessage:
        """Handle incoming user messages and generate a response."""
        print(f"\n--- DomainAgent received: {message.content} from {message.source}")
        
        # Add to chat history
        self._chat_history.append(LLMUserMessage(content=message.content, source=message.source))
        
        # Generate response
        messages = [self._system_message] + self._chat_history
        completion = await self._model_client.create(messages, cancellation_token=ctx.cancellation_token)
        
        # Extract content
        assert isinstance(completion.content, str)
        response_content = completion.content
        # Add to chat history
        self._chat_history.append(LLMAssistantMessage(content=response_content, source=self.id.type))
        
        # Return response
        print(f"--- DomainAgent responding with: {response_content[:50]}...")
        return AssistantMessage(content=response_content, source=self.id.type)

class FormatProxyAgent(RoutedAgent):
    """Format Proxy Agent that handles WebSocket connections and audio transcription."""
    
    def __init__(
        self,
        description: str,
        workbench: McpWorkbench,
        ui_config: UIAgentConfig
    ) -> None:
        super().__init__(description=description)
        self.workbench = workbench
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self._ui_config = ui_config
    
    @message_handler
    async def handle_call_request(self, message: CallRequest, ctx: MessageContext) -> AssistantMessage:
        """Handle call requests from the orchestrator."""
        print(f"\n--- FormatProxyAgent handling call request: {message.call_id}")
        
        try:
            # Send to UI that we're initiating a call
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Initiating call to {message.to_number}...",
                ui_config=self._ui_config
            )
            
            # TODO: Implement actual MCP tool call
            # Mock WebSocket URL in this example - in production this would come from a real backend
            websocket_url = f"ws://localhost:8080/calls/{message.call_id}"
            print(f"--- Would connect to WebSocket URL: {websocket_url}")
            
            # In a real implementation, we would connect to the WebSocket and keep receiving messages chunks and processing them to the domain agent
            
            # Since we're just simulating, create a mock message
            await asyncio.sleep(2)  # Simulate connection delay
            
            # Publish a mock transcript
            mock_transcript = "Hello, if you are using English, please press 1. If you are using Spanish, please press 2."
            
            # Publish to domain_input topic with call_id as source
            await self.publish_message(
                UserMessage(content=mock_transcript, source=message.call_id),
                DefaultTopicId(type="domain_input", source=message.call_id)
            )
            
            # Send to UI that call is connected
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Call connected! Received: '{mock_transcript}'",
                ui_config=self._ui_config
            )

            # Return status as AssistantMessage instead of dict
            status_content = json.dumps({"status": "success", "call_id": message.call_id})
            return AssistantMessage(content=status_content, source=self.id.type)
            
        except Exception as e:
            print(f"Error in call request handling: {e}")
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Error initiating call: {str(e)}",
                ui_config=self._ui_config
            )
            # Return error info as AssistantMessage
            error_content = json.dumps({"status": "error", "message": str(e)})
            return AssistantMessage(content=error_content, source=self.id.type)
    
    @message_handler
    async def handle_domain_response(self, message: AssistantMessage, ctx: MessageContext) -> AssistantMessage:
        """Handle responses from domain agents via domain_output topic."""
        
        if not ctx.topic_id or ctx.topic_id.type != "domain_output":
            # Return empty response if not handled
            return AssistantMessage(content="", source=self.id.type)
        
        call_id = ctx.topic_id.source
        if not is_call_id(call_id):
            # Return empty response if not a call ID
            return AssistantMessage(content="", source=self.id.type)
        
        # Extract message content, regardless of message type
        message_content = ""
        if hasattr(message, "content"):
            message_content = message.content
        else:
            # Try to convert message to string if it's not a recognized format
            try:
                message_content = str(message)
            except:
                message_content = "Received response in unknown format"
            
        print(f"--- FormatProxyAgent received response for call {call_id}: {message_content[:50]}...")
        
        # TODO: Implement actual WebSocket send
        # In a real implementation we would send this to the WebSocket
        # if call_id in self.connections:
        #     await self.connections[call_id].send(json.dumps({
        #         "type": "text_response", 
        #         "data": {"text": message_content}
        #     }))
        
        # Since we're just simulating, in real implementation UI would not receive this intermidiate message
        await publish_message_to_ui(
            runtime=self,
            source=f"{self.id.type} (Call {call_id[:8]})",
            user_message=f"Sending response to client: '{message_content}'",
            ui_config=self._ui_config
        )
        
        # TODO: Add some checking WebSocket connection status logic to handle the termination
        # Simulate call ending after response
        await asyncio.sleep(3)
        await publish_message_to_ui(
            runtime=self,
            source=self.id.type,
            user_message=f"Call {call_id[:8]} ended",
            ui_config=self._ui_config
        )

        # Return successful response as AssistantMessage
        status_content = json.dumps({"status": "success", "call_id": call_id})
        return AssistantMessage(content=status_content, source=self.id.type)

class GroupChatManager(RoutedAgent):
    """Orchestrator that routes requests to either FPA or domain agent."""
    
    def __init__(
        self,
        description: str,
        model_client: ChatCompletionClient,
        ui_config: UIAgentConfig
    ) -> None:
        super().__init__(description=description)
        self.model_client = model_client
        self._ui_config = ui_config
    
    @message_handler
    async def handle_user_request(self, message: UserMessage, ctx: MessageContext) -> Optional[str]:
        """Handle user requests and route appropriately."""
        print(f"\n--- GroupChatManager received request: {message.content}")
        
        # Send acknowledgment to UI
        await publish_message_to_ui(
            runtime=self,
            source=self.id.type,
            user_message=f"Processing request: '{message.content}'",
            ui_config=self._ui_config
        )
        
        # Determine task type (simplified - in production use LLM)
        task_type = "call_request" if "call" in message.content.lower() else "direct_task"
        
        if task_type == "call_request":
            # SCENARIO 1: Phone call request
            # Extract phone number and context (simplified)
            phone_number = "+1234567890"  # Mock phone number
            context = message.content
            
            # Generate unique call ID
            call_id = str(uuid.uuid4())
            
            # Inform UI
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Initiating call scenario with ID {call_id[:8]}",
                ui_config=self._ui_config
            )
            
            # Route through FormatProxyAgent
            await self.send_message(
                CallRequest(call_id=call_id, to_number=phone_number, context=context),
                AgentId("format_proxy", "default")
            )
            
            return f"Initiating call with ID {call_id[:8]}"
            
        else:
            # SCENARIO 2: Direct task
            # Inform UI
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message="Processing direct task",
                ui_config=self._ui_config
            )
            
            # Directly message domain agent with standard ID
            response = await self.send_message(
                UserMessage(content=message.content, source="user"),
                AgentId("domain_agent", "default")
            )
            
            # Send response to UI
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Response from domain agent: '{response.content}'",
                ui_config=self._ui_config
            )
            
            return f"Direct task response: {response.content}"


class UIAgent(RoutedAgent):
    """Handles UI-related tasks and message processing."""

    def __init__(self, on_message_chunk_func: Callable[[MessageChunk], Awaitable[None]]) -> None:
        super().__init__("UI Agent")
        self._on_message_chunk_func = on_message_chunk_func

    @message_handler
    async def handle_message_chunk(self, message: MessageChunk, ctx: MessageContext) -> None:
        await self._on_message_chunk_func(message)

class BidirectionalAdapter(RoutedAgent):
    """A bidirectional adapter that connects Format Proxy Agent with Domain Agent."""
    
    def __init__(self, description: str = "Bidirectional Adapter") -> None:
        super().__init__(description=description)
    
    @message_handler
    async def handle_domain_input(self, message: UserMessage, ctx: MessageContext) -> None:
        """Handle messages from domain_input topic and forward to domain agent."""
        # Only process messages with the right topic type
        if not ctx.topic_id or ctx.topic_id.type != "domain_input":
            return
        
        # Get the call_id from topic source
        call_id = ctx.topic_id.source
        if is_call_id(call_id):
            print(f"--- BidirectionalAdapter forwarding message to domain agent with key {call_id}")
            
            # Forward message to domain agent and get response
            response = await self.send_message(message, AgentId("domain_agent", call_id))
            
            # Publish response to domain_output topic
            if response:
                print(f"--- BidirectionalAdapter publishing response to domain_output for {call_id}")
                await self.publish_message(
                    response, 
                    DefaultTopicId(type="domain_output", source=call_id)
                )


# Helper Functions
async def publish_message_to_ui(
    runtime: RoutedAgent,
    source: str,
    user_message: str,
    ui_config: UIAgentConfig,
) -> None:
    """Publish a message to the UI."""
    message_id = str(uuid.uuid4())
    
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