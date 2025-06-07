import asyncio
import logging

try:
    from ._agents import OrchestratorAgent
    from ._types import GroupChatMessage, RequestToSpeak, MessageChunk, AppConfig
    from ._utils import load_config, set_all_log_levels, get_serializers
except ImportError:
    from _agents import OrchestratorAgent
    from _types import GroupChatMessage, RequestToSpeak, MessageChunk, AppConfig
    from _utils import load_config, set_all_log_levels, get_serializers

from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.models.openai import OpenAIChatCompletionClient
from rich.console import Console
from rich.markdown import Markdown

# Set log level
set_all_log_levels(logging.ERROR)

async def main(config: AppConfig):
    """Start the orchestrator agent runtime following GroupChatManager pattern."""
    # Initialize runtime
    orchestrator_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    orchestrator_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk]))
    
    await asyncio.sleep(1)
    Console().print(Markdown("Starting **`Orchestrator Agent`**"))
    await orchestrator_runtime.start()
    
    # Create model client
    model_client = OpenAIChatCompletionClient(**config.orchestrator.model_client_config)
    
    # Register orchestrator agent following GroupChatManager pattern
    orchestrator_agent_type = await OrchestratorAgent.register(
        orchestrator_runtime,
        "orchestrator_agent",
        lambda: OrchestratorAgent(
            model_client=model_client,
            participant_topic_types=[config.proxy_agent.topic_type, config.medical_data_agent.topic_type],
            participant_descriptions=[config.proxy_agent.description, config.medical_data_agent.description],
            ui_config=config.ui_agent,
            max_rounds=config.orchestrator.max_rounds,
        ),
    )
    
    # Set up subscription to group chat topic only
    await orchestrator_runtime.add_subscription(
        TypeSubscription(topic_type=config.orchestrator.topic_type, agent_type=orchestrator_agent_type.type)
    )
    
    # Wait for system to be ready
    await asyncio.sleep(2)
    
    Console().print(Markdown("**`Orchestrator Agent`** is ready and managing conversations"))
    
    # Wait until stopped
    await orchestrator_runtime.stop_when_signal()
    await model_client.close()
    Console().print("Orchestrator left the chat!")

if __name__ == "__main__":
    config = load_config()
    asyncio.run(main(config)) 