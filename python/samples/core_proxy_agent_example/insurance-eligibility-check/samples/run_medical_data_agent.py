import asyncio
import logging

from employees.medical_data_agent import MedicalDataAgent
from facilities.core import (
    GroupChatMessage, RequestToSpeak, MessageChunk, ConversationFinished, AppConfig,
    load_config, set_all_log_levels, get_serializers
)
from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.models.openai import OpenAIChatCompletionClient
from rich.console import Console
from rich.markdown import Markdown

# Set log level
set_all_log_levels(logging.ERROR)

async def main(config: AppConfig):
    """Start the medical data agent runtime following BaseGroupChatAgent pattern."""
    # Initialize runtime
    medical_data_agent_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    medical_data_agent_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk, ConversationFinished]))
    
    await asyncio.sleep(4)  # Stagger startup
    Console().print(Markdown("Starting **`Medical Data Agent`**"))
    await medical_data_agent_runtime.start()
    
    # Create model client
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=config.orchestrator.model_client_config["api_key"]  # Reuse API key from config
    )
    
    # Register medical data agent
    medical_data_agent_type = await MedicalDataAgent.register(
        medical_data_agent_runtime,
        config.medical_data_agent.topic_type,
        lambda: MedicalDataAgent(
            description=config.medical_data_agent.description,
            group_chat_topic_type=config.orchestrator.topic_type,
            model_client=model_client,
            system_message=config.medical_data_agent.system_message,
            ui_config=config.ui_agent,
        ),
    )
    
    # Set up dual subscriptions following BaseGroupChatAgent pattern
    # 1. Subscribe to own topic for RequestToSpeak messages
    await medical_data_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.medical_data_agent.topic_type, agent_type=medical_data_agent_type.type)
    )
    # 2. Subscribe to group chat topic for message history
    await medical_data_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.orchestrator.topic_type, agent_type=medical_data_agent_type.type)
    )
    
    Console().print(Markdown("**`Medical Data Agent`** is ready and listening for messages"))
    
    # Wait until stopped
    await medical_data_agent_runtime.stop_when_signal()
    await model_client.close()
    Console().print("Medical Data Agent left the chat!")

if __name__ == "__main__":
    config = load_config()
    asyncio.run(main(config)) 