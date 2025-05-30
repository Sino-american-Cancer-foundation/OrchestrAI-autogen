#!/usr/bin/env python3
"""
Test script to verify MCP server connection and available tools.
Run this before starting the wrapper agent to ensure the MCP server is properly configured.
"""

import asyncio
from autogen_ext.tools.mcp import McpWorkbench, SseServerParams

async def test_mcp_server():
    """Test connection to MCP server and list available tools"""
    
    server_url = "http://localhost:8931/sse"
    print(f"Testing connection to MCP server at: {server_url}")
    print("=" * 60)
    
    try:
        # Initialize workbench
        workbench = McpWorkbench(SseServerParams(url=server_url))
        await workbench.start()
        
        print("✓ Successfully connected to MCP server")
        
        # List tools
        tools = await workbench.list_tools()
        print(f"\nFound {len(tools)} tools:")
        for tool in tools:
            print(f"\n- {tool['name']}")
            print(f"  Description: {tool.get('description', 'No description')}")
            if 'parameters' in tool:
                print(f"  Parameters: {tool['parameters']}")
        
        # Test ask_ai_agent tool if available
        tool_names = [t['name'] for t in tools]
        if 'ask_ai_agent' in tool_names:
            print("\n" + "=" * 60)
            print("Testing ask_ai_agent tool...")
            
            result = await workbench.call_tool(
                "ask_ai_agent",
                arguments={"question": "Hello, please tell me about the patient."}
            )
            
            if result.is_error:
                print("✗ Error calling ask_ai_agent tool")
            else:
                response_text = result.result[0].content if result.result and hasattr(result.result[0], 'content') else ""
                print(f"✓ Response: {response_text}")
        else:
            print("\n⚠️  WARNING: ask_ai_agent tool not found!")
            print("Make sure your MCP server is properly configured with the AI agent.")
        
        await workbench.stop()
        print("\n✓ Test completed successfully")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure the MCP server is running on port 8931")
        print("2. Check that OPENAI_API_KEY is set in the MCP server environment")
        print("3. Verify the server URL matches your configuration")
        return False
    
    return True

if __name__ == "__main__":
    print("MCP Server Connection Test")
    asyncio.run(test_mcp_server()) 