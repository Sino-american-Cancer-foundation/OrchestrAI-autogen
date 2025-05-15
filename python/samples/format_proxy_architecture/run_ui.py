import asyncio
import logging
import warnings

import chainlit as cl  # This requires installing chainlit with pip
from _agents import UIAgent, MessageChunk
from _types import AppConfig, UserMessage, AssistantMessage
from _utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from chainlit import Message
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.WARNING)

# Global dictionary to keep track of message chunks
message_chunks = {}

async def send_cl_stream(msg: MessageChunk) -> None:
    """Send message chunks to chainlit UI."""
    if msg.message_id not in message_chunks:
        message_chunks[msg.message_id] = Message(content="", author=msg.author)

    if not msg.finished:
        await message_chunks[msg.message_id].stream_token(msg.text)
    else:
        await message_chunks[msg.message_id].stream_token(msg.text)
        await message_chunks[msg.message_id].update()
        await asyncio.sleep(1)  # Short delay before sending
        cl_msg = message_chunks[msg.message_id]
        await cl_msg.send()

async def main(config: AppConfig):
    """Start the UI Agent runtime."""
    # Initialize runtime
    ui_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    ui_runtime.add_message_serializer(
        get_serializers([UserMessage, AssistantMessage, MessageChunk])
    )
    
    # Start runtime
    Console().print(Markdown("Starting **`UI Agent`**"))
    await ui_runtime.start()
    
    # Register UI Agent
    ui_agent_type = await UIAgent.register(
        ui_runtime,
        "ui_agent",
        lambda: UIAgent(on_message_chunk_func=send_cl_stream),
    )
    
    # Set up subscription
    await ui_runtime.add_subscription(
        TypeSubscription(topic_type=config.ui_agent.topic_type, agent_type=ui_agent_type.type)
    )
    
    # Wait until stopped
    await ui_runtime.stop_when_signal()

@cl.on_chat_start
async def start_chat():
    """Start the UI Agent when a chat session begins."""
    set_all_log_levels(logging.WARNING)
    warnings.filterwarnings("ignore", category=UserWarning)
    
    config = load_config()
    await main(config)

@cl.on_message
async def on_message(message: str):
    """Handle user messages from chainlit UI."""
    # In a full implementation, this would send messages to the orchestrator
    # For now, just acknowledge receipt
    await cl.Message(content=f"Received: {message} (Not implemented in this demo)").send()
