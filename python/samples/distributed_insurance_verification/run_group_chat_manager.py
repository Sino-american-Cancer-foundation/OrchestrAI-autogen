import asyncio
import logging
import warnings

from _agents import GroupChatManager, publish_message_to_ui, publish_message_to_ui_and_backend
from _types import AppConfig, GroupChatMessage, MessageChunk, RequestToSpeak
from _utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.ERROR)


async def main(config: AppConfig):
    set_all_log_levels(logging.ERROR)
    group_chat_manager_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)

    group_chat_manager_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk]))
    await asyncio.sleep(1)
    Console().print(Markdown("Starting **`Group Chat Manager`**"))
    await group_chat_manager_runtime.start()
    set_all_log_levels(logging.ERROR)

    model_client = OpenAIChatCompletionClient(**config.client_config)

    participant_topic_types = [
        config.web_navigation_agent.topic_type,
        config.image_analysis_agent.topic_type,
        config.healthcare_task_agent.topic_type
    ]
    
    participant_descriptions = [
        config.web_navigation_agent.description,
        config.image_analysis_agent.description,
        config.healthcare_task_agent.description
    ]

    group_chat_manager_type = await GroupChatManager.register(
        group_chat_manager_runtime,
        "group_chat_manager",
        lambda: GroupChatManager(
            model_client=model_client,
            participant_topic_types=participant_topic_types,
            participant_descriptions=participant_descriptions,
            max_rounds=config.group_chat_manager.max_rounds,
            ui_config=config.ui_agent,
        ),
    )

    await group_chat_manager_runtime.add_subscription(
        TypeSubscription(topic_type=config.group_chat_manager.topic_type, agent_type=group_chat_manager_type.type)
    )

    await asyncio.sleep(5)

    await publish_message_to_ui(
        runtime=group_chat_manager_runtime,
        source="System",
        user_message="[ **Insurance Verification Team initialized and ready for task** ]",
        ui_config=config.ui_agent,
    )
    await asyncio.sleep(3)

    user_message: str = """
    Do your job with the following information:
    1. Portal website url: https://www.brmsprovidergateway.com/provideronline/search.aspx
    2. Member ID (username): E01257465
    3. Date of Birth (password): 08/03/1988
    4. Patient Name: Liza Silina
    5. Service Date: 2024-01-15
    """
    Console().print(f"Simulating User input in group chat topic:\n\t'{user_message}'")

    await publish_message_to_ui_and_backend(
        runtime=group_chat_manager_runtime,
        source="User",
        user_message=user_message,
        ui_config=config.ui_agent,
        group_chat_topic_type=config.group_chat_manager.topic_type,
    )

    await group_chat_manager_runtime.stop_when_signal()
    await model_client.close()
    Console().print("Manager left the chat!")


if __name__ == "__main__":
    set_all_log_levels(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, message="Resolved model mismatch.*")
    asyncio.run(main(load_config()))