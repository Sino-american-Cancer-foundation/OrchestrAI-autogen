import asyncio
import logging
import warnings

from _agents import DomainAgent, input_adapter, output_adapter
from _types import AppConfig, UserMessage, AssistantMessage, MessageChunk
from _utils import get_serializers, load_config, set_all_log_levels
from autogen_core import ClosureAgent, TypeSubscription
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.WARNING)

async def main(config: AppConfig):
    """Start the Domain Agent runtime with adapters."""
    # Initialize runtime
    domain_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    domain_runtime.add_message_serializer(
        get_serializers([UserMessage, AssistantMessage, MessageChunk])
    )
    
    # Start runtime
    Console().print(Markdown("Starting **`Domain Agent with Adapters`**"))
    await domain_runtime.start()
    
    # Initialize model client
    model_client = OpenAIChatCompletionClient(**config.client_config)
    
    # Register Domain Agent
    domain_agent_type = await DomainAgent.register(
        domain_runtime,
        "domain_agent",
        lambda: DomainAgent(
            description=config.domain_agent.description,
            system_message=config.domain_agent.system_message,
            model_client=model_client,
            ui_config=config.ui_agent,
            knowledge_file="prompts/domain_knowledge.txt",
        ),
    )
    
    # Set up domain agent subscription for direct messages
    await domain_runtime.add_subscription(
        TypeSubscription(topic_type=config.domain_agent.topic_type, agent_type=domain_agent_type.type)
    )
    
    # Register Input Adapter
    await ClosureAgent.register_closure(
        domain_runtime,
        "input_adapter",
        input_adapter,
        subscriptions=lambda: [TypeSubscription(topic_type="domain_input", agent_type="input_adapter")],
    )

    # Register Output Adapter
    # Subscribe to ALL messages from the domain agent topic type
    await ClosureAgent.register_closure(
        domain_runtime,
        "output_adapter",
        output_adapter,
        subscriptions=lambda: [TypeSubscription(topic_type=config.domain_agent.topic_type, agent_type="output_adapter")],
    )


    # Also add a debug subscription to see all messages
    await domain_runtime.add_subscription(
        TypeSubscription(topic_type=config.ui_agent.topic_type, agent_type="output_adapter")
    )
    
    # Wait until stopped
    await domain_runtime.stop_when_signal()
    await model_client.close()

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    asyncio.run(main(load_config()))