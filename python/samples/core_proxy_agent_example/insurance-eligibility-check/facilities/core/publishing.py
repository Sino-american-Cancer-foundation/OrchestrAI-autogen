import asyncio
import random
from uuid import uuid4

from autogen_core import RoutedAgent, DefaultTopicId
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_core.models import UserMessage

from .types import MessageChunk, UIAgentConfig, GroupChatMessage


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