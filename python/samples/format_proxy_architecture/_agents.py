import os
import re
import asyncio
import random
import json
import uuid
import websockets
import base64
from typing import Dict, List, Callable, Awaitable, Optional, Any

from autogen_core import (
    AgentId, DefaultTopicId, MessageContext, RoutedAgent, 
    message_handler, CancellationToken
)
from autogen_core.models import (
    AssistantMessage as LLMAssistantMessage, 
    UserMessage as LLMUserMessage,
    SystemMessage, ChatCompletionClient
)
from autogen_ext.tools.mcp import McpWorkbench

from _types import (
    MessageChunk, UserMessage, AssistantMessage, CallRequest,
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
        self.running_calls: Dict[str, bool] = {}
        self._ui_config = ui_config
        self.call_prompts: Dict[str, Dict[str, str]] = {}
    
    @message_handler
    async def handle_call_request(self, message: CallRequest, ctx: MessageContext) -> AssistantMessage:
        """Handle call requests from the orchestrator."""
        print(f"\n--- FormatProxyAgent handling call request: {message.call_id}")
        # Load prompts for this call if specified
        if hasattr(message, 'instruction_prompt_id') and message.instruction_prompt_id or \
           hasattr(message, 'patient_info_prompt_id') and message.patient_info_prompt_id:
            await self._load_prompts_for_call(message.call_id, message)

        try:
            # Send to UI that we're initiating a call
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Initiating call to {message.to_number}...",
                ui_config=self._ui_config
            )
            
            # Use the MCP tool to make the call
            call_result = await self.workbench.call_tool(
                "make_call", 
                arguments={
                    "to_number": message.to_number,
                    "information": message.context
                },
                cancellation_token=ctx.cancellation_token
            )
            
            # Process the result properly
            if call_result.is_error:
                error_msg = "Call failed to initiate"
                await publish_message_to_ui(
                    runtime=self,
                    source=self.id.type,
                    user_message=f"Error: {error_msg}",
                    ui_config=self._ui_config
                )
                return AssistantMessage(content=json.dumps({"status": "error", "message": error_msg}), source=self.id.type)
            
            # Parse the result as JSON (assuming it's a JSON string)
            try:
                result_text = call_result.to_text()
                call_data = json.loads(result_text)
                
                # Extract call details
                call_sid = call_data.get("call_sid", "unknown")
                websocket_url = call_data.get("websocket_url", "")
                
                if not websocket_url:
                    error_msg = "No WebSocket URL returned from make_call"
                    await publish_message_to_ui(
                        runtime=self,
                        source=self.id.type,
                        user_message=f"Error: {error_msg}",
                        ui_config=self._ui_config
                    )
                    return AssistantMessage(content=json.dumps({"status": "error", "message": error_msg}), source=self.id.type)
                
            except json.JSONDecodeError:
                # If result is not JSON, use it as is
                error_msg = f"Invalid response from make_call: {result_text}"
                await publish_message_to_ui(
                    runtime=self,
                    source=self.id.type,
                    user_message=f"Error: {error_msg}",
                    ui_config=self._ui_config
                )
                return AssistantMessage(content=json.dumps({"status": "error", "message": error_msg}), source=self.id.type)
            
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Call initiated with SID: {call_sid}",
                ui_config=self._ui_config
            )
            
            # Connect to the WebSocket
            try:
                self.connections[message.call_id] = await websockets.connect(websocket_url)
                self.running_calls[message.call_id] = True
                
                # Start message processing for this call
                asyncio.create_task(self._process_websocket_messages(message.call_id))
                
                await publish_message_to_ui(
                    runtime=self,
                    source=self.id.type,
                    user_message=f"Connected to WebSocket for call {message.call_id[:8]}",
                    ui_config=self._ui_config
                )
                
            except Exception as e:
                await publish_message_to_ui(
                    runtime=self,
                    source=self.id.type,
                    user_message=f"WebSocket connection error: {str(e)}",
                    ui_config=self._ui_config
                )
                return AssistantMessage(
                    content=json.dumps({"status": "error", "message": f"WebSocket connection failed: {str(e)}"}),
                    source=self.id.type
                )
            
            # Return success response
            return AssistantMessage(
                content=json.dumps({
                    "status": "success", 
                    "call_id": message.call_id,
                    "call_sid": call_sid
                }),
                source=self.id.type
            )
            
        except Exception as e:
            error_message = f"Error in call request handling: {str(e)}"
            print(error_message)
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=error_message,
                ui_config=self._ui_config
            )
            return AssistantMessage(
                content=json.dumps({"status": "error", "message": error_message}),
                source=self.id.type
            )

    async def _process_websocket_messages(self, call_id: str) -> None:
        """Process WebSocket messages for a specific call."""
        if call_id not in self.connections or not self.connections[call_id]:
            print(f"No WebSocket connection for call {call_id}")
            return
            
        websocket = self.connections[call_id]
        
        try:
            while self.running_calls.get(call_id, False):
                # Wait for a message
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                except websockets.exceptions.ConnectionClosed:
                    print(f"WebSocket connection closed for call {call_id}")
                    self.running_calls[call_id] = False
                    break

                # Process based on message type
                msg_type = data.get('type')
                print(f"Received message for call {call_id}: {msg_type}")
                
                if msg_type == "speech_segment":
                    # Process complete speech segment
                    await self._handle_speech_segment(data, call_id)
                    
                elif msg_type == "call_started":
                    stream_sid = data.get('data', {}).get('stream_sid', 'unknown')
                    print(f"Call {call_id} started with stream SID: {stream_sid}")
                    await publish_message_to_ui(
                        runtime=self,
                        source=f"{self.id.type} (Call {call_id[:8]})",
                        user_message=f"Call started with stream SID: {stream_sid}",
                        ui_config=self._ui_config
                    )
                    
                elif msg_type == "call_status" and data.get('data', {}).get('status') == "terminating":
                    eligibility = data.get('data', {}).get('eligibility', 'unknown')
                    print(f"Call {call_id} terminating with eligibility: {eligibility}")
                    await publish_message_to_ui(
                        runtime=self,
                        source=f"{self.id.type} (Call {call_id[:8]})",
                        user_message=f"Call terminating with eligibility: {eligibility}",
                        ui_config=self._ui_config
                    )
                    self.running_calls[call_id] = False
                    
                elif msg_type == "call_ended":
                    status = data.get('data', {}).get('status', 'unknown')
                    print(f"Call {call_id} ended with status: {status}")
                    await publish_message_to_ui(
                        runtime=self,
                        source=f"{self.id.type} (Call {call_id[:8]})",
                        user_message=f"Call ended with status: {status}",
                        ui_config=self._ui_config
                    )
                    self.running_calls[call_id] = False
                    
        except Exception as e:
            print(f"Error processing WebSocket messages for call {call_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            self.running_calls[call_id] = False
        finally:
            # Clean up resources
            if call_id in self.connections and self.connections[call_id]:
                print(f"DEBUG: Closing WebSocket connection for call {call_id}")
                await self.connections[call_id].close()
                self.connections[call_id] = None

    async def _handle_speech_segment(self, data: dict, call_id: str) -> None:
        """Process a speech segment and directly communicate with domain agent."""
        try:
            # Extract audio data
            payload = data.get('data', {}).get('payload')
            if not payload:
                print(f"No audio payload in speech segment for call {call_id}")
                return
                
            # Use MCP tool to transcribe the audio
            transcribe_result = await self.workbench.call_tool(
                "transcribe_audio", 
                arguments={
                    "audio_data": payload,
                    "model": "whisper"
                },
                cancellation_token=CancellationToken()
            )
            
            if transcribe_result.is_error:
                print(f"Transcription error for call {call_id}")
                return
                
            # Parse the result
            try:
                result_text = transcribe_result.to_text()
                result_data = json.loads(result_text)
                transcript = result_data.get("text", "")
            except json.JSONDecodeError:
                transcript = result_text
            
            if not transcript:
                print(f"Empty transcript for call {call_id}")
                return
                
            print(f"🎤 Transcribed for call {call_id}: {transcript}")
            
            # Send to UI
            await publish_message_to_ui(
                runtime=self,
                source=f"Caller (Call {call_id[:8]})",
                user_message=transcript,
                ui_config=self._ui_config
            )

            # Add instruction/personal info prompt if available
            if call_id in self.call_prompts:
                composed_message = self._compose_prompt(transcript, call_id)
                print(f"Composed message with prompts for call {call_id}")
            else:
                composed_message = transcript
            
            print(f"Composed message for call {call_id}: {composed_message[:50]}...")
            
            # DIRECT COMMUNICATION: Send directly to domain agent and get response
            response = await self.send_message(
                UserMessage(content=composed_message, source=call_id),
                AgentId("domain_agent", call_id)
            )
            
            # Process response directly
            if response:
                response_content = response.content
                print(f"🤖 Domain agent response for call {call_id}: {response_content[:50]}...")
                
                # Send to UI
                await publish_message_to_ui(
                    runtime=self,
                    source=f"Agent (Call {call_id[:8]})",
                    user_message=response_content,
                    ui_config=self._ui_config
                )
                
                # Send to WebSocket
                if call_id in self.connections and self.connections[call_id]:
                    await self.connections[call_id].send(json.dumps({
                        "type": "text_response",
                        "data": {
                            "text": response_content
                        }
                    }))
                    print(f"Sent response to WebSocket for call {call_id}")
            
        except Exception as e:
            print(f"Error handling speech segment for call {call_id}: {str(e)}")
            import traceback
            traceback.print_exc()
        
    async def _load_prompts_for_call(self, call_id: str, request: CallRequest):
        """Load prompts from MCP for this call."""
        self.call_prompts[call_id] = {}
        
        # Load instruction prompt if specified
        if hasattr(request, 'instruction_prompt_id') and request.instruction_prompt_id:
            result = await self.workbench.call_tool(
                "prompt_get",
                arguments={"id": request.instruction_prompt_id},
                cancellation_token=CancellationToken()
            )
            print(f"Result from prompt_get: {result}")
            if not result.is_error:
                data = json.loads(result.to_text())
                if data.get("status") == "success":
                    self.call_prompts[call_id]["instruction"] = data.get("content", "")
                    print(f"Loaded instruction prompt for call {call_id}")
        
        # Load patient info prompt if specified
        if hasattr(request, 'patient_info_prompt_id') and request.patient_info_prompt_id:
            result = await self.workbench.call_tool(
                "prompt_get",
                arguments={"id": request.patient_info_prompt_id},
                cancellation_token=CancellationToken()
            )
            if not result.is_error:
                data = json.loads(result.to_text())
                if data.get("status") == "success":
                    self.call_prompts[call_id]["patient_info"] = data.get("content", "")
                    print(f"Loaded patient info prompt for call {call_id}")
    
    def _compose_prompt(self, transcript: str, call_id: str) -> str:
        """Compose a full prompt including instructions and patient info."""
        prompts = self.call_prompts.get(call_id, {})
        
        composed = ""
        
        # Add instruction prompt if available
        if "instruction" in prompts:
            composed += f"INSTRUCTIONS:\n{prompts['instruction']}\n\n"
            
        # Add patient info if available
        if "patient_info" in prompts:
            composed += f"PATIENT INFORMATION:\n{prompts['patient_info']}\n\n"
            
        # Add the actual transcript
        composed += f"CALLER SAID:\n{transcript}"
        
        return composed


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
            phone_number = "+12132841509"  # Mock phone number
            context = message.content
            
            # Generate unique call ID
            call_id = str(uuid.uuid4())
            
            # Select appropriate prompts for this call
            instruction_prompt_id = "eligibility_check"
            patient_info_prompt_id = "sample_patient"
            
            # Inform UI
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=f"Initiating call scenario with ID {call_id[:8]} using prompts: {instruction_prompt_id}, {patient_info_prompt_id}",
                ui_config=self._ui_config
            )
            
            # Route through FormatProxyAgent with prompt IDs
            await self.send_message(
                CallRequest(
                    call_id=call_id, 
                    to_number=phone_number, 
                    context=context,
                    instruction_prompt_id=instruction_prompt_id,
                    patient_info_prompt_id=patient_info_prompt_id
                ),
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