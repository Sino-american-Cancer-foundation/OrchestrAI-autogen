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
    web_navigation_agent_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    web_navigation_agent_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk]))
    await asyncio.sleep(2)
    Console().print(Markdown("Starting **`Web Navigation Agent`**"))
    await web_navigation_agent_runtime.start()
    
    model_client = OpenAIChatCompletionClient(**config.client_config)
    
    web_navigation_agent_type = await McpSseGroupChatAgent.register(
        web_navigation_agent_runtime,
        config.web_navigation_agent.topic_type,
        lambda: McpSseGroupChatAgent(
            description=config.web_navigation_agent.description,
            group_chat_topic_type=config.group_chat_manager.topic_type,
            system_message=config.web_navigation_agent.system_message,
            model_client=model_client,
            ui_config=config.ui_agent,
            sse_url=config.web_navigation_mcp.sse_url,
            sse_headers=config.web_navigation_mcp.sse_headers,
            sse_timeout=config.web_navigation_mcp.sse_timeout,
        ),
    )
    
    await web_navigation_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.web_navigation_agent.topic_type, agent_type=web_navigation_agent_type.type)
    )
    await web_navigation_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.group_chat_manager.topic_type, agent_type=web_navigation_agent_type.type)
    )

    await web_navigation_agent_runtime.stop_when_signal()
    await model_client.close()


if __name__ == "__main__":
    set_all_log_levels(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, message="Resolved model mismatch.*")
    asyncio.run(main(load_config()))