import asyncio
import logging
from typing import Any, Dict, List, Union, Optional

import chainlit as cl

try:
    from ._agents import UIAgent
    from ._types import GroupChatMessage, MessageChunk, ConversationFinished, AppConfig
    from ._utils import load_config, set_all_log_levels, get_serializers
except ImportError:
    from _agents import UIAgent
    from _types import GroupChatMessage, MessageChunk, ConversationFinished, AppConfig
    from _utils import load_config, set_all_log_levels, get_serializers

from autogen_core import DefaultTopicId, TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_core.models import UserMessage
from rich.console import Console

# Load configuration
config = load_config()
set_all_log_levels(logging.ERROR)

# Global runtime instance
runtime: Optional[GrpcWorkerAgentRuntime] = None

# Track streaming messages by message_id
message_chunks: dict[str, cl.Message] = {}

async def handle_message_chunk(message_chunk: MessageChunk) -> None:
    """Handle message chunks from agents using proper Chainlit streaming."""
    # Initialize message if it's the first chunk for this message_id
    if message_chunk.message_id not in message_chunks:
        # Prepend agent name to the message content instead of using author field
        agent_prefix = f"**{message_chunk.author}**: " if message_chunk.author != "System" else ""
        message_chunks[message_chunk.message_id] = cl.Message(content=agent_prefix)

    if not message_chunk.finished:
        # Stream the token to the existing message
        await message_chunks[message_chunk.message_id].stream_token(message_chunk.text)
    else:
        # Stream final token and finalize the message
        await message_chunks[message_chunk.message_id].stream_token(message_chunk.text)
        await message_chunks[message_chunk.message_id].update()
        await asyncio.sleep(0.1)  # Small delay before sending final message
        await message_chunks[message_chunk.message_id].send()
        
        # Clean up the completed message
        del message_chunks[message_chunk.message_id]

@cl.on_chat_start
async def start_chat():
    """Initialize the chat session and set up UI agent."""
    global runtime
    
    # Connect to gRPC host
    runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    runtime.add_message_serializer(get_serializers([GroupChatMessage, MessageChunk, ConversationFinished]))
    
    Console().print("Starting **`UI Agent`**")
    await runtime.start()
    
    # Register UI agent
    ui_agent_type = await UIAgent.register(
        runtime,
        config.ui_agent.topic_type,
        lambda: UIAgent(handle_message_chunk),
    )
    
    # Subscribe to UI events topic
    await runtime.add_subscription(
        TypeSubscription(topic_type=config.ui_agent.topic_type, agent_type=ui_agent_type.type)
    )
    
    Console().print("✅ UI Agent connected and ready")
    
    await cl.Message(
        content="**Assistant System** is ready! 🏥\n\nYou can:\n- Ask about patient information\n- Request phone calls to external participants\n- Get medical data and reports\n\nTry: *I need to reach John Smith at 555-0123 about his recent diabetes follow-up visit.*",
        author="System"
    ).send()

@cl.on_message
async def handle_message(message: cl.Message):
    """Handle incoming user messages and publish to group chat."""
    global runtime
    
    if runtime is None:
        await cl.Message(content="Error: Runtime not initialized", author="System").send()
        return
    
    try:
        # Create GroupChatMessage with proper LLMMessage body
        group_chat_msg = GroupChatMessage(
            body=UserMessage(content=message.content, source="User")
        )
        
        # Publish to group chat topic (orchestrator topic)
        await runtime.publish_message(group_chat_msg, DefaultTopicId(type=config.orchestrator.topic_type))
        
        Console().print(f"User message published to group chat: {message.content}")
        
    except Exception as e:
        Console().print(f"❌ Error sending message: {str(e)}")
        await cl.Message(
            content=f"Error processing message: {str(e)}",
            author="System"
        ).send()

@cl.on_chat_end
async def end_chat():
    """Clean up when chat ends."""
    global runtime
    
    if runtime:
        await runtime.stop()
        Console().print("🔌 UI Agent disconnected")

if __name__ == "__main__":
    # Chainlit will handle the rest 
    pass 