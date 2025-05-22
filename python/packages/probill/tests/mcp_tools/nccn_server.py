from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
import uvicorn
import argparse
from .nccn_tool import DecisionLoader

# Initialize FastMCP server for NCCN tools
mcp = FastMCP("nccn")

# Global state storage
evaluation_states: Dict[str, Dict[str, Any]] = {}

# Resource definitions
DECISION_TREE_RESOURCE = {
    "type": "decision_tree",
    "content": None,  # Will be loaded dynamically
    "metadata": {
        "description": "NCCN Clinical Practice Guidelines decision tree",
        "version": "2023.1"
    }
}

# Prompt templates
EVALUATION_PROMPT = """Evaluate patient {patient_id} against NCCN guidelines starting from page {start_page_id}.
Consider the following clinical data points:
{clinical_data}

Follow the decision tree and determine:
1. Recommended therapies
2. Missing information needed for decisions
3. Next steps in the pathway"""

class NCCNEvaluation(BaseModel):
    """Evaluation request class for NCCN guidelines."""
    evaluation_id: str | None = None
    patient_id: str
    start_page_id: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str = "oncologykg"

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


@mcp.tool()
async def evaluate_patient_guidelines(evaluation: NCCNEvaluation) -> Dict[str, Any]:
    """Evaluate a patient against NCCN guidelines using the decision tree."""
    try:
        # Initialize DecisionLoader with Neo4j connection details
        loader = DecisionLoader(
            evaluation.neo4j_uri,
            evaluation.neo4j_user,
            evaluation.neo4j_password,
            evaluation.neo4j_database
        )

        # Get the decision tree resource
        decision_tree = await mcp.get_resource("decision_tree")
        if not decision_tree.content:
            # Load the decision tree if not already loaded
            decision_tree.content = loader.load_decision_tree()

        # Get the evaluation prompt
        prompt = await mcp.get_prompt("evaluation")
        clinical_data = loader.get_patient_data(evaluation.patient_id)
        
        # Format the prompt with patient data
        formatted_prompt = prompt.template.format(
            patient_id=evaluation.patient_id,
            start_page_id=evaluation.start_page_id,
            clinical_data=clinical_data
        )

        # Evaluate patient using the decision tree
        result = loader.evaluate_patient(
            evaluation.patient_id,
            evaluation.start_page_id,
            decision_tree=decision_tree.content
        )
        
        # Close Neo4j connection
        loader.close()

        # Store evaluation state
        evaluation_states[evaluation.evaluation_id] = {
            "evaluation": evaluation.to_dict(),
            "result": result,
            "prompt": formatted_prompt
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
    """Get the state of an NCCN evaluation."""
    if evaluation_id in evaluation_states:
        return {
            "status": "success",
            "state": evaluation_states[evaluation_id]
        }
    return {
        "status": "error",
        "message": f"No evaluation found with ID {evaluation_id}"
    }


# Register resources and prompts
@mcp.on_initialize
async def initialize_server(context: Context) -> None:
    """Initialize server resources and prompts."""
    await context.register_resource("decision_tree", DECISION_TREE_RESOURCE)
    await context.register_prompt("evaluation", {
        "template": EVALUATION_PROMPT,
        "variables": ["patient_id", "start_page_id", "clinical_data"],
        "metadata": {
            "description": "Template for evaluating a patient against NCCN guidelines"
        }
    })


def create_app(*, debug: bool = False) -> Starlette:
    """Create a Starlette application for the NCCN MCP server."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NCCN MCP SSE-based server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9003, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    app = create_app(debug=args.debug)
    uvicorn.run(app, host=args.host, port=args.port)