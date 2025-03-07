from typing import Any, Dict
import json
import uuid
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import argparse

# Initialize FastMCP server for Probill tools (SSE)
mcp = FastMCP("probill")
task_states = {}

class Task(BaseModel):
    """Task class to hold task information."""
    task_id: str | None = None
    task_worker_id: str | None = None
    task_status: str = "initiated"
    task_description: str | None = None
    task_name: str
    task_parameters: Dict[str, Any] | None = None
    task_state: Dict[str, Any] | None = None

    def __init__(
            self, 
            task_id: str, 
            task_parameters: Dict[str, Any] = None,
            **kwargs
        ) -> None:
        if not task_id:
            task_id = str(uuid.uuid4())
        task_parameters["ext_args"]=kwargs if kwargs else {}
        task_state=task_parameters["ext_args"].get("task_state",None)
        task_worker_id=task_parameters["ext_args"].get("task_worker_id",None)
        super().__init__(
            task_id=task_id,
            task_parameters=task_parameters,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_status": self.task_status,
            "task_name": self.task_name,
            "task_description": self.task_description,
            "task_parameters": self.task_parameters,
            "task_state": self.task_state
        }
    
    def __str__(self) -> str:
        return f"Task: {self.task_name} ({self.task_id}) - {self.task_status}"

@mcp.tool()
async def get_task_state(task_id: str) -> Dict[str, Any]:
    """Get the state of the task with the given task ID. format "task_state://{task_id}"."""
    return task_states.get(task_id)

@mcp.tool()
async def set_task_state(task_id: str, task_state: Dict) -> Dict:
    """Set the state of the task with the given task ID.
    
    Args:
        task_id (str): ID of the task to update
        task_state (Dict): New state to update or add
        
    Returns:
        Dict: Status response indicating success or failure
    """
    try:
        if not task_id:
            raise ValueError("task_id cannot be empty")
        
        if not isinstance(task_state, dict):
            raise TypeError("task_state must be a dictionary")

        # Update task state if task_id exists, otherwise add new task
        if task_id in task_states:
            task_states[task_id].update(task_state or {})
        else:
            task_states[task_id] = task_state or {}

        return {
            "status": "success",
            "message": "Task state successfully updated"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
async def initiate_task(task) -> Dict[str, Any]:
    """Initiate a task with the given Task object.

    Args:
        task (Task): Task object containing:
            - task_id: Unique identifier for the task (optional)
            - task_name: Name of the task 
            - task_status: Current status of the task
            - task_description: Description of the task (optional)
            - task_parameters: Dictionary of task-specific parameters (optional)

    Returns:
        Dict[str, Any]: Dictionary containing:
            - status: "success" or "error"
            - task: Task details dictionary (on success)
            - message: Success message with task name and ID (on success)
            - error: Error message (on failure)

    Raises:
        Exception: Any exception during task processing will be caught and returned
            in the error response
    """
    try:
        # Convert task to dictionary format
        print(f"Initiating task type [{type(task)}]: {task}",flush=True)
        if isinstance(task, Task):
            task_dict = task.to_dict()
        elif isinstance(task, str):
            task_dict = json.loads(task)
            task = Task(**task_dict)
        elif isinstance(task, dict):
            if "task" in task:
                task = task.get("task")
            task = Task(**task)
            task_dict = task
        else:
            raise ValueError(f"Invalid task type: {type(task)}")
        # Implementation for task initiation
        # This is a placeholder - implement actual logic

        # Update task state if task_id exists, otherwise add new task
        if task.task_id in task_states:
            task_states[task.task_id].update(task.task_state or {})
        else:
            task_states[task.task_id] = task.task_state or {}

        return {
            "status": "success", 
            "task": task_dict,
            "message": f"Task '{task.task_name}' initiated with ID {task.task_id}"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def retrieve_source_content(task_id: str, uri: str) -> Dict[str, Any]:
    """Retrieve and decrypt source content from the given URI.

    Args:
        task_id (str): Unique identifier for tracking the retrieval request
        uri (str): Source content URI in format "source_content://{data_id}" 
            where data_id is the unique identifier for the content

    Returns:
        Dict[str, Any]: Dictionary containing:
            - status: "success" or "error"
            - content: Content object with id, title, description, content, 
              author, date, tags, categories and metadata (on success)
            - message: Error message (on failure)
    """
    try:
        # Implementation for content retrieval and decryption
        # This is a placeholder - implement actual logic
        source_content = {
            "resources": {
                "uri": "contents://fsh_123456",
                "content": {
                    "id": "fsh_123456",
                    "title": "Face Sheet",
                    "description": "Face sheet for patient",
                    "content": {
                        "patient_name": "John Doe",
                        "patient_dob": "01/01/1970",
                        "patient_address": "123 Main St, Anytown, USA",
                        "patient_phone": "123-456-7890",
                        "patient_email": "",
                        "patient_insurance": "Blue Cross Blue Shield"
                    }
                },
                "metadata": {
                    "type": "face sheet",
                    "original_id": uri,
                }      
            }
        }

        # Update task state with source content
        if task_id in task_states:
            if "source_content" in task_states[task_id]:
                task_states[task_id]["source_content"].update(source_content)
            else:
                task_states[task_id]["source_content"] = source_content
        else:
            task_states[task_id] = {"source_content": source_content}

        return source_content
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def match_healthcare_provider(task_id: str, uri: str) -> Dict[str, Any]:
    """Match and return healthcare provider information from the given URI.

    Args:
        task_id (str): Unique identifier for tracking the retrieval request
        uri (str): Source content URI in format "contents://{content_data_id}" 
            where content_data_id is the unique identifier for the provider content

    Returns:
        Dict[str, Any]: Dictionary containing:
            - status: "success" or "error"  
            - provider: Provider object with id, name, address, contact info,
              services, hours, insurance, languages, specialties and identifiers (on success)
            - message: Error message (on failure)
    """
    try:
        # Implementation for healthcare provider matching
        # This is a placeholder - implement actual logic
        provider = {
            "status": "success", 
            "resources": {
                "uri": "providers://healthcare/huntington_hospital",
                "content": {
                    "id": "huntington_hospital",
                    "name": "Huntington Hospital",
                    "address": "100 W California Blvd, Pasadena, CA 91105",
                    "contact": {
                        "phone": "626-397-5000",
                        "email": "frontoffice@huntington.com"
                    },
                    "services": ["Emergency Care", "Cardiology", "Oncology"],
                    "hours": "24/7",
                    "insurance": ["Blue Cross Blue Shield", "Aetna", "Cigna"],
                    "languages": ["English", "Spanish", "Chinese"],
                    "specialties": ["Cardiology", "Oncology", "Pediatrics"],
                    "identifiers": {
                        "NPI": "1234567890",
                        "EIN": "987654321"
                    }
                },
                "metadata": {
                    "type": "required_data_format",
                    "id": uri
                },
                "context": {
                    "face_sheet": {
                        "prompt": "Please provide the following information for patient registration",
                        "required_data_format":{
                            "patient_name":"",
                            "patient_dob":"",
                            "patient_address":"",
                            "patient_phone":"",
                            "patient_email":"",
                            "patient_insurance":""
                        }
                    }
                }
            }
        }

        # Update task state with source content
        if task_id in task_states:
            if "source_content" in task_states[task_id]:
                task_states[task_id]["provider"].update(provider)
            else:
                task_states[task_id]["provider"] = provider
        else:
            task_states[task_id] = {"provider": provider}

        return provider
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