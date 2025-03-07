import asyncio
import json
from typing import List, Optional
from autogen_core import ComponentModel
from autogen_ext.tools.mcp import SseServerParams, StdioServerParams, mcp_server_tools, SseMcpToolAdapter

async def _fetch_mcp_tools(server_params: SseServerParams):
    """Helper to asynchronously fetch MCP tools and update their metadata."""
    tool_adapters = []
    mcp_tools = await mcp_server_tools(server_params)
    for tool in mcp_tools:
        tool_adapter = await SseMcpToolAdapter.from_server_params(server_params, tool.name)
        tool_adapters.append(tool_adapter)
    return tool_adapters

def _update_component_metadata(
    component: ComponentModel, label: Optional[str] = None, description: Optional[str] = None
) -> ComponentModel:
    """Helper method to update component metadata."""
    if label is not None:
        component.label = label
        component.config["name"] = label
    if description is not None:
        component.description = description
        component.config["description"] = description
    return component

def add_mcp_tools(
    server_params_list: List[SseServerParams]
) :
    """Add MCP tools by asynchronously fetching tools for each given server parameter."""
    tools = []
    for server_params in server_params_list:
        tool_adapters = asyncio.run(_fetch_mcp_tools(server_params))
        for adapter in tool_adapters:
            tools.append(_update_component_metadata(
                adapter.dump_component(), adapter.name, adapter.description
            ))
    return tools

mcp_tool_url = "http://localhost:9002/sse"
# Define connection parameters for your MCP service.
server_params_lst = [
    SseServerParams(
        url=mcp_tool_url,
        # headers={"Authorization": "Bearer YOUR_API_KEY", "Content-Type": "application/json"},
        timeout=30  # Connection timeout in seconds
    )
]

tools = add_mcp_tools([server_params for server_params in server_params_lst])
tool_json = []
for tool in tools:
    tool_json.append(tool.model_dump())
    # print(tool.model_dump_json(indent=2))
    
print(json.dumps(tool_json, indent=2))
