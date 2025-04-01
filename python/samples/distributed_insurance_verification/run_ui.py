import asyncio
import logging
import warnings

import chainlit as cl
from _agents import MessageChunk, UIAgent
from _types import AppConfig, GroupChatMessage, RequestToSpeak
from _utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from chainlit import Message
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.ERROR)

message_chunks: dict[str, Message] = {}


async def send_cl_stream(msg: MessageChunk) -> None:
    if msg.message_id not in message_chunks:
        message_chunks[msg.message_id] = Message(content="", author=msg.author)

    if not msg.finished:
        await message_chunks[msg.message_id].stream_token(msg.text)
    else:
        await message_chunks[msg.message_id].stream_token(msg.text)
        await message_chunks[msg.message_id].update()
        await asyncio.sleep(3)
        cl_msg = message_chunks[msg.message_id]
        await cl_msg.send()


async def main(config: AppConfig):
    set_all_log_levels(logging.ERROR)
    ui_agent_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)

    ui_agent_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk]))

    Console().print(Markdown("Starting **`UI Agent`**"))
    await ui_agent_runtime.start()
    set_all_log_levels(logging.ERROR)

    ui_agent_type = await UIAgent.register(
        ui_agent_runtime,
        "ui_agent",
        lambda: UIAgent(
            on_message_chunk_func=send_cl_stream,
        ),
    )

    await ui_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.ui_agent.topic_type, agent_type=ui_agent_type.type)
    )

    await ui_agent_runtime.stop_when_signal()
    Console().print("UI Agent left the chat!")


@cl.on_chat_start
async def start_chat():
    set_all_log_levels(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, message="Resolved model mismatch.*")
    asyncio.run(main(load_config()))