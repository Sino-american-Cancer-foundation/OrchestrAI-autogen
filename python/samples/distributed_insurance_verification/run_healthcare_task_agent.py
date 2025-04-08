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
    healthcare_task_agent_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    healthcare_task_agent_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk]))
    await asyncio.sleep(2)
    Console().print(Markdown("Starting **`Healthcare Task Agent`**"))
    await healthcare_task_agent_runtime.start()
    
    model_client = OpenAIChatCompletionClient(**config.client_config)
    
    healthcare_task_agent_type = await McpSseGroupChatAgent.register(
        healthcare_task_agent_runtime,
        config.healthcare_task_agent.topic_type,
        lambda: McpSseGroupChatAgent(
            description=config.healthcare_task_agent.description,
            group_chat_topic_type=config.group_chat_manager.topic_type,
            system_message=config.healthcare_task_agent.system_message,
            model_client=model_client,
            ui_config=config.ui_agent,
            sse_url=config.healthcare_task_mcp.sse_url,
            sse_headers=config.healthcare_task_mcp.sse_headers,
            sse_timeout=config.healthcare_task_mcp.sse_timeout,
        ),
    )
    
    await healthcare_task_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.healthcare_task_agent.topic_type, agent_type=healthcare_task_agent_type.type)
    )
    await healthcare_task_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.group_chat_manager.topic_type, agent_type=healthcare_task_agent_type.type)
    )

    await healthcare_task_agent_runtime.stop_when_signal()
    await model_client.close()


if __name__ == "__main__":
    set_all_log_levels(logging.ERROR)
    warnings.filterwarnings("ignore", category=UserWarning, message="Resolved model mismatch.*")
    asyncio.run(main(load_config()))