import asyncio
import logging

from employees.twilio_proxy_agent import TwilioProxyAgent
from facilities.core import (
    GroupChatMessage, RequestToSpeak, MessageChunk, ConversationFinished, AppConfig, AgentMode,
    load_config, set_all_log_levels, get_serializers
)
from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import McpWorkbench, SseServerParams
from rich.console import Console
from rich.markdown import Markdown

# Set log level
set_all_log_levels(logging.ERROR)

async def main(config: AppConfig):
    """Start the proxy agent runtime following BaseGroupChatAgent pattern."""
    # Initialize runtime
    proxy_agent_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    proxy_agent_runtime.add_message_serializer(get_serializers([RequestToSpeak, GroupChatMessage, MessageChunk, ConversationFinished]))
    
    await asyncio.sleep(3)
    Console().print(Markdown("Starting **`Proxy Agent`**"))
    await proxy_agent_runtime.start()
    
    # Create model client
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=config.orchestrator.model_client_config["api_key"]  # Reuse API key from config
    )
    
    # Initialize MCP Workbench for phone call functionality
    workbench = McpWorkbench(SseServerParams(url="http://localhost:8931/sse"))
    await workbench.start()
    
    # List available tools for verification
    Console().print(Markdown("**MCP Server Connected** - Available Tools:"))
    tools = await workbench.list_tools()
    for tool in tools:
        Console().print(f"- {tool['name']}: {tool.get('description', 'No description')}")
    
    # Register twilio proxy agent
    proxy_agent_type = await TwilioProxyAgent.register(
        proxy_agent_runtime,
        config.proxy_agent.topic_type,
        lambda: TwilioProxyAgent(
            description=config.proxy_agent.description,
            group_chat_topic_type=config.orchestrator.topic_type,
            model_client=model_client,
            system_message=config.proxy_agent.system_message,
            ui_config=config.ui_agent,
            websocket_port=config.proxy_agent.websocket_port,
            phone_pattern=config.proxy_agent.phone_pattern,
            workbench=workbench,
            mode=AgentMode(config.proxy_agent.mode),
        ),
    )
    
    # Set up dual subscriptions following BaseGroupChatAgent pattern
    # 1. Subscribe to own topic for RequestToSpeak messages
    await proxy_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.proxy_agent.topic_type, agent_type=proxy_agent_type.type)
    )
    # 2. Subscribe to group chat topic for message history
    await proxy_agent_runtime.add_subscription(
        TypeSubscription(topic_type=config.orchestrator.topic_type, agent_type=proxy_agent_type.type)
    )
    
    Console().print(Markdown("**`Proxy Agent`** is ready and listening for messages"))
    
    # Wait until stopped
    await proxy_agent_runtime.stop_when_signal()
    await workbench.stop()
    await model_client.close()
    Console().print("Proxy Agent left the chat!")

if __name__ == "__main__":
    config = load_config()
    asyncio.run(main(config)) 