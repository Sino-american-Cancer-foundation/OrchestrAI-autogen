from __future__ import annotations

import asyncio
import logging
import warnings

from ._agents import FormatProxyAgent
from ._types import AppConfig, CallRequest, UserMessage, AssistantMessage, MessageChunk
from ._utils import get_serializers, load_config, set_all_log_levels
from autogen_core import TypeSubscription
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from .extended_mcp_workbench.extended_mcp_workbench import ExtendedMcpWorkbench
from autogen_ext.tools.mcp import SseServerParams
from rich.console import Console
from rich.markdown import Markdown

set_all_log_levels(logging.WARNING)

async def main(config: AppConfig):
    """Start the Format Proxy Agent runtime."""
    # Initialize runtime
    fpa_runtime = GrpcWorkerAgentRuntime(host_address=config.host.address)
    fpa_runtime.add_message_serializer(
        get_serializers([CallRequest, UserMessage, AssistantMessage, MessageChunk])
    )
    
    # Start runtime
    Console().print(Markdown("Starting **`Format Proxy Agent`**"))
    await fpa_runtime.start()
    
    # Initialize Extended MCP Workbench
    workbench = ExtendedMcpWorkbench(SseServerParams(url="http://localhost:8931/sse"))
    await workbench.start()
    
    # List all available capabilities
    print("\n=== MCP Server Capabilities ===")

    # List tools
    tools = await workbench.list_tools()
    print("\nAvailable Tools:")
    for tool in tools:
        print(f"- {tool['name']}: {tool['description']}")

    # List prompts
    try:
        prompts = await workbench.list_prompts()
        print("\nAvailable Prompts:")
        for prompt in prompts:
            print(f"- {prompt['name']}: {prompt['description']}")
    except Exception as e:
        print(f"\nError listing prompts: {str(e)}")

    # List resources
    try:
        resources = await workbench.list_resources()
        print("\nAvailable Resources:")
        for resource in resources:
            # Use .get for robustness and prefer 'uri' or 'name' as key
            resource_key = resource.get('uri', resource.get('name', 'Unknown Resource'))
            print(f"- {resource_key}: {resource.get('description', '')}")
    except Exception as e:
        print(f"\nError listing resources: {str(e)}")

    print("\n===========================\n")
    
    # Register FormatProxyAgent
    fpa_agent_type = await FormatProxyAgent.register(
        fpa_runtime,
        "format_proxy",
        lambda: FormatProxyAgent(
            description=config.fpa.description,
            workbench=workbench,
            ui_config=config.ui_agent,
        ),
    )
    
    # Set up subscriptions - removed domain_output subscription
    await fpa_runtime.add_subscription(
        TypeSubscription(topic_type=config.fpa.topic_type, agent_type=fpa_agent_type.type)
    )
    await fpa_runtime.add_subscription(
        TypeSubscription(topic_type=config.ui_agent.topic_type, agent_type=fpa_agent_type.type)
    )
    
    # Wait until stopped
    await fpa_runtime.stop_when_signal()
    await workbench.stop()


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    asyncio.run(main(load_config()))