import httpx
import os
import click
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL")

# Initialize FastMCP server
mcp = FastMCP("tool-api")


async def make_api_request(endpoint: str, method: str = "GET", data: dict = None, params: dict = None):
    """Make a request to the API with proper error handling."""
    url = f"{API_BASE_URL}{endpoint}"

    async with httpx.AsyncClient() as client:
        try:
            if method.upper() == "GET":
                response = await client.get(url, params=params, timeout=120.0)
            elif method.upper() == "POST":
                response = await client.post(url, json=data, timeout=120.0)
            else:
                return {"error": f"Unsupported method: {method}"}

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}


@mcp.tool(
    name="portal-login", description="Log into an insurance portal and capture a screenshot of the member information."
)
async def portal_login(url: str, username: str, password: str) -> str:
    """Log into an insurance portal and return a screenshot.

    Args:
        url: The full URL of the insurance portal website
        username: Login username or member ID
        password: Login password or date of birth

    Returns:
        A detailed response about the login attempt and the result screenshot ID for further analysis
    """
    data = {"url": url, "username": username, "password": password}

    response = await make_api_request("/portal-login", "POST", data)

    if "error" in response:
        return f"Failed to log into portal: {response['error']}"

    screenshot_data = response.get("screenshot", "")
    if not screenshot_data:
        return "Login may have been successful, but no screenshot was captured."

    # We don't return the raw screenshot base64 as it would be too large
    # Instead, we indicate success and that the screenshot was captured

    # Generate a real-fake screenshot ID for display purposes
    screenshot_id = "SCRN" + str(hash(screenshot_data))[-6:]
    return f"Successfully captured the screenshot of the member information page. Screenshot ID: {screenshot_id}"


@mcp.tool(
    name="analyze-image",
    description="Analyze an insurance portal screenshot to determine eligibility for a specific service date.",
)
async def analyze_image(screenshot_id: str, service_date: str) -> str:
    """Analyze an insurance portal screenshot to determine eligibility.

    Args:
        screenshot_id: Base64-encoded image of the insurance portal page
        service_date: The service date in YYYY-MM-DD format

    Returns:
        Extracted insurance details including provider information and eligibility status
    """
    data = {"screenshot_id": screenshot_id, "service_date": service_date}

    response = await make_api_request("/analyze-image", "POST", data)

    if "error" in response:
        return f"Failed to analyze portal image: {response['error']}"

    # Format the response in a readable way
    result = []
    result.append(f"Insurance Provider: {response.get('insurance_provider_name', 'Unknown')}")
    result.append(f"Eligibility: {'Eligible' if response.get('eligibility', False) else 'Not Eligible'}")

    if response.get("ipa", False):
        result.append(f"IPA Involved: Yes")
        result.append(f"IPA Phone Number: {response.get('ipa_phone_number', 'Not available')}")
    else:
        result.append(f"IPA Involved: No")
        result.append(f"Provider Phone Number: {response.get('provider_phone_number', 'Not available')}")

    result.append(f"Reason: {response.get('reason', 'No reason provided')}")

    return "\n".join(result)


@mcp.tool(name="make-call", description="Initiate an outgoing call to verify insurance eligibility with a provider.")
async def make_call(phone_number: str, information: str) -> str:
    """Initiate an outgoing call to verify insurance eligibility. After the call is completed, use get_call_results to check the results.

    Args:
        phone_number: A valid E.164 formatted phone number (e.g., +12345678900)
        information: Information about the patient and service to include in the call

    Returns:
        The call SID that can be used to retrieve results later
    """
    data = {"to": phone_number, "information": information}

    response = await make_api_request("/make-call", "POST", data)

    if "error" in response:
        return f"Failed to initiate call: {response['error']}"

    call_sid = response.get("call_sid", "Unknown")
    status = response.get("status", "Unknown")

    return f"Call initiated with SID: {call_sid}\nStatus: {status}\n\nPlease use get_call_results with this SID to check the verification results once the call is completed."


@mcp.tool(
    name="get-call-results",
    description="Retrieve results from a completed insurance verification call. Keep checking until the call response is not unknown.",
)
async def get_call_results(call_sid: str) -> str:
    """Get the results of a completed insurance verification call.

    Args:
        call_sid: The unique call identifier returned by make_call

    Returns:
        The eligibility verification results from the call

    Note: This endpoint must be used after the make_call tool. Results will show as "unknown" until the call is completed.
    """
    response = await make_api_request(f"/call-results/{call_sid}", "GET")

    if "error" in response:
        return f"Failed to retrieve call results: {response['error']}"

    results = response.get("results", "Unknown")

    if results == "unknown":
        return "The call is still in progress or hasn't been completed yet. Please try again in a few moments."

    return f"Insurance Verification Results: {results}"


@mcp.tool(
    name="run-vm-task",
    description="Run a background task on the VM that takes some time to fill out information into a third-party EMR/EHR system.",
)
async def run_vm_task(task_name: str) -> str:
    """Run a task on the VM that takes some time to complete.

    Args:
        task_name: The name of the filling task to run on the VM

    Returns:
        Status message indicating if the task was successfully completed
    """
    response = await make_api_request("/run-vm-task", "POST", {"task_name": task_name})

    if "error" in response:
        return f"Failed to run VM task: {response['error']}"

    status = response.get("status", "Unknown")
    message = response.get("message", "No message provided")

    return f"VM Task Status: {status}\nMessage: {message}"


@click.command()
@click.option("--port", default=8000, help="Port to listen on for SSE")
def main(port: int):
    # Set up SSE transport
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp._mcp_server.run(streams[0], streams[1], mcp._mcp_server.create_initialization_options())

    # Create Starlette app with SSE routes
    starlette_app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    # Run the server using Uvicorn
    import uvicorn

    print(f"Starting server on port {port}...")
    uvicorn.run(starlette_app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
