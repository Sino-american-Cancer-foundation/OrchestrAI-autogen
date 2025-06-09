import asyncio
import re
import random
import json
import websockets
from typing import Any, Dict, List, Optional, AsyncIterator, Awaitable, Callable
from uuid import uuid4

try:
    from ._types import GroupChatMessage, RequestToSpeak, MessageChunk, PatientData, AgentMode, UIAgentConfig, ConversationFinished
except ImportError:
    from _types import GroupChatMessage, RequestToSpeak, MessageChunk, PatientData, AgentMode, UIAgentConfig, ConversationFinished

from autogen_core import (
    RoutedAgent, 
    MessageContext, 
    DefaultTopicId,
    message_handler,
    CancellationToken
)
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import UserMessage, AssistantMessage, LLMMessage, SystemMessage, ChatCompletionClient
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.tools.mcp import McpWorkbench
from rich.console import Console
from rich.markdown import Markdown


class BaseGroupChatAgent(RoutedAgent):
    """A group chat participant using an LLM - follows distributed group chat pattern."""
    
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
        """Handle group chat messages - store in history for context"""
        self._chat_history.extend(
            [
                UserMessage(content=f"Transferred to {message.body.source}", source="system"),
                message.body,
            ]
        )

    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        """Handle requests to speak from orchestrator"""
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


class OrchestratorAgent(RoutedAgent):
    """Orchestrator that manages conversation flow - follows GroupChatManager pattern."""
    
    def __init__(
        self,
        model_client: ChatCompletionClient,
        participant_topic_types: List[str],
        participant_descriptions: List[str],
        ui_config: UIAgentConfig,
        max_rounds: int = 10,
    ) -> None:
        super().__init__("Orchestrator Agent")
        self._model_client = model_client
        self._num_rounds = 0
        self._participant_topic_types = participant_topic_types
        self._chat_history: List[LLMMessage] = []
        self._max_rounds = max_rounds
        self.console = Console()
        self._participant_descriptions = participant_descriptions
        self._previous_participant_topic_type: str | None = None
        self._ui_config = ui_config
        self._plan_created = False  # Track if plan has been created
    
    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        """Handle group chat messages - orchestrate next speaker"""
        assert isinstance(message.body, UserMessage)

        self._chat_history.append(message.body)
        
        # If this is the first user message and no plan created yet, create a complete plan first
        if not self._plan_created and isinstance(message.body, UserMessage) and message.body.source == "User":
            await self._create_complete_plan(ctx.cancellation_token)
            self._plan_created = True

        # Format message history
        messages: List[str] = []
        for msg in self._chat_history:
            if isinstance(msg.content, str):
                messages.append(f"{msg.source}: {msg.content}")
            elif isinstance(msg.content, list):
                messages.append(f"{msg.source}: {', '.join(msg.content)}")
        history = "\n".join(messages)
        
        # Format roles (allow all participants, including previous speaker)
        roles = "\n".join(
            [
                f"{topic_type}: {description}".strip()
                for topic_type, description in zip(
                    self._participant_topic_types, self._participant_descriptions, strict=True
                )
            ]
        )
        participants = str(self._participant_topic_types)

        # Check if we have a plan in the history
        plan_messages = [msg for msg in self._chat_history if isinstance(msg, AssistantMessage) and msg.source == "Orchestrator" and msg.content.startswith("Plan:")]
        plan_context = ""
        if plan_messages:
            plan_context = f"\nExecuting plan: {plan_messages[0].content[5:]}\n"  # Remove "Plan: " prefix

        selector_prompt = f"""You are orchestrating a conversation between agents:
{roles}.
{plan_context}
Read the following conversation. Then select the next agent from {participants} to respond based on the plan above and conversation flow. Only return the agent name.

{history}

CRITICAL INSTRUCTIONS:
1. You MUST strictly follow the established plan. Do not deviate from the plan unless absolutely necessary.
2. Before selecting the next agent, check which steps of the plan have been completed and which are still pending.
3. Select the agent that should handle the NEXT step in the plan that hasn't been completed yet.
4. Only return "FINISH: [REASON]" when ALL steps in the plan have been successfully completed AND the user's original request has been fully addressed.
5. Do NOT return "FINISH" just because agents have spoken - ensure the plan's objectives are actually accomplished.
6. If you exceed {self._max_rounds} rounds limit, return "FINISH: [REASON]" but only as a last resort.

Read the above conversation. If the plan is complete, return "FINISH: [REASON]". Otherwise, select the next agent from {participants} to respond. Follow the established plan strictly and ensure all plan steps are completed before finishing.
"""
        system_message = SystemMessage(content=selector_prompt)
        
        completion = await self._model_client.create([system_message], cancellation_token=ctx.cancellation_token)

        assert isinstance(
            completion.content, str
        ), f"Completion content must be a string, but is: {type(completion.content)}"

        # Log what the LLM decided
        await publish_message_to_ui(
            runtime=self, 
            source="Orchestrator_Debug", 
            user_message=f"🤖 **LLM DECISION**: '{completion.content.strip()}'", 
            ui_config=self._ui_config
        )

        if completion.content.upper().startswith("FINISH"):
            # Parse the finish reason from "FINISH: reason" format
            if ":" in completion.content:
                finish_msg = completion.content.split(":", 1)[1].strip()
            else:
                finish_msg = "The conversation has concluded. Thank you for using our assistant system!"
            
            manager_message = f"\n{'-'*80}\n Orchestrator ({id(self)}): {finish_msg}"
            await publish_message_to_ui(
                runtime=self, source=self.id.type, user_message=finish_msg, ui_config=self._ui_config
            )
            self.console.print(Markdown(manager_message))
            
            # Notify all participant agents that the conversation is finished
            conversation_finished_msg = ConversationFinished(reason=finish_msg)
            for participant_topic_type in self._participant_topic_types:
                await self.publish_message(conversation_finished_msg, DefaultTopicId(type=participant_topic_type))
            
            return

        selected_topic_type: str
        for topic_type in self._participant_topic_types:
            if topic_type.lower() in completion.content.lower():
                selected_topic_type = topic_type
                self._previous_participant_topic_type = selected_topic_type
                
                self.console.print(
                    Markdown(f"\n{'-'*80}\n Orchestrator ({id(self)}): Asking `{selected_topic_type}` to speak")
                )
                await self.publish_message(RequestToSpeak(), DefaultTopicId(type=selected_topic_type))
                return
        raise ValueError(f"Invalid agent selected: {completion.content}")
    
    async def _create_complete_plan(self, cancellation_token: CancellationToken) -> None:
        """Create a complete plan for handling the user's request."""
        # Get the user's request
        user_request = self._chat_history[-1].content
        
        # Format available agents and their capabilities
        agent_capabilities = "\n".join(
            [
                f"- {topic_type}: {description}"
                for topic_type, description in zip(
                    self._participant_topic_types, self._participant_descriptions, strict=True
                )
            ]
        )
        
        planning_prompt = f"""You are an orchestrator for a assistant system. Create a concise step by step plan to address the user's request.

Available agents:
{agent_capabilities}

User request: {user_request}

Create a structured plan with numbered steps. Each step should:
1. Specify which agent should handle it
2. Clearly define what that agent needs to accomplish
3. Be specific about the expected outcome

Format your plan as:
Step 1: [Specific task/objective]
Step 2: [Specific task/objective]
Step 3: [Specific task/objective] (if needed)

Provide a brief plan with clear steps. Be concise and focus only on the essential actions needed.
"""
        
        system_message = SystemMessage(content=planning_prompt)
        completion = await self._model_client.create([system_message], cancellation_token=cancellation_token)
        
        assert isinstance(completion.content, str)
        
        # Present the plan to the user
        plan_message = f"**Plan**: {completion.content}\n\n---\n\nExecuting plan..."
        
        await publish_message_to_ui(
            runtime=self, 
            source="Orchestrator", 
            user_message=plan_message, 
            ui_config=self._ui_config
        )
        
        self.console.print(Markdown(f"\n{'-'*80}\n**Orchestrator Plan**: {completion.content}"))
        
        # Store the plan in chat history for future reference
        self._chat_history.append(AssistantMessage(content=f"Plan: {completion.content}", source="Orchestrator"))


class TwilioProxyAgent(BaseGroupChatAgent):
    """Twilio proxy agent that connects external participants via phone calls with full WebSocket functionality."""
    
    def __init__(
        self,
        description: str,
        group_chat_topic_type: str,
        model_client: ChatCompletionClient,
        system_message: str,
        ui_config: UIAgentConfig,
        websocket_port: int,
        phone_pattern: str,
        workbench: McpWorkbench,
        mode: AgentMode = AgentMode.INACTIVE
    ) -> None:
        super().__init__(description, group_chat_topic_type, model_client, system_message, ui_config)
        self.websocket_port = websocket_port
        self.phone_pattern = phone_pattern
        self.mode = mode
        self.workbench = workbench
        
        # WebSocket session management (like WrapperAgent)
        self.active_websocket_sessions: Dict[str, Dict[str, Any]] = {}
        self.websocket_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.call_conversations: Dict[str, List[Dict[str, str]]] = {}
        self.external_participant_connected = False
    
    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        """Handle group chat messages - store in history for context."""
        # Call parent to store in history for context when generating responses
        await super().handle_message(message, ctx)
    
    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        """Handle RequestToSpeak based on current mode."""
        
        if self.mode == AgentMode.INACTIVE:
            # Check history for phone numbers to initiate call
            await self._check_history_for_phone_call()
        else:
            # ACTIVE mode: Generate response for external participant
            await self._generate_response_for_group_chat()
    
    @message_handler
    async def handle_conversation_finished(self, message: ConversationFinished, ctx: MessageContext) -> None:
        """Handle conversation finish notification and terminate active calls."""
        print(f"[TwilioProxyAgent] Conversation finished: {message.reason}")
        await self._terminate_all_active_calls(message.reason)
    
    async def _check_history_for_phone_call(self) -> None:
        """Check chat history for phone call requests/needs when in INACTIVE mode."""
        # Build context from chat history to understand if a call is needed
        history_context = "\n".join([
            f"{msg.source if hasattr(msg, 'source') else 'unknown'}: {msg.content if hasattr(msg, 'content') else str(msg)}"
            for msg in self._chat_history[-10:]  # Last 10 messages for context
        ])
        
        # Use LLM to determine if a phone call is needed and extract phone number
        system_message = SystemMessage(content="""
You are analyzing a conversation to determine if a phone call should be made.
Look for:
1. Explicit requests to make a phone call
2. Mentions of needing to contact someone by phone
3. Phone numbers mentioned in context of calling

If a call should be made, respond with: CALL_NEEDED:{phone_number}, and the number should be in the E.164 format.
If no call is needed, respond with: NO_CALL_NEEDED

""")
        
        analysis_msg = UserMessage(content=f"Analyze this conversation:\n{history_context}", source="system")
        completion = await self._model_client.create([system_message, analysis_msg])
        assert isinstance(completion.content, str)
        
        response = completion.content.strip()
        
        if response.startswith("CALL_NEEDED:"):
            phone_number = response.split("CALL_NEEDED:")[1].strip()
            await self._initiate_call(phone_number)
        else:
            # No call needed
            await publish_message_to_ui_and_backend(
                runtime=self,
                source=self.id.type,
                user_message="Agent is inactive. Not detecting a need for a call.",
                ui_config=self._ui_config,
                group_chat_topic_type=self._group_chat_topic_type,
            )
    
    async def _generate_response_for_group_chat(self) -> None:
        """Generate response for group chat when requested to speak."""
        try:
            # Build context for response generation using chat history
            context = self._build_context_for_response_generation()
            
            # Generate response using model
            enhanced_system_content = self._system_message.content
            enhanced_system_message = SystemMessage(content=enhanced_system_content)
            context_message = UserMessage(content=context, source="system")
            
            # Use streaming generation
            accumulated_response = ""
            current_sentence = ""
            
            stream = self._model_client.create_stream([enhanced_system_message, context_message])
            
            async for chunk in stream:
                if isinstance(chunk, str):
                    accumulated_response += chunk
                    current_sentence += chunk
                    
                    # Check if we have a complete sentence
                    if self._detect_sentence_end(current_sentence):
                        # Send the complete sentence as partial response to external participant
                        await self._send_response_to_external_participant(
                            current_sentence.strip(),
                            list(self.active_websocket_sessions.keys())[0] if self.active_websocket_sessions else "",
                            is_partial=True
                        )
                        current_sentence = ""
                else:
                    break
            
            # Send any remaining text as final partial response
            if current_sentence.strip():
                await self._send_response_to_external_participant(
                    current_sentence.strip(),
                    list(self.active_websocket_sessions.keys())[0] if self.active_websocket_sessions else "",
                    is_partial=True
                )
            
            # Clean the response to remove any unwanted prefixes
            cleaned_response = self._clean_response(accumulated_response)
            
            # Send final complete response to external participant
            session_id = list(self.active_websocket_sessions.keys())[0] if self.active_websocket_sessions else ""
            if session_id:
                await self._send_response_to_external_participant(cleaned_response, session_id)
                
                # Update conversation history with cleaned response
                if session_id in self.call_conversations:
                    self.call_conversations[session_id].append({
                        "role": "assistant",
                        "content": cleaned_response
                    })
            
            # Clean the response to remove any unwanted prefixes
            cleaned_response = self._clean_response(accumulated_response)
            
            # Publish to UI only (not to group chat to avoid triggering orchestrator)
            await publish_message_to_ui(
                runtime=self,
                source=self.id.type,
                user_message=cleaned_response,
                ui_config=self._ui_config,
            )
            
        except Exception as e:
            print(f"[TwilioProxyAgent] Error generating response for group chat: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def _initiate_call(self, phone_number: str) -> None:
        """Initiate phone call using MCP tools and connect to WebSocket."""
        session_id = str(uuid4())
        ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        
        try:
            print(f"[TwilioProxyAgent] Initiating call to {phone_number} with session_id: {session_id}")
            
            # Use real MCP make_call tool
            call_result = await self.workbench.call_tool(
                "make_call",
                arguments={
                    "to_number": phone_number,
                    "information": f"Agent call initiated for {phone_number}"
                },
                cancellation_token=CancellationToken()
            )
            print(call_result)
            
            if call_result.is_error:
                error_msg = f"MCP make_call failed: {call_result.result if call_result.result else 'Unknown error'}"
                print(f"[TwilioProxyAgent] {error_msg}")
                return
            
            # Parse call result
            result_text = call_result.result[0].content if call_result.result and hasattr(call_result.result[0], 'content') else ""
            call_data = json.loads(result_text)
            
            if call_data.get("status") != "success":
                error_msg = call_data.get("message", "Failed to make call")
                print(f"[TwilioProxyAgent] {error_msg}")
                return
            
            call_sid = call_data.get("call_sid", f"call_{session_id[:8]}")
            websocket_url = call_data.get("websocket_url")
            
            if not websocket_url:
                error_msg = "No WebSocket URL provided by MCP server"
                print(f"[TwilioProxyAgent] {error_msg}")
                return
            
            # Create session tracking
            session = {
                "session_id": session_id,
                "call_sid": call_sid,
                "websocket_url": websocket_url,
                "phone_number": phone_number,
                "is_active": True
            }
            self.active_websocket_sessions[session_id] = session
            self.call_conversations[session_id] = []
            
            # Connect to WebSocket
            print(f"[TwilioProxyAgent] Connecting to WebSocket URL: {websocket_url} for session {session_id}")
            ws_connection = await websockets.connect(websocket_url)
            self.websocket_connections[session_id] = ws_connection
            print(f"[TwilioProxyAgent] WebSocket connection established for session {session_id}")
            
            # Switch to active mode
            self.mode = AgentMode.ACTIVE
            self.external_participant_connected = True
            
            # Connection established (logging only)
            print(f"[TwilioProxyAgent] Connected to external participant via phone call {call_sid}")
            
            # Start processing WebSocket messages (like WrapperAgent)
            asyncio.create_task(self._process_websocket_session(session_id))
            
        except websockets.exceptions.WebSocketException as e_ws:
            error_msg = f"WebSocket connection failed for session {session_id}: {str(e_ws)}"
            print(f"[TwilioProxyAgent] {error_msg}")
            if session_id in self.active_websocket_sessions:
                self.active_websocket_sessions[session_id]["is_active"] = False
            await self._cleanup_session(session_id)
        except Exception as e:
            error_msg = f"Failed to initiate call to {phone_number}: {str(e)}"
            print(f"[TwilioProxyAgent] {error_msg}")
            if session_id in self.active_websocket_sessions:
                self.active_websocket_sessions[session_id]["is_active"] = False
            await self._cleanup_session(session_id)
    
    async def _process_websocket_session(self, session_id: str) -> None:
        """Process messages for a WebSocket session (like WrapperAgent)."""
        ws = self.websocket_connections.get(session_id)
        session = self.active_websocket_sessions.get(session_id)

        if not session:
            print(f"[TwilioProxyAgent] Session {session_id} not found at start of _process_websocket_session. Aborting.")
            await self._cleanup_session(session_id)
            return
        
        if not ws:
            print(f"[TwilioProxyAgent] WebSocket connection {session_id} not found for active session. Aborting.")
            session["is_active"] = False
            await self._cleanup_session(session_id)
            return
        
        print(f"[TwilioProxyAgent] Starting to process WebSocket session {session_id}. Session active: {session['is_active']}")
        try:
            while session["is_active"]:  # Loop based on session active flag
                try:
                    message_str = await ws.recv()
                    data = json.loads(message_str)
                    
                    msg_type = data.get('type')
                    print(f"[TwilioProxyAgent] Received message type: {msg_type}")
                    
                    if msg_type == "speech_segment":
                        await self._process_websocket_message(data, session_id)
                        
                    elif msg_type == "call_started":
                        stream_sid = data.get('data', {}).get('stream_sid', 'unknown')
                        # Publish call status to UI only (not to group chat to avoid triggering orchestrator)
                        await publish_message_to_ui(
                            runtime=self,
                            source=self.id.type,
                            user_message=f"Call started - Stream SID: {stream_sid}",
                            ui_config=self._ui_config,
                        )
                        
                    elif msg_type == "call_ended":
                        # Publish eligibility result to UI only (not to group chat to avoid triggering orchestrator)
                        await publish_message_to_ui(
                            runtime=self,
                            source=self.id.type,
                            user_message=f"Call ended - External participant disconnected",
                            ui_config=self._ui_config,
                        )
                        session["is_active"] = False  # Mark inactive on call_ended
                        
                except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e_closed:
                    print(f"[TwilioProxyAgent] WebSocket connection closed for session {session_id}: {type(e_closed).__name__} - {e_closed}")
                    session["is_active"] = False
                except json.JSONDecodeError:
                    print(f"[TwilioProxyAgent] Invalid JSON received for session {session_id}")
                    continue
                except Exception as e:
                    print(f"[TwilioProxyAgent] Error processing WebSocket message for session {session_id}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    session["is_active"] = False
            
            print(f"[TwilioProxyAgent] Exited WebSocket processing loop for session {session_id}. Session active: {session['is_active']}")
                    
        except Exception as e:
            print(f"[TwilioProxyAgent] Outer error in WebSocket session {session_id}: {str(e)}")
            if session:
                session["is_active"] = False
            import traceback
            traceback.print_exc()
        finally:
            print(f"[TwilioProxyAgent] Performing final cleanup for session {session_id}.")
            # Ensure session is marked inactive if not already
            if session and session["is_active"]:
                 print(f"[TwilioProxyAgent] Warning: Session {session_id} was still marked active in finally block. Forcing inactive.")
                 session["is_active"] = False
            await self._cleanup_session(session_id)
    
    async def _process_websocket_message(self, ws_message: dict, session_id: str) -> None:
        """Process a single WebSocket message (like WrapperAgent)."""
        try:
            # Extract audio payload
            payload = ws_message.get('data', {}).get('payload')
            if not payload:
                return
            
            # Transcribe audio
            transcribe_result = await self.workbench.call_tool(
                "transcribe_audio",
                arguments={
                    "audio_data": payload,
                    "model": "whisper"
                },
                cancellation_token=CancellationToken()
            )
            
            if transcribe_result.is_error:
                print(f"[TwilioProxyAgent] Transcription error for session {session_id}")
                return
            
            # Parse transcript
            result_text = transcribe_result.result[0].content if transcribe_result.result and hasattr(transcribe_result.result[0], 'content') else ""
            result_data = json.loads(result_text)
            print(f"[TwilioProxyAgent] Transcription result: {result_text}")
            
            if result_data.get("status") != "success":
                print(f"[TwilioProxyAgent] Transcription failed: {result_data.get('message', 'Unknown error')}")
                return
            
            transcript = result_data.get("text", "")
            
            if not transcript:
                return
            
            print(f"[TwilioProxyAgent] 🎤 Transcribed: {transcript}")
            
            # Update conversation history
            if session_id not in self.call_conversations:
                self.call_conversations[session_id] = []
            
            self.call_conversations[session_id].append({
                "role": "user",
                "content": transcript
            })
            
            # Immediately add to TwilioProxyAgent's chat history to ensure it's available for response generation
            external_participant_message = UserMessage(
                content=transcript,
                source="External_Participant_TwilioProxyAgent"
            )
            self._chat_history.append(external_participant_message)
            
            # Publish to group chat (external participant speaking via proxy)
            await publish_message_to_ui_and_backend(
                runtime=self,
                source=f"External_Participant_TwilioProxyAgent",
                user_message=transcript,
                ui_config=self._ui_config,
                group_chat_topic_type=self._group_chat_topic_type,
            )
            
            # Note: Response generation is handled by orchestrator via RequestToSpeak
            # The TwilioProxyAgent will only respond to external participant when explicitly asked by the orchestrator
            
        except Exception as e:
            print(f"[TwilioProxyAgent] Error processing WebSocket message: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _build_context_for_response_generation(self) -> str:
        """Build context for generating response using full chat history."""
        context = []
        
        # Add full group chat history for context
        if self._chat_history:
            context.append("Phone call conversation context:")
            for msg in self._chat_history[-10:]:  # Last 10 messages for full context
                if hasattr(msg, 'source') and hasattr(msg, 'content'):
                    # Clean up the source name for better context
                    source_name = msg.source
                    if source_name == "External_Participant_TwilioProxyAgent":
                        source_name = "External Participant"
                    context.append(f"{source_name}: {msg.content}")
        
        context.append("\nYou are the proxy agent. Generate ONLY your direct response to the external participant without any prefixes or labels:")
        
        return "\n".join(context)
    
    def _detect_sentence_end(self, text: str) -> bool:
        """Detect if text ends with sentence-ending punctuation."""
        return bool(re.search(r'[,.!?]\s*$', text))
    
    def _clean_response(self, response: str) -> str:
        """Clean the response to remove unwanted prefixes and formatting."""
        # Remove common unwanted prefixes that the LLM might generate
        prefixes_to_remove = [
            "External_Participant_TwilioProxyAgent:",
            "TwilioProxyAgent:",
            "ProxyAgent:",
            "Proxy Agent:",
            "Assistant:",
            "Agent:",
        ]
        
        cleaned = response.strip()
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        
        return cleaned
    
    async def _send_response_to_external_participant(self, response: str, session_id: str, is_partial: bool = False) -> None:
        """Send response to external participant via WebSocket."""
        ws = self.websocket_connections.get(session_id)
        session = self.active_websocket_sessions.get(session_id)
        
        response_type = "partial" if is_partial else "final"

        if not session:
            print(f"[TwilioProxyAgent] Cannot send {response_type} response: Session {session_id} not found.")
            return

        if not session["is_active"]:
            print(f"[TwilioProxyAgent] Cannot send {response_type} response: Session {session_id} is inactive.")
            return
            
        if not ws:
            print(f"[TwilioProxyAgent] Cannot send {response_type} response: WebSocket for session {session_id} not found though session is active.")
            session["is_active"] = False
            await self._cleanup_session(session_id)
            return
                
        try:
            message_type = "partial_response" if is_partial else "text_response"
            await ws.send(json.dumps({
                "type": message_type,
                "data": {
                    "text": response,
                    "source": "agent"
                }
            }))
            
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e_closed:
            print(f"[TwilioProxyAgent] WebSocket connection closed while sending {response_type} response for session {session_id}: {type(e_closed).__name__} - {e_closed}")
            session["is_active"] = False
        except Exception as e:
            print(f"[TwilioProxyAgent] Error sending {response_type} response for session {session_id}: {str(e)}")
            session["is_active"] = False
            
    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up session resources (like WrapperAgent)."""
        print(f"[TwilioProxyAgent] Initiating cleanup for session {session_id}")
        ws = self.websocket_connections.get(session_id)
        if ws:
            try:
                print(f"[TwilioProxyAgent] Attempting to close WebSocket for session {session_id}")
                await ws.close()
                print(f"[TwilioProxyAgent] WebSocket closed for session {session_id}")
            except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK):
                print(f"[TwilioProxyAgent] WebSocket already closed for session {session_id} during cleanup.")
            except AttributeError as ae:
                 print(f"[TwilioProxyAgent] AttributeError during ws.close() for session {session_id} (type: {type(ws)}): {ae}")
            except Exception as e_close:
                 print(f"[TwilioProxyAgent] Exception during ws.close() for session {session_id} (type: {type(ws)}): {e_close}")
            finally:
                if session_id in self.websocket_connections:
                    del self.websocket_connections[session_id]
        else:
            print(f"[TwilioProxyAgent] No WebSocket connection found in dict for session {session_id} during cleanup.")
        
        active_session = self.active_websocket_sessions.get(session_id)
        if active_session:
            active_session["is_active"] = False
            if session_id in self.active_websocket_sessions:
                 del self.active_websocket_sessions[session_id]
            print(f"[TwilioProxyAgent] Active session entry removed for {session_id}")
        else:
            print(f"[TwilioProxyAgent] No active_session entry found for {session_id} during cleanup.")
            
        if session_id in self.call_conversations:
            del self.call_conversations[session_id]
            print(f"[TwilioProxyAgent] Conversation history removed for {session_id}")
            
        # Check if any sessions are still active
        active_sessions = [s for s in self.active_websocket_sessions.values() if s["is_active"]]
        if not active_sessions:
            self.mode = AgentMode.INACTIVE
            self.external_participant_connected = False
            print(f"[TwilioProxyAgent] No more active sessions, switching to INACTIVE mode")
            
        print(f"[TwilioProxyAgent] Session {session_id} cleanup process completed.")
    
    async def _terminate_all_active_calls(self, reason: str) -> None:
        """Terminate all active phone calls when conversation finishes."""
        print(f"[TwilioProxyAgent] Terminating all active calls. Reason: {reason}")
        
        # Get list of active session IDs to avoid modifying dict during iteration
        active_session_ids = [
            session_id for session_id, session in self.active_websocket_sessions.items() 
            if session["is_active"]
        ]
        
        if not active_session_ids:
            print(f"[TwilioProxyAgent] No active calls to terminate")
            return
        
        # Send end_call message to each active session
        for session_id in active_session_ids:
            await self._send_end_call_message(session_id, reason)
        
        print(f"[TwilioProxyAgent] Sent end_call messages to {len(active_session_ids)} active sessions")
    
    async def _send_end_call_message(self, session_id: str, reason: str) -> None:
        """Send end_call message to WebSocket to gracefully terminate the call."""
        ws = self.websocket_connections.get(session_id)
        session = self.active_websocket_sessions.get(session_id)
        
        if not session:
            print(f"[TwilioProxyAgent] Cannot send end_call: Session {session_id} not found.")
            return

        if not session["is_active"]:
            print(f"[TwilioProxyAgent] Cannot send end_call: Session {session_id} is already inactive.")
            return
            
        if not ws:
            print(f"[TwilioProxyAgent] Cannot send end_call: WebSocket for session {session_id} not found.")
            session["is_active"] = False
            await self._cleanup_session(session_id)
            return
                
        try:
            end_call_message = {
                "type": "end_call",
                "data": {
                    "reason": reason,
                    "source": "agent_system"
                }
            }
            
            await ws.send(json.dumps(end_call_message))
            print(f"[TwilioProxyAgent] Sent end_call message to session {session_id}")
            
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e_closed:
            print(f"[TwilioProxyAgent] WebSocket connection closed while sending end_call for session {session_id}: {type(e_closed).__name__} - {e_closed}")
            session["is_active"] = False
            await self._cleanup_session(session_id)
        except Exception as e:
            print(f"[TwilioProxyAgent] Error sending end_call for session {session_id}: {str(e)}")
            session["is_active"] = False
            await self._cleanup_session(session_id)


class MedicalDataAgent(BaseGroupChatAgent):
    """Agent that retrieves medical data for patients."""
    
    def __init__(
        self,
        description: str,
        group_chat_topic_type: str,
        model_client: ChatCompletionClient,
        system_message: str,
        ui_config: UIAgentConfig,
    ) -> None:
        super().__init__(description, group_chat_topic_type, model_client, system_message, ui_config)
    
    @message_handler
    async def handle_request_to_speak(self, message: RequestToSpeak, ctx: MessageContext) -> None:
        """Enhanced request to speak handler with medical data lookup."""
        # Add medical data context to system message
        enhanced_system_content = f"""{self._system_message.content}

When responding, you can access patient medical data. If the conversation mentions patients or medical information needs, 
provide relevant medical data from your database. Simulate a brief search delay before responding with detailed patient information."""

        enhanced_system_message = SystemMessage(content=enhanced_system_content)
        
        self._chat_history.append(
            UserMessage(content=f"Transferred to {self.id.type}, adopt the persona immediately.", source="system")
        )
        
        # Get patient data and include in response
        patient_data = await self._get_patient_data()
            
        # Add patient data context
        medical_context = f"""
Current patient data available:
Patient Name: {patient_data.name} (Member ID: {patient_data.patient_id})
Age: {patient_data.age}
Gender: {patient_data.gender}
Date of Birth: {patient_data.date_of_birth}
Physician: {patient_data.physician} (NPI: {patient_data.npi})
Contact/Call back number: {patient_data.callback_number}
Medical History: {', '.join(patient_data.medical_history)}
Current Medications: {', '.join(patient_data.current_medications)}
Insurance: {patient_data.insurance_info}

Use this information to provide helpful medical context in your response.
"""
        
        medical_context_msg = UserMessage(content=medical_context, source="system")
        completion = await self._model_client.create([enhanced_system_message] + self._chat_history + [medical_context_msg])
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
    
    async def _get_patient_data(self) -> PatientData:
        """Simulate retrieving patient data from medical database."""
        return PatientData(
            patient_id="E01222465",
            name="John Smith",
            age=38,
            gender="Male",
            date_of_birth="August 23, 1987",
            physician="Dr. Julius Caesar",
            npi="168719879",
            callback_number="554-187-8789",
            medical_history=[
                "Type 2 Diabetes",
                "Hypertension",
                "Seasonal Allergies"
            ],
            current_medications=[
                "Metformin 500mg",
                "Lisinopril 10mg",
                "Cetirizine 10mg"
            ],
            insurance_info={
                "provider": "HealthFirst Insurance",
                "customer_service_phone": "2132841509",
                "customer_service_email": "customer_service@healthfirst.com"
            }
        )


class UIAgent(RoutedAgent):
    """Handles UI-related tasks and message processing for the distributed group chat system."""
    
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
    """Publish message to UI with streaming effect."""
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
    """Publish message to both UI and backend group chat."""
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