import asyncio
import logging
import warnings

import chainlit as cl
from samples.wrapper_agent_example._ui_agent import UIAgent, MessageChunk
from samples.wrapper_agent_example._types import AppConfig, UserMessage, AssistantMessage
from samples.wrapper_agent_example._utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription, DefaultTopicId
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

# Global runtime reference
ui_runtime = None

async def main(config: AppConfig):
    """Start the UI Agent runtime."""
    global ui_runtime
    
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
    asyncio.create_task(main(config))
    
    # Give some time for the runtime to start
    await asyncio.sleep(2)
    
    await cl.Message(
        content="Welcome! I can help you with healthcare insurance questions or initiate calls to verify eligibility.\n\n"
                "Try asking me:\n"
                "- Tell me about health insurance\n"
                "- Call to check eligibility for patient John Doe with Blue Cross Blue Shield"
    ).send()

@cl.on_message
async def on_message(message: str):
    """Handle user messages from chainlit UI."""
    global ui_runtime
    
    if ui_runtime is None:
        await cl.Message(content="System is still initializing, please wait...").send()
        return
    
    config = load_config()
    
    # Send message to wrapper agent
    await ui_runtime.publish_message(
        UserMessage(content=message, source="User"),
        DefaultTopicId(type=config.wrapper_agent.topic_type),
    ) 