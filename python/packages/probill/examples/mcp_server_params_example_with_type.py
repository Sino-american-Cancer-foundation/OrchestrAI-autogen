"""
Example demonstrating how to use McpHostAgent with different server parameter types
that include the type discriminator field.
"""
import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from probill.agents import McpHostAgent
from probill.utils import check_and_create_server_params, create_stdio_server, create_sse_server
from autogen_agentchat.ui import Console
from autogen_core import CancellationToken

async def example_with_type_field():
    """Example showing how to use the MCP Host Agent with server params that include the type field."""
    # Create a model client
    model_client = OpenAIChatCompletionClient(model="gpt-4")
    
    # Method 1: Create server_params as dictionaries with type field
    stdio_server_params = {
        "type": "StdioServerParams",  # Include the type field
        "command": ["python", "-m", "my_server"],
        "args": ["--debug"],
        "env": {"DEBUG": "1"},
        "read_timeout_seconds": 10
    }
    
    sse_server_params = {
        "type": "SseServerParams",  # Include the type field
        "url": "https://api.example.com/mcp",
        "headers": {"Authorization": "Bearer your-api-key"},
        "timeout": 30.0,
        "sse_read_timeout": 600.0
    }
    
    # Method 2: Use the utility functions that set the type field
    stdio_params = create_stdio_server({
        "command": ["python", "-m", "my_other_server"],
        "args": ["--debug"],
        "env": {"DEBUG": "1"}
    })
    
    sse_params = create_sse_server({
        "url": "https://api.another-example.com/mcp",
        "headers": {"Authorization": "Bearer another-api-key"}
    })
    
    # Method 3: Use check_and_create_server_params utility
    # This automatically adds the type field if missing
    processed_stdio_params = check_and_create_server_params(stdio_server_params)
    processed_sse_params = check_and_create_server_params(sse_server_params)
    
    # Now create an agent with any of these server parameters
    agent = McpHostAgent(
        name="mcp_agent",
        model_client=model_client,
        # You can pass:
        # 1. Dict with type field: stdio_server_params, sse_server_params
        # 2. Objects created by utility functions: stdio_params, sse_params
        # 3. Processed params: processed_stdio_params, processed_sse_params
        mcp_servers=[stdio_server_params, sse_server_params],
        system_message="You are a helpful MCP host agent."
    )
    
    print("MCP Agent created successfully with server parameters that include type field")
    return agent

if __name__ == "__main__":
    # This is just an illustrative example and won't run fully since the server params point to
    # non-existent servers. In a real application, you would use valid server configurations.
    asyncio.run(example_with_type_field())
