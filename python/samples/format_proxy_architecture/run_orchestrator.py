import asyncio
import logging
import warnings

from _agents import GroupChatManager
from _types import AppConfig, CallRequest, UserMessage, AssistantMessage, MessageChunk
from _utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription, DefaultTopicId
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.WARNING)

async def main(config: AppConfig):
    """Start the Orchestrator (GroupChatManager) runtime."""
    # Initialize runtime
    orchestrator_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    orchestrator_runtime.add_message_serializer(
        get_serializers([CallRequest, UserMessage, AssistantMessage, MessageChunk])
    )
    
    # Start runtime
    Console().print(Markdown("Starting **`Orchestrator (GroupChatManager)`**"))
    await orchestrator_runtime.start()
    
    # Initialize model client
    model_client = OpenAIChatCompletionClient(**config.client_config)
    
    # Register GroupChatManager
    orchestrator_agent_type = await GroupChatManager.register(
        orchestrator_runtime,
        "group_chat_manager",
        lambda: GroupChatManager(
            description=config.orchestrator.description,
            model_client=model_client,
            ui_config=config.ui_agent,
        ),
    )
    
    # Set up subscriptions
    await orchestrator_runtime.add_subscription(
        TypeSubscription(topic_type=config.orchestrator.topic_type, agent_type=orchestrator_agent_type.type)
    )
    await orchestrator_runtime.add_subscription(
        TypeSubscription(topic_type=config.ui_agent.topic_type, agent_type=orchestrator_agent_type.type)
    )
    
    # Send a test message to start the conversation (optional)
    await asyncio.sleep(5)  # Give time for other runtimes to start
    
    Console().print("Sending initial test request to GroupChatManager...")
    await orchestrator_runtime.publish_message(
        UserMessage(content="Hi make a phone call for me.", source="User"),
        DefaultTopicId(type=config.orchestrator.topic_type),
    )
    
    # Wait until stopped
    await orchestrator_runtime.stop_when_signal()
    await model_client.close()

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    asyncio.run(main(load_config()))