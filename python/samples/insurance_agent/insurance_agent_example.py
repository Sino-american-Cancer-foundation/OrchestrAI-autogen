import asyncio
import json
from typing import Dict, List, Any, Union

from autogen_core import FunctionCall
from autogen_core.models import RequestUsage
from autogen_agentchat.messages import ToolCallRequestEvent, ToolCallExecutionEvent, TextMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.insurance import InsuranceAgent

class FormattedConsole:
    """Custom console UI for displaying clean, formatted agent interactions."""
    
    def __init__(self, stream):
        self.stream = stream
        self.tool_calls = []
        self.tool_results = []
    
    async def __aenter__(self):
        return await self.__anext__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    async def __anext__(self):
        return self
    
    async def run(self):
        """Run the stream and display formatted output."""
        print("\n" + "="*80)
        print(" 🏥 INSURANCE VERIFICATION SESSION")
        print("="*80 + "\n")
        
        async for message in self.stream:
            if isinstance(message, TextMessage):
                # Direct text response from the agent
                print("\n🔷 AGENT RESPONSE:")
                print(f"{message.content}\n")
                
            elif isinstance(message, ToolCallRequestEvent):
                # Tool call - captures the reasoning logic and tool selection
                for tool_call in message.content:
                    self.tool_calls.append(tool_call)
                    tool_args = json.loads(tool_call.arguments) if isinstance(tool_call.arguments, str) else tool_call.arguments
                    
                    print("\n📋 REASONING & TOOL SELECTION:")
                    print(f"• Selected tool: {tool_call.name}")
                    print(f"• Parameters: {json.dumps(tool_args, indent=2)}")
                    
            elif isinstance(message, ToolCallExecutionEvent):
                # Tool execution results
                for result in message.content:
                    self.tool_results.append(result)
                    print("\n🛠️ TOOL EXECUTION RESULT:")
                    print(f"• Tool: {result.name}")
                    
                    # Format the content nicely if it's structured
                    try:
                        content_json = json.loads(result.content)
                        print(f"• Result: {json.dumps(content_json, indent=2)}")
                    except (json.JSONDecodeError, TypeError):
                        print(f"• Result: {result.content}")
                    
                    if result.is_error:
                        print("• Status: ❌ ERROR")
                    else:
                        print("• Status: ✅ SUCCESS")
        
        print("\n" + "="*80)
        print(" 🏁 VERIFICATION SESSION COMPLETE")
        print("="*80 + "\n")
        
        return {
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results
        }

async def main() -> None:
    """
    Example script demonstrating how to use the InsuranceAgent with a local MCP server.
    """
    # Create the model client
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    
    # Create the insurance agent
    insurance_agent = InsuranceAgent(
        name="InsuranceVerifier",
        model_client=model_client,
        sse_url="http://localhost:8000/sse", # Update with your actual MCP server URL
    )
    
    # Run a sample task
    task = """
    Help me do your job. Here is the information I have:
    1. Portal website url: https://www.brmsprovidergateway.com/provideronline/search.aspx
    2. Member ID (username): E01257465
    3. Date of Birth (password): 08/03/1988
    4. Patient Name: Liza Silina
    5. Service Date: 2024-01-15
    """
    
    print("🔷 USER REQUEST:")
    print(task)
    
    # Use the formatted console UI to display structured output
    try:
        await FormattedConsole(insurance_agent.run_stream(task=task)).run()
    finally:
        # Clean up resources
        await model_client.close()

if __name__ == "__main__":
    asyncio.run(main())