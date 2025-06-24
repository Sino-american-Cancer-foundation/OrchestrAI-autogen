import asyncio
import json
import uuid
import websockets
import httpx
import re
from typing import Dict, List, Optional, Any

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

from ._types import (
    MessageChunk, UserMessage, AssistantMessage, WebSocketSession,
    UIAgentConfig, FlowType
)


class WrapperAgent(RoutedAgent):
    """Universal wrapper agent that handles all routing and orchestration"""
    
    def __init__(
        self,
        description: str,
        workbench: McpWorkbench,
        ui_config: UIAgentConfig,
        model_client: Optional[ChatCompletionClient] = None
    ) -> None:
        super().__init__(description=description)
        self.workbench = workbench
        self._ui_config = ui_config
        
        # Initialize model client
        if model_client:
            self._model_client = model_client
        else:
            raise ValueError("Model_client must be provided")
        
        # Initialize system message
        self._system_message = SystemMessage(
            content="You are a helpful AI assistant tasked with summarizing phone conversations. Please provide concise summaries including key points and outcomes."
        )
        
        # State management
        self.active_websocket_sessions: Dict[str, WebSocketSession] = {}
        self.websocket_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}
        self.session_contexts: Dict[str, str] = {}
        # New history state for memory
        self.agent_history: List[Dict[str, Any]] = []
    
    @property
    def model_client(self) -> ChatCompletionClient:
        """Get the model client used by this agent."""
        return self._model_client
    
    @message_handler
    async def handle_user_request(self, message: UserMessage, ctx: MessageContext) -> Optional[AssistantMessage]:
        """Main entry point for all user requests"""
        print(f"\n--- WrapperAgent received: {message.content}")
        
        # Detect flow type
        flow_type = await self._detect_flow_type(message.content)
        
        if flow_type == FlowType.SINGLE_RESPONSE:
            return await self._handle_single_response_flow(message, ctx)
        else:  # WEBSOCKET_CONVERSATION
            return await self._handle_websocket_flow(message, ctx)
    
    async def _detect_flow_type(self, content: str) -> FlowType:
        """Analyze request to determine flow type"""
        # Simple keyword detection - could be enhanced with ML
        call_keywords = ["call", "phone", "dial", "contact", "speak"]
        
        if any(keyword in content.lower() for keyword in call_keywords):
            return FlowType.WEBSOCKET_CONVERSATION
        return FlowType.SINGLE_RESPONSE
    
    async def _handle_single_response_flow(self, message: UserMessage, ctx: MessageContext) -> AssistantMessage:
        """Handle single request → single response flow"""
        try:
            # Add message to history
            history_entry = {
                "type": "single_response",
                "input": message.content,
                "response": None,
                "timestamp": str(uuid.uuid4())  # Using UUID as timestamp for now
            }
            self.agent_history.append(history_entry)
            
            # Send to UI that we're processing
            await self._publish_to_ui(
                source="WrapperAgent",
                content=f"Processing your request..."
            )
            
            # Build context with history
            context = self._build_context_with_history(message.content)
            
            # Call AI agent MCP tool
            result = await self.workbench.call_tool(
                "ask_ai_agent",
                arguments={
                    "question": context
                },
                cancellation_token=ctx.cancellation_token
            )
            
            if result.is_error:
                error_msg = "Failed to get response from AI agent"
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            
            # Extract response from the result
            response_text = result.result[0].content if result.result and hasattr(result.result[0], 'content') else ""
            
            try:
                response_data = json.loads(response_text)
                
                if response_data.get("status") == "streaming_url_generated":
                    stream_url = response_data.get("stream_url")
                    stream_id = response_data.get("stream_id")
                    
                    if not stream_url:
                        error_msg = "No streaming URL provided"
                        await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                        return AssistantMessage(content=error_msg, source="wrapper")
                    
                    print(f"Connecting to streaming URL")
                    accumulated_response = ""  # Track complete response
                    
                    # Connect to streaming endpoint
                    async with httpx.AsyncClient(timeout=None) as stream_client:
                        async with stream_client.stream("GET", stream_url, headers={"Accept": "text/event-stream"}) as sse_response:
                            if sse_response.status_code != 200:
                                error_msg = f"Streaming connection failed (Status {sse_response.status_code})"
                                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                                return AssistantMessage(content=error_msg, source="wrapper")
                            
                            event_name = None
                            event_data_lines = []
                            buffer = ""  # Buffer for incomplete lines
                            
                            async for line_bytes in sse_response.aiter_bytes():
                                # Decode and add to buffer
                                buffer += line_bytes.decode('utf-8')
                                
                                # Process complete lines from buffer
                                while '\n' in buffer:
                                    line, buffer = buffer.split('\n', 1)
                                    line = line.strip()
                                    
                                    if line.startswith("event:"):
                                        event_name = line.split("event:", 1)[1].strip()
                                    elif line.startswith("data:"):
                                        data_line = line.split("data:", 1)[1].strip()
                                        event_data_lines.append(data_line)
                                    elif not line and event_name and event_data_lines:  # Empty line = end of event
                                        try:
                                            full_event_data = "".join(event_data_lines)
                                            data_json = json.loads(full_event_data)
                                            
                                            if event_name == "chunk":
                                                chunk_text = data_json.get("text_chunk", "")
                                                accumulated_response += chunk_text
                                                
                                            elif event_name == "error":
                                                error_msg = f"Streaming error: {data_json.get('error', 'Unknown error')}"
                                                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                                                return AssistantMessage(content=error_msg, source="wrapper")
                                                
                                            elif event_name == "completed":                                                
                                                # Send complete response to UI
                                                await self._publish_to_ui(
                                                    "AI Agent",
                                                    accumulated_response,
                                                    is_streaming=False
                                                )
                                                
                                                # Update history with response
                                                history_entry["response"] = accumulated_response
                                                
                                                return AssistantMessage(content=accumulated_response, source="wrapper")
                                                
                                        except json.JSONDecodeError as e:
                                            print(f"Error parsing streaming event: {e}")
                                        
                                        # Reset for next event
                                        event_name = None
                                        event_data_lines = []
                                        
                else:
                    error_msg = f"Unexpected response status: {response_data.get('status')}"
                    await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                    return AssistantMessage(content=error_msg, source="wrapper")
                    
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing AI response: {e}"
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            except Exception as e:
                error_msg = f"Error in streaming process: {e}"
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            
        except Exception as e:
            error_msg = f"Error in single response flow: {str(e)}"
            print(error_msg)
            await self._publish_to_ui("WrapperAgent", error_msg)
            return AssistantMessage(content=error_msg, source="wrapper")
    
    def _build_context_with_history(self, current_input: str) -> str:
        """Build context string including relevant history"""
        context = []
        
        # Add recent history (last 5 interactions)
        if self.agent_history:
            context.append("Interactions history:")
            for entry in self.agent_history:
                # print(entry)
                if entry["response"]:  # Only include completed interactions
                    context.append(f"User: {entry['input']}")
                    context.append(f"Assistant: {entry['response']}\n")
                else: # if no history, just add the current input
                    context.append(f"User: {current_input}")
        
        # Add current input
        context.append(f"Current question: {current_input}")
        context.append("\nPlease answer current question based on the rules and information you have:")
        
        return "\n".join(context)
    
    async def _handle_websocket_flow(self, message: UserMessage, ctx: MessageContext) -> AssistantMessage:
        """Handle WebSocket conversation flow"""
        session_id = str(uuid.uuid4())
        ws_connection: Optional[websockets.WebSocketClientProtocol] = None # Initialize
        
        try:
            # Add message to history
            history_entry = {
                "type": "websocket_conversation",
                "input": message.content,
                "response": None,  # Will be filled with summary later
                "session_id": session_id,
                "timestamp": str(uuid.uuid4())
            }
            self.agent_history.append(history_entry)
            
            # Extract phone number (simplified - in production use better parsing)
            to_number = "+12132841509"  # Default/mock number
            
            await self._publish_to_ui(
                "WrapperAgent",
                f"Initiating call to {to_number}..."
            )
            
            # Make the call using MCP tool
            call_result = await self.workbench.call_tool(
                "make_call",
                arguments={
                    "to_number": to_number,
                    "information": message.content
                },
                cancellation_token=ctx.cancellation_token
            )
            
            if call_result.is_error:
                error_msg = "Failed to initiate call"
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            
            # Parse call result
            result_text = call_result.result[0].content if call_result.result and hasattr(call_result.result[0], 'content') else ""
            call_data = json.loads(result_text)
            
            if call_data.get("status") != "success":
                error_msg = call_data.get("message", "Failed to make call")
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            
            call_sid = call_data.get("call_sid", "unknown")
            websocket_url = call_data.get("websocket_url", "")
            
            if not websocket_url:
                error_msg = "No WebSocket URL returned"
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            
            # Create session
            session = WebSocketSession(
                session_id=session_id,
                call_sid=call_sid,
                websocket_url=websocket_url,
                original_request=message.content,
                is_active=True # Explicitly set active on creation
            )
            self.active_websocket_sessions[session_id] = session
            self.session_contexts[session_id] = message.content
            
            # Connect to WebSocket
            print(f"Connecting to WebSocket URL: {websocket_url} for session {session_id}")
            ws_connection = await websockets.connect(websocket_url)
            self.websocket_connections[session_id] = ws_connection
            print(f"WebSocket connection established for session {session_id}, type: {type(ws_connection)}")
            
            await self._publish_to_ui(
                "WrapperAgent",
                f"Connected to call {call_sid}"
            )
            
            # Start processing WebSocket messages
            asyncio.create_task(self._process_websocket_session(session_id))
            
            return AssistantMessage(
                content=f"Call initiated with ID {session_id[:8]}",
                source="wrapper"
            )
            
        except websockets.exceptions.WebSocketException as e_ws:
            error_msg = f"WebSocket connection failed for session {session_id}: {str(e_ws)}"
            print(error_msg)
            await self._publish_to_ui("WrapperAgent", error_msg)
            if session_id in self.active_websocket_sessions:
                self.active_websocket_sessions[session_id].is_active = False
            await self._cleanup_session(session_id) # Ensure cleanup on connection failure
            return AssistantMessage(content=error_msg, source="wrapper")
        except Exception as e:
            error_msg = f"Error in WebSocket flow for session {session_id}: {str(e)}"
            print(error_msg)
            await self._publish_to_ui("WrapperAgent", error_msg)
            if session_id in self.active_websocket_sessions:
                self.active_websocket_sessions[session_id].is_active = False
            await self._cleanup_session(session_id) # Ensure cleanup on other errors
            return AssistantMessage(content=error_msg, source="wrapper")
    
    async def _process_websocket_session(self, session_id: str) -> None:
        """Process messages for a WebSocket session"""
        ws = self.websocket_connections.get(session_id)
        session = self.active_websocket_sessions.get(session_id)

        if not session:
            print(f"Session {session_id} not found at start of _process_websocket_session. Aborting.")
            await self._cleanup_session(session_id) # Cleanup ws if it exists
            return
        
        if not ws:
            print(f"WebSocket connection {session_id} not found for active session. Aborting.")
            session.is_active = False # Mark session inactive
            await self._cleanup_session(session_id)
            return
        
        print(f"Starting to process WebSocket session {session_id}. Session active: {session.is_active}")
        try:
            while session.is_active: # Loop based on custom active flag
                try:
                    message_str = await ws.recv()
                    data = json.loads(message_str)
                    
                    msg_type = data.get('type')
                    print(f"Received message type: {msg_type}")
                    
                    if msg_type == "speech_segment":
                        await self._process_websocket_message(data, session_id)
                        
                    elif msg_type == "call_started":
                        stream_sid = data.get('data', {}).get('stream_sid', 'unknown')
                        await self._publish_to_ui(
                            f"Call ({session_id[:8]})",
                            f"Call started - Stream SID: {stream_sid}"
                        )
                        
                    elif msg_type == "call_ended":
                        eligibility = data.get('data', {}).get('eligibility', 'unknown')
                        # Publish eligibility result to UI
                        await self._publish_to_ui(
                            f"Call ({session_id[:8]})",
                            f"Call ended - Eligibility: {eligibility}"
                        )
                        
                        # Add eligibility check result to conversation history
                        if session_id in self.conversation_histories:
                            self.conversation_histories[session_id].append({
                                "role": "system",
                                "content": f"Eligibility check result: {eligibility}"
                            })
                        session.is_active = False # Mark inactive on call_ended
                        
                        # Generate summary before cleanup
                        await self._generate_conversation_summary(session_id)
                        # No longer break here, cleanup is handled by finally and outer loop condition
                        
                except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e_closed:
                    print(f"WebSocket connection closed for session {session_id}: {type(e_closed).__name__} - {e_closed}")
                    session.is_active = False # Crucial: set session inactive
                    # Loop will terminate due to session.is_active being false
                except json.JSONDecodeError:
                    print(f"Invalid JSON received for session {session_id}")
                    continue
                except Exception as e:
                    print(f"Error processing WebSocket message for session {session_id}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    session.is_active = False # Mark inactive on other errors within the loop
                    # Loop will terminate
            
            print(f"Exited WebSocket processing loop for session {session_id}. Session active: {session.is_active}")
                    
        except Exception as e:
            print(f"Outer error in WebSocket session {session_id}: {str(e)}")
            if session: # Check if session still exists
                session.is_active = False # Mark inactive on outer errors
            import traceback
            traceback.print_exc()
        finally:
            print(f"Performing final cleanup for session {session_id}.")
            # Ensure session is marked inactive if not already
            if session and session.is_active:
                 print(f"Warning: Session {session_id} was still marked active in finally block. Forcing inactive.")
                 session.is_active = False
            await self._cleanup_session(session_id)
    
    def _detect_sentence_end(self, text: str) -> bool:
        """Detect if text ends with sentence-ending punctuation."""
        return bool(re.search(r'[,.!?]\s*$', text))

    async def _process_websocket_message(self, ws_message: dict, session_id: str) -> None:
        """Process a single WebSocket message"""
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
                print(f"Transcription error for session {session_id}")
                return
            
            # Parse transcript
            result_text = transcribe_result.result[0].content if transcribe_result.result and hasattr(transcribe_result.result[0], 'content') else ""
            result_data = json.loads(result_text)
            
            if result_data.get("status") != "success":
                print(f"Transcription failed: {result_data.get('message', 'Unknown error')}")
                return
            
            transcript = result_data.get("text", "")
            
            if not transcript:
                return
            
            print(f"🎤 Transcribed: {transcript}")
            await self._publish_to_ui(f"Caller ({session_id[:8]})", transcript)
            
            # Update conversation history
            if session_id not in self.conversation_histories:
                self.conversation_histories[session_id] = []
            
            self.conversation_histories[session_id].append({
                "role": "user",
                "content": transcript
            })
            
            # Build context for AI agent with history
            context = f"""\n**ROLE:** You are Cindy, and AI biller bot, and now you are the caller representing your patients, helping them contacting customer service to **ask about eligibility** for a medical plan. You are initiating the call and requesting assistance. Use the **Response Guide** below to determine the situation and respond appropriately.
                            ---

                            ### **RESPONSE GUIDE**

                            #### **1. Determine the Current Context**

                            * **Eligibility Result Confirmed:** You have received the eligibility outcome.
                            * **Automated System (IVR/Menu):** You're interacting with a phone menu and must use keypad input.
                            * **Human Representative:** You're speaking with a real person who can assist you.

                            ---

                            #### **2. Reply Formats (Based on the Context)**

                            * **Eligibility Result Confirmed**

                            * Eligible → `END_CALL: 1`
                            * Not eligible → `END_CALL: 0`

                            * **Automated System (IVR/Menu)**

                            * Use only DTMF keypad input:

                                * Example (single digit): `DTMF: 1`
                                * Example with pauses (`w` = 0.5s): `DTMF: 1w2w3`
                                * Example DOB entry (MM/DD/YYYY):

                                * 11/01/1992 → `DTMF: 1w1w0w1w1w9w9w2w#`
                                * 08/14/2002 → `DTMF: 0w8w1w4w2w0w0w2w#`

                            * **Human Representative**

                            * Speak naturally and professionally.
                            * Keep responses brief and clear.
                            * Use hyphens in numeric IDs:

                                * e.g., “The policy number is 1-2-3-4-5-6-7-8-9.”

                            ---

                            #### **3. Important Rules**

                            * **If Eligibility Result is Confirmed** → Use ONLY `END_CALL: 0` or `END_CALL: 1` — no other text.
                            * **If speaking to an Automated System** → Use ONLY DTMF input — no natural language.
                            * **If speaking to a Human Representative** → Do NOT use DTMF.
                            * **Do NOT ask follow-up questions in your response.**

                            ---"""
            
            # Add current question to context
            context += f"Current question: {transcript}"
            
            # Get response from AI agent
            ai_result = await self.workbench.call_tool(
                "ask_ai_agent",
                arguments={
                    "question": context
                },
                cancellation_token=CancellationToken()
            )
            
            if ai_result.is_error:
                print(f"AI agent error for session {session_id}")
                return
            
            # Parse initial response to get streaming URL
            response_text = ai_result.result[0].content if ai_result.result and hasattr(ai_result.result[0], 'content') else ""
            try:
                response_data = json.loads(response_text)
                
                if response_data.get("status") == "streaming_url_generated":
                    stream_url = response_data.get("stream_url")
                    stream_id = response_data.get("stream_id")
                    
                    if not stream_url:
                        print(f"No streaming URL provided for session {session_id}")
                        return
                        
                    print(f"Connecting to streaming URL for session {session_id}")
                    accumulated_response = ""  # Track complete response
                    current_sentence = ""  # Track current sentence being built
                    
                    # Connect to streaming endpoint
                    async with httpx.AsyncClient(timeout=None) as stream_client:
                        async with stream_client.stream("GET", stream_url, headers={"Accept": "text/event-stream"}) as sse_response:
                            if sse_response.status_code != 200:
                                print(f"Streaming connection failed (Status {sse_response.status_code})")
                                return
                                
                            event_name = None
                            event_data_lines = []
                            buffer = ""  # Buffer for incomplete lines
                            
                            async for line_bytes in sse_response.aiter_bytes():
                                # Decode and add to buffer
                                buffer += line_bytes.decode('utf-8')
                                
                                # Process complete lines from buffer
                                while '\n' in buffer:
                                    line, buffer = buffer.split('\n', 1)
                                    line = line.strip()
                                    
                                    if line.startswith("event:"):
                                        event_name = line.split("event:", 1)[1].strip()
                                    elif line.startswith("data:"):
                                        data_line = line.split("data:", 1)[1].strip()
                                        event_data_lines.append(data_line)
                                    elif not line and event_name and event_data_lines:  # Empty line = end of event
                                        try:
                                            full_event_data = "".join(event_data_lines)
                                            data_json = json.loads(full_event_data)
                                            
                                            if event_name == "chunk":
                                                chunk_text = data_json.get("text_chunk", "")
                                                accumulated_response += chunk_text
                                                current_sentence += chunk_text
                                                
                                                # Check if we have a complete sentence
                                                if self._detect_sentence_end(current_sentence):
                                                    # Send the complete sentence
                                                    await self._route_response(
                                                        current_sentence.strip(),
                                                        accumulated_response,
                                                        session_id,
                                                        is_partial=True
                                                    )
                                                    current_sentence = ""  # Reset for next sentence
                                                
                                            elif event_name == "error":
                                                print(f"Streaming error: {data_json.get('error', 'Unknown error')}")
                                                break
                                                
                                            elif event_name == "completed":
                                                # Send any remaining text as final sentence
                                                if current_sentence.strip():
                                                    await self._route_response(
                                                        current_sentence.strip(),
                                                        accumulated_response,
                                                        session_id,
                                                        is_partial=True
                                                    )
                                                
                                                # Send final complete response
                                                await self._route_response(
                                                    accumulated_response,
                                                    accumulated_response,
                                                    session_id,
                                                    is_partial=False
                                                )
                                                
                                                # Update conversation history with complete response
                                                self.conversation_histories[session_id].append({
                                                    "role": "assistant",
                                                    "content": accumulated_response
                                                })
                                                
                                                # Send to UI
                                                await self._publish_to_ui(
                                                    f"Agent ({session_id[:8]})",
                                                    accumulated_response
                                                )
                                                break
                                                
                                        except json.JSONDecodeError as e:
                                            print(f"Error parsing streaming event: {e}")
                                        
                                        # Reset for next event
                                        event_name = None
                                        event_data_lines = []
                                        
                else:
                    print(f"Unexpected response status: {response_data.get('status')}")
                    return
                    
            except json.JSONDecodeError as e:
                print(f"Error parsing AI response: {e}")
                return
            except Exception as e:
                print(f"Error in streaming process: {e}")
                return
                
        except Exception as e:
            print(f"Error processing WebSocket message: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # TODO: The accumulated_response part could be removed in the future, here it is to make the MCP tool streaming reponse work
    async def _route_response(self, response: str, accumulated_response: str, session_id: str, is_partial: bool = False) -> None:
        """Route AI response to appropriate destination"""
        ws = self.websocket_connections.get(session_id)
        session = self.active_websocket_sessions.get(session_id)

        if not session:
            print(f"Cannot route response: Session {session_id} not found.")
            return

        if not session.is_active:
            print(f"Cannot route response: Session {session_id} is inactive.")
            return
            
        if not ws:
            print(f"Cannot route response: WebSocket for session {session_id} not found though session is active.")
            session.is_active = False # Mark session inactive as ws is missing
            await self._cleanup_session(session_id)
            return
                
        try:
            # print(f"Routing {'partial' if is_partial else 'complete'} AI response to WebSocket for session {session_id}")
            
            message_type = "partial_response" if is_partial else "text_response"
            await ws.send(json.dumps({
                "type": message_type,
                "data": {
                    "text": response,
                    "accumulated_text": accumulated_response
                }
            }))
            
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e_closed:
            print(f"WebSocket connection closed while sending for session {session_id}: {type(e_closed).__name__} - {e_closed}")
            session.is_active = False # Mark session inactive
            # Cleanup will be handled by the main processing loop's finally block or next iteration
        except Exception as e:
            print(f"Error routing response for session {session_id}: {str(e)}")
            session.is_active = False # Mark session inactive
            # Cleanup will be handled by the main processing loop's finally block or next iteration
    
    async def _generate_conversation_summary(self, session_id: str) -> None:
        """Generate summary of conversation"""
        if session_id not in self.conversation_histories:
            await self._publish_to_ui(
                f"Summary ({session_id[:8]})",
                "No conversation data available"
            )
            return
        
        conversation = self.conversation_histories[session_id]
        
        # Create messages for the model
        messages = [
            self._system_message,
            LLMUserMessage(
                content=f"Please summarize this conversation:\n{json.dumps(conversation, indent=2)}",
                source="user"
            )
        ]
        
        try:
            # Get summary directly from model
            print(f"Generating summary for session {session_id}")
            completion = await self.model_client.create(
                messages=messages,
                cancellation_token=CancellationToken()
            )
            
            # Extract content
            assert isinstance(completion.content, str)
            summary = completion.content
            print(f"Summary generated: {summary}")
            
            if summary:
                await self._publish_to_ui(
                    f"Call Summary ({session_id[:8]})",
                    f"📝 **CALL SUMMARY**\n\n{summary}"
                )
                
                # Update history with summary
                for entry in self.agent_history:
                    if entry["type"] == "websocket_conversation" and entry["session_id"] == session_id:
                        entry["response"] = summary
                        break
            else:
                await self._publish_to_ui(
                    f"Call Summary ({session_id[:8]})",
                    "Unable to generate summary"
                )
                
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            import traceback
            traceback.print_exc()
            await self._publish_to_ui(
                f"Call Summary ({session_id[:8]})",
                f"Error generating summary: {str(e)}"
            )
    
    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up session resources"""
        print(f"Initiating cleanup for session {session_id}")
        ws = self.websocket_connections.get(session_id)
        if ws:
            try:
                print(f"Attempting to close WebSocket for session {session_id}")
                await ws.close()
                print(f"WebSocket closed for session {session_id}")
            except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK):
                print(f"WebSocket already closed for session {session_id} during cleanup.")
            except AttributeError as ae:
                 print(f"AttributeError during ws.close() for session {session_id} (type: {type(ws)}): {ae}")
            except Exception as e_close:
                 print(f"Exception during ws.close() for session {session_id} (type: {type(ws)}): {e_close}")
            finally:
                 # Remove from dict after attempting close
                if session_id in self.websocket_connections:
                    del self.websocket_connections[session_id]
        else:
            print(f"No WebSocket connection found in dict for session {session_id} during cleanup.")
        
        active_session = self.active_websocket_sessions.get(session_id)
        if active_session:
            active_session.is_active = False # Ensure marked as inactive
            if session_id in self.active_websocket_sessions: # Re-check before del
                 del self.active_websocket_sessions[session_id]
            print(f"Active session entry removed for {session_id}")
        else:
            print(f"No active_session entry found for {session_id} during cleanup.")
            
        if session_id in self.conversation_histories:
            del self.conversation_histories[session_id]
            print(f"Conversation history removed for {session_id}")
            
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
            print(f"Session context removed for {session_id}")
            
        print(f"Session {session_id} cleanup process completed.")
    
    async def _publish_to_ui(self, source: str, content: str, is_streaming: bool = False) -> None:
        """Helper to publish messages to UI"""
        message_id = str(uuid.uuid4())
        
        if is_streaming:
            # For streaming, send the entire sentence as one chunk
            chunk = MessageChunk(
                message_id=message_id,
                text=content + " ",  # Add space after sentence
                author=source,
                finished=False
            )
            await self.publish_message(
                chunk,
                DefaultTopicId(type=self._ui_config.topic_type)
            )
        else:
            # For non-streaming, split into tokens and stream with delay
            tokens = content.split()
            for token in tokens:
                chunk = MessageChunk(
                    message_id=message_id,
                    text=token + " ",
                    author=source,
                    finished=False
                )
                await self.publish_message(
                    chunk,
                    DefaultTopicId(type=self._ui_config.topic_type)
                )
                await asyncio.sleep(0.05)  # Small delay for streaming effect
        
        # Send finished marker
        await self.publish_message(
            MessageChunk(
                message_id=message_id,
                text="",
                author=source,
                finished=True
            ),
            DefaultTopicId(type=self._ui_config.topic_type)
        ) 

    async def close(self) -> None:
        """Close the agent and its resources."""
        await super().close()
        await self._model_client.close() 