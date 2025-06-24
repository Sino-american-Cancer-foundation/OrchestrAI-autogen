import asyncio
import logging
import warnings

from ._wrapper_agent import WrapperAgent
from ._types import AppConfig, UserMessage, AssistantMessage, MessageChunk
from ._utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import McpWorkbench, SseServerParams
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.WARNING)

async def main(config: AppConfig):
    """Start the Wrapper Agent runtime."""
    # Initialize runtime
    wrapper_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    wrapper_runtime.add_message_serializer(
        get_serializers([UserMessage, AssistantMessage, MessageChunk])
    )
    
    # Start runtime
    Console().print(Markdown("Starting **`Wrapper Agent`**"))
    await wrapper_runtime.start()

    # Initialize model client
    model_client = OpenAIChatCompletionClient(**config.client_model_config)
    
    # Initialize MCP Workbench
    workbench = McpWorkbench(
        SseServerParams(url=config.client_config.mcp_server_url)
    )
    await workbench.start()
    
    # List available capabilities
    print("\n=== MCP Server Capabilities ===")
    
    # List tools
    tools = await workbench.list_tools()
    print("\nAvailable Tools:")
    for tool in tools:
        print(f"- {tool['name']}: {tool['description']}")
    
    # Check if ask_ai_agent tool exists
    has_ai_agent = any(tool['name'] == 'ask_ai_agent' for tool in tools)
    if not has_ai_agent:
        print("\n⚠️  WARNING: 'ask_ai_agent' tool not found in MCP server!")
        print("Make sure your MCP server is running and implements this tool.")
    
    print("\n================================\n")
    
    # Register WrapperAgent
    wrapper_agent_type = await WrapperAgent.register(
        wrapper_runtime,
        "wrapper_agent",
        lambda: WrapperAgent(
            description=config.wrapper_agent.description,
            workbench=workbench,
            ui_config=config.ui_agent,
            model_client=model_client,
        ),
    )
    
    # Set up subscriptions
    await wrapper_runtime.add_subscription(
        TypeSubscription(
            topic_type=config.wrapper_agent.topic_type, 
            agent_type=wrapper_agent_type.type
        )
    )
    await wrapper_runtime.add_subscription(
        TypeSubscription(
            topic_type=config.ui_agent.topic_type,
            agent_type=wrapper_agent_type.type
        )
    )
    
    # Wait until stopped
    await wrapper_runtime.stop_when_signal()
    await workbench.stop()

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    asyncio.run(main(load_config())) 