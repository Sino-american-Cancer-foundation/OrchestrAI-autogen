import asyncio
import logging
import warnings

from _agents import McpSseGroupChatAgent
from _types import AppConfig, GroupChatMessage, MessageChunk, RequestToSpeak
from _utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from rich.console import Console
from rich.markdown import Markdown


async def main(config: AppConfig):
    set_all_log_levels(logging.ERROR)
    image_analysis_agent_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    image_analysis_agent_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk]))
    await asyncio.sleep(2)
    Console().print(Markdown("Starting **`Image Analysis Agent`**"))
    await image_analysis_agent_runtime.start()
    
    model_client = OpenAIChatCompletionClient(**config.client_config)
    
    image_analysis_agent_type = await McpSseGroupChatAgent.register(
        image_analysis_agent_runtime,
        config.image_analysis_agent.topic_type,
        lambda: McpSseGroupChatAgent(
            description=config.image_analysis_agent.description,
            group_chat_topic_type=config.group_chat_manager.topic_type,
            system_message=config.image_analysis_agent.system_message,
            model_client=model_client,
            ui_config=config.ui_agent,
            sse_url=config.image_analysis_mcp.sse_url,
            sse_headers=config.image_analysis_mcp.sse_headers,
            sse_timeout=config.image_analysis_mcp.sse_timeout,
        ),
    )
    
    await image_analysis_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.image_analysis_agent.topic_type, agent_type=image_analysis_agent_type.type)
    )
    await image_analysis_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.group_chat_manager.topic_type, agent_type=image_analysis_agent_type.type)
    )

    await image_analysis_agent_runtime.stop_when_signal()
    await model_client.close()


if __name__ == "__main__":
    set_all_log_levels(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, message="Resolved model mismatch.*")
    asyncio.run(main(load_config()))