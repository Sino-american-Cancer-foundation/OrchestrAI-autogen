import asyncio
import json
import uuid
import websockets
from typing import Dict, List, Optional, Any

from autogen_core import (
    AgentId, DefaultTopicId, MessageContext, RoutedAgent, 
    message_handler, CancellationToken
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
        ui_config: UIAgentConfig
    ) -> None:
        super().__init__(description=description)
        self.workbench = workbench
        self._ui_config = ui_config
        
        # State management
        self.active_websocket_sessions: Dict[str, WebSocketSession] = {}
        self.websocket_connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.conversation_histories: Dict[str, List[Dict[str, str]]] = {}
        self.session_contexts: Dict[str, str] = {}
    
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
            # Send to UI that we're processing
            await self._publish_to_ui(
                source="WrapperAgent",
                content=f"Processing your request..."
            )
            
            # Call AI agent MCP tool
            result = await self.workbench.call_tool(
                "ask_ai_agent",
                arguments={
                    "question": message.content
                },
                cancellation_token=ctx.cancellation_token
            )
            
            if result.is_error:
                error_msg = "Failed to get response from AI agent"
                await self._publish_to_ui("WrapperAgent", f"Error: {error_msg}")
                return AssistantMessage(content=error_msg, source="wrapper")
            
            # Extract response from the result
            response_text = result.result[0].content if result.result and hasattr(result.result[0], 'content') else ""
            
            # Parse the JSON response
            try:
                response_data = json.loads(response_text)
                if response_data.get("status") == "success":
                    ai_response = response_data.get("response", "No response from AI")
                    model_used = response_data.get("model", "unknown")
                    print(f"AI response using {model_used}: {ai_response[:100]}...")
                else:
                    ai_response = f"Error: {response_data.get('message', 'Unknown error')}"
            except json.JSONDecodeError:
                # If not JSON, use the raw text
                ai_response = response_text
            
            # Send to UI
            await self._publish_to_ui("AI Agent", ai_response)
            
            return AssistantMessage(content=ai_response, source="wrapper")
            
        except Exception as e:
            error_msg = f"Error in single response flow: {str(e)}"
            print(error_msg)
            await self._publish_to_ui("WrapperAgent", error_msg)
            return AssistantMessage(content=error_msg, source="wrapper")
    
    async def _handle_websocket_flow(self, message: UserMessage, ctx: MessageContext) -> AssistantMessage:
        """Handle WebSocket conversation flow"""
        session_id = str(uuid.uuid4())
        
        try:
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
                original_request=message.content
            )
            self.active_websocket_sessions[session_id] = session
            self.session_contexts[session_id] = message.content
            
            # Connect to WebSocket
            ws_connection = await websockets.connect(websocket_url)
            self.websocket_connections[session_id] = ws_connection
            
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
            
        except Exception as e:
            error_msg = f"Error in WebSocket flow: {str(e)}"
            print(error_msg)
            await self._publish_to_ui("WrapperAgent", error_msg)
            return AssistantMessage(content=error_msg, source="wrapper")
    
    async def _process_websocket_session(self, session_id: str) -> None:
        """Process messages for a WebSocket session"""
        if session_id not in self.websocket_connections:
            return
        
        ws = self.websocket_connections[session_id]
        session = self.active_websocket_sessions[session_id]
        
        try:
            while session.is_active:
                # Receive message
                try:
                    message = await ws.recv()
                    data = json.loads(message)
                except websockets.exceptions.ConnectionClosed:
                    print(f"WebSocket closed for session {session_id}")
                    break
                
                msg_type = data.get('type')
                
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
                    await self._publish_to_ui(
                        f"Call ({session_id[:8]})",
                        f"Call ended - Eligibility: {eligibility}"
                    )
                    session.is_active = False
                    
                    # Generate summary
                    await self._generate_conversation_summary(session_id)
                    
        except Exception as e:
            print(f"Error in WebSocket session {session_id}: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            await self._cleanup_session(session_id)
    
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
            
            # Build context for AI agent
            context = f"Context: You are handling a phone call about: {self.session_contexts.get(session_id, 'healthcare eligibility verification')}\n\n"
            if self.conversation_histories[session_id]:
                context += "Previous conversation:\n"
                for turn in self.conversation_histories[session_id][-5:]:  # Last 5 turns
                    context += f"{turn['role']}: {turn['content']}\n"
                context += "\n"
            context += f"Caller just said: {transcript}\n"
            context += "Please provide a helpful response:"
            
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
            
            # Parse response
            response_text = ai_result.result[0].content if ai_result.result and hasattr(ai_result.result[0], 'content') else ""
            response_data = json.loads(response_text)
            
            if response_data.get("status") != "success":
                print(f"AI agent failed: {response_data.get('message', 'Unknown error')}")
                return
            
            ai_response = response_data.get("response", "I understand. How can I help you further?")
            
            print(f"🤖 Response: {ai_response[:50]}...")
            
            # Update conversation history
            self.conversation_histories[session_id].append({
                "role": "assistant",
                "content": ai_response
            })
            
            # Send to UI
            await self._publish_to_ui(f"Agent ({session_id[:8]})", ai_response)
            
            # Send back to WebSocket
            await self._route_response(ai_response, session_id)
            
        except Exception as e:
            print(f"Error processing WebSocket message: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def _route_response(self, response: str, context_id: str) -> None:
        """Route response to appropriate destination"""
        if context_id in self.websocket_connections:
            # Send to WebSocket
            ws = self.websocket_connections[context_id]
            await ws.send(json.dumps({
                "type": "text_response",
                "data": {
                    "text": response
                }
            }))
            print(f"Sent response to WebSocket for session {context_id}")
        else:
            # If no WebSocket, send to UI (already done in calling function)
            pass
    
    async def _generate_conversation_summary(self, session_id: str) -> None:
        """Generate summary of conversation"""
        if session_id not in self.conversation_histories:
            await self._publish_to_ui(
                f"Summary ({session_id[:8]})",
                "No conversation data available"
            )
            return
        
        conversation = self.conversation_histories[session_id]
        summary_prompt = f"Please provide a concise summary of this phone call conversation, including key points and outcomes:\n\n{json.dumps(conversation, indent=2)}"
        
        try:
            summary_result = await self.workbench.call_tool(
                "ask_ai_agent",
                arguments={
                    "question": summary_prompt
                },
                cancellation_token=CancellationToken()
            )
            
            if not summary_result.is_error:
                result_text = summary_result.result[0].content if summary_result.result and hasattr(summary_result.result[0], 'content') else ""
                result_data = json.loads(result_text)
                
                if result_data.get("status") == "success":
                    summary = result_data.get("response", "Unable to generate summary")
                    
                    await self._publish_to_ui(
                        f"Call Summary ({session_id[:8]})",
                        f"📝 **CALL SUMMARY**\n\n{summary}"
                    )
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
    
    async def _cleanup_session(self, session_id: str) -> None:
        """Clean up session resources"""
        # Close WebSocket
        if session_id in self.websocket_connections:
            ws = self.websocket_connections[session_id]
            await ws.close()
            del self.websocket_connections[session_id]
        
        # Remove session data
        if session_id in self.active_websocket_sessions:
            del self.active_websocket_sessions[session_id]
        
        if session_id in self.conversation_histories:
            del self.conversation_histories[session_id]
        
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
    
    async def _publish_to_ui(self, source: str, content: str) -> None:
        """Helper to publish messages to UI"""
        message_id = str(uuid.uuid4())
        
        # Stream the message
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