from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import argparse
import aiohttp
from .mcp_tool_manager import add_mcp_tools
# Initialize FastMCP server for GalleryManager tools (SSE)
mcp = FastMCP("gallery_manager")

@mcp.tool()
async def get_gallery(user_id: str, gallery_id: Optional[str]=None) -> Dict[str, Any]:
    """Get gallery information for a user.

    Args:
        user_id (str): User ID (email)
        gallery_id (Optional[str]): Specific gallery ID if requesting single gallery

    Returns:
        Dict[str, Any]: Gallery information response from API
    """
    
    try:
        base_url = "http://localhost:8081/api/gallery"
        headers = {"accept": "application/json"}
        
        async with aiohttp.ClientSession() as session:
            if gallery_id is None:
                url = f"{base_url}/?user_id={user_id}"
            else:
                url = f"{base_url}/{gallery_id}?user_id={user_id}"
                
            async with session.get(url, headers=headers) as response:
                return await response.json()
                
    except Exception as e:
        return {"status": "error", "message": str(e)}

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can serve the provided mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

if __name__ == "__main__":
    mcp_server = mcp._mcp_server  # noqa: WPS437
    
    parser = argparse.ArgumentParser(description='Run Probill MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=9002, help='Port to listen on')

    args = parser.parse_args()

    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)
