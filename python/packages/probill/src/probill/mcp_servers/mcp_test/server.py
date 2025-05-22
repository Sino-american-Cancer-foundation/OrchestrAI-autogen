from mcp.server.fastmcp import FastMCP, Image
import asyncio
from pdf2image import convert_from_path
from typing import List
import io

GUIDELINE_PATH="/workspaces/OrchestrAI-autogen/python/packages/probill/src/probill/mcp_servers/mcp_nccn/guideline/breast.pdf"

mcp = FastMCP("My App")

@mcp.tool()
async def test_tool(name: str) -> str:
    """Test tool that returns a greeting message."""
    return f"Hello, {name}!"

@mcp.tool()
async def error_tool() -> str:
    """Tool that raises an error."""
    return "This is a test error."
    raise ValueError("This is a test error.")

@mcp.tool()
async def exception_tool() -> str:
    """Tool that raises an exception."""
    raise Exception("This is a test exception.")

@mcp.tool()
async def timeout_tool() -> str:
    """Tool that raises a timeout error."""
    await asyncio.sleep(10)
    return "This tool should have timed out."

@mcp.tool()
async def load_image(page: int) -> List:
    """
    Converts a specified page from a PDF guideline into an image.
    
    Args:
        page (int): Page number to convert from PDF
        
    Returns:
        List: A list containing a success message and the converted image in PNG format
    """
    # Convert single page to image
    images = convert_from_path(
        GUIDELINE_PATH, 
        first_page=page, 
        last_page=page
    )

    # Convert PIL Image to bytes
    img_byte_arr = io.BytesIO()
    images[0].save(img_byte_arr, format='PNG')
    image_bytes = Image(data=img_byte_arr.getvalue(), format="png")

    return [
        f"Loaded page {page} successfully ...",
        image_bytes
    ]

def main():
    mcp.run()