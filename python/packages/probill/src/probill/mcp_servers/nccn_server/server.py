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
from .nccn_tool import DecisionLoader
import signal

# Initialize FastMCP server for NCCN tools (SSE)
mcp = FastMCP("nccn")

# Global state storage
evaluation_states: Dict[str, Dict[str, Any]] = {}

class NCCNEvaluation(BaseModel):
    """Evaluation request class for NCCN guidelines."""
    evaluation_id: str | None = None
    patient_id: str
    start_page_id: str = "BINV-20"
    neo4j_uri: str = "bolt://10.0.40.49:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "sacf_sacf"
    neo4j_database: str = "neo4j"

    def __init__(self, evaluation_id: str | None = None, **kwargs) -> None:
        if not evaluation_id:
            evaluation_id = str(uuid.uuid4())
        super().__init__(
            evaluation_id=evaluation_id,
            **kwargs
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "patient_id": self.patient_id,
            "start_page_id": self.start_page_id,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": self.neo4j_password,
            "neo4j_database": self.neo4j_database
        }

@mcp.resource("patient://{patient_id}")
async def get_patient(patient_id: str) -> Dict[str, Any]:
    """Get patient details from the knowledge graph.

    Args:
        patient_id (str): ID of the patient
    Returns:
        Dict[str, Any]: Dictionary containing patient details
    """
    return {
        "patient_id": patient_id,
        "name": "John Doe",
        "age": 45,  
    }

@mcp.resource("regimen://{name}")
async def get_regimen(name: str) -> Dict[str, Any]:
    """Get regimen details from the knowledge graph.

    Args:
        name (str): Name of the regimen

    Returns:
        Dict[str, Any]: Dictionary containing regimen details
    """
    # Load regimen details from the decision tree
    # This is a placeholder; actual implementation will depend on the decision tree structure
    regimen_details = {
        "name": name,
        "description": f"Details for regimen {name}"
    }
    return regimen_details

@mcp.prompt("evaluation")
async def get_evaluation_prompt(patient_id: str, start_page_id: str, clinical_data: Dict) -> Dict[str, Any]:
    """_summary_

    Args:
        patient_id (str): _description_
        start_page_id (str): _description_
        clinical_data (Dict): _description_

    Returns:
        Dict[str, Any]: _description_
    """
    return {
        "template": (
            f"Evaluate the patient {patient_id} against the NCCN guidelines starting from page {start_page_id}. "
            f"Use the following clinical data: {clinical_data}"
        )
    }
    
@mcp.tool()
async def update_patient_data(patient_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update patient data in the knowledge graph.

    Args:
        patient_id (str): ID of the patient
        data (Dict[str, Any]): Data to update

    Returns:
        Dict[str, Any]: Dictionary containing updated patient details
    """
    # Placeholder for updating patient data in the knowledge graph
    # Actual implementation will depend on the Neo4j database structure
    return {
        "status": "success",
        "message": f"Patient {patient_id} updated successfully",
        "data": data
    }
    
@mcp.tool()
async def remove_patient_data(patient_id: str) -> Dict[str, Any]:
    """Remove patient data from the knowledge graph.

    Args:
        patient_id (str): ID of the patient

    Returns:
        Dict[str, Any]: Dictionary containing removal status
    """
    # Placeholder for removing patient data from the knowledge graph
    # Actual implementation will depend on the Neo4j database structure
    return {
        "status": "success",
        "message": f"Patient {patient_id} removed successfully"
    }
    
@mcp.tool()
async def remove_patient(patient_id: str) -> Dict[str, Any]:
    """Remove patient from the knowledge graph.

    Args:
        patient_id (str): ID of the patient

    Returns:
        Dict[str, Any]: Dictionary containing removal status
    """
    # Placeholder for removing patient from the knowledge graph
    # Actual implementation will depend on the Neo4j database structure
    return {
        "status": "success",
        "message": f"Patient {patient_id} removed successfully"
    }
    # Placeholder for removing patient from the knowledge graph
    
    
    
@mcp.tool()
async def evaluate_patient_guidelines(evaluation: NCCNEvaluation) -> Dict[str, Any]:
    """Evaluate a patient against NCCN guidelines using the decision tree.

    Args:
        evaluation (NCCNEvaluation): Evaluation request containing:
            - evaluation_id: Unique identifier for the evaluation (optional)
            - patient_id: ID of the patient to evaluate
            - start_page_id: Starting page ID in NCCN guidelines (default: BINV-20)
            - neo4j_uri: URI for Neo4j database (optional)
            - neo4j_user: Neo4j username (optional)
            - neo4j_password: Neo4j password (optional)
            - neo4j_database: Neo4j database name (default: oncologykg)

    Returns:
        Dict[str, Any]: Dictionary containing:
            - status: "success" or "error"
            - evaluation: Evaluation details (on success)
            - result: Evaluation results including steps, therapies, missing data
            - message: Success/error message
    """
    try:
        # Initialize DecisionLoader with Neo4j connection details
        loader = DecisionLoader(
            evaluation.neo4j_uri,
            evaluation.neo4j_user,
            evaluation.neo4j_password,
            evaluation.neo4j_database
        )

        # Evaluate patient
        result = loader.evaluate_patient(evaluation.patient_id, evaluation.start_page_id)
        
        # Close Neo4j connection
        loader.close()

        # Store evaluation state
        evaluation_states[evaluation.evaluation_id] = {
            "evaluation": evaluation.to_dict(),
            "result": result
        }

        return {
            "status": "success",
            "evaluation": evaluation.to_dict(),
            "result": result,
            "message": f"Successfully evaluated patient {evaluation.patient_id} against NCCN guidelines"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def get_evaluation_state(evaluation_id: str) -> Dict[str, Any]:
    """Get the state of an NCCN evaluation with the given ID.

    Args:
        evaluation_id (str): ID of the evaluation to retrieve

    Returns:
        Dict[str, Any]: The evaluation state if found, or error if not found
    """
    if evaluation_id in evaluation_states:
        return {
            "status": "success",
            "state": evaluation_states[evaluation_id]
        }
    return {
        "status": "error",
        "message": f"No evaluation found with ID {evaluation_id}"
    }


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

    parser = argparse.ArgumentParser(description="Run NCCN MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9003, help="Port to listen on")

    args = parser.parse_args()

    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)
    
    def signal_handler(sig, frame):
        print("\nShutting down NCCN MCP server...")
        # Close MCP client connections
        mcp._mcp_server.close()
        
        # Close any open Neo4j connections
        for state in evaluation_states.values():
            if 'loader' in state:
                state['loader'].close()
        evaluation_states.clear()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)