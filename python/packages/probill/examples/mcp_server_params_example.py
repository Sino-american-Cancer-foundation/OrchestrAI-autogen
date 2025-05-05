"""
Example showing how to use the MCP server params utility functions
"""
import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from probill.agents import McpHostAgent
from probill.utils._mcp_utils import check_and_create_server_params
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken

async def example_with_dict_params() -> None:
    """Example showing how to use the MCP Host Agent with dictionary server params."""
    # Create a model client
    model_client = OpenAIChatCompletionClient(model="gpt-4")
    
    # Create server params as dictionaries
    stdio_server_params = {
        "command": ["python", "-m", "my_server"],
        "args": ["--debug"],
        "env": {"DEBUG": "1"}
    }
    
    sse_server_params = {
        "url": "https://api.example.com/mcp",
        "headers": {"Authorization": "Bearer your-api-key"}
    }
    
    # The utility will automatically convert these to proper types
    # You can do this explicitly:
    processed_stdio_params = check_and_create_server_params(stdio_server_params)
    processed_sse_params = check_and_create_server_params(sse_server_params)
    
    print(f"Processed stdio params: {type(processed_stdio_params)}")
    print(f"Processed SSE params: {type(processed_sse_params)}")
    
    # Or the McpHostAgent will handle it automatically
    agent = McpHostAgent(
        name="mcp_agent",
        model_client=model_client,
        # Pass either the processed params:
        # mcp_servers=[processed_stdio_params, processed_sse_params],
        # Or pass the dictionaries directly:
        mcp_servers=[stdio_server_params, sse_server_params],
        system_message="You are a helpful MCP host agent."
    )
    
    # Now the agent will automatically handle the server params
    # (In a real example, we'd actually run the agent)
    # await Console(agent.run_stream(task="Your task", cancellation_token=CancellationToken()))
    
    return agent

if __name__ == "__main__":
    # This is just an illustrative example and won't run fully since the server params point to
    # non-existent servers. In a real application, you would use valid server configurations.
    asyncio.run(example_with_dict_params())
