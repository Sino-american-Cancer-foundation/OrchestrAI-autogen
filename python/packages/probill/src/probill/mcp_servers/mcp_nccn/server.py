from typing import Optional, Dict, Any, AsyncGenerator, TypedDict
import logging
import asyncio
import signal
import uuid
from asyncio import Event
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator
from pydantic import BaseModel, Field, SecretStr, ValidationError
from dataclasses import dataclass
from mcp.server.fastmcp.server import FastMCP, Context, Image
from mcp.types import TextContent, ImageContent, EmbeddedResource
from .nccn_tool import DecisionLoader
from dotenv import load_dotenv
import os
import backoff
from neo4j.exceptions import ServiceUnavailable, AuthError
from pdf2image import convert_from_path
from typing import List
import io

GUIDELINE_PATH="/workspaces/OrchestrAI-autogen/python/packages/probill/src/probill/mcp_servers/mcp_nccn/guideline/breast.pdf"

# Create a named server
# mcp = FastMCP("NCCN MCP Server")
# Custom exceptions
class NCCNServerError(Exception):
    """Base exception for NCCN server errors"""
    pass

class DatabaseConnectionError(NCCNServerError):
    """Raised when database connection fails"""
    pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_nccn")  # Updated logger name
load_dotenv()

class Neo4jConfig(BaseModel):
    """Configuration for Neo4j connection"""
    uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    user: str = Field(default="neo4j", description="Neo4j username")
    password: str = Field(description="Neo4j password")
    database: str = Field(default="neo4j", description="Neo4j database name")

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """Create configuration from environment variables"""
        return cls(
            uri=os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
            user=os.getenv('NEO4J_USER', 'neo4j'),
            password=os.getenv('NEO4J_PASSWORD', ''),
            database=os.getenv('NEO4J_DATABASE', 'neo4j')
        )

class EvaluationState(TypedDict):
    """Type definition for evaluation state storage"""
    evaluation: Dict[str, Any]
    result: Dict[str, Any]

# Global state with proper typing
evaluation_states: Dict[str, EvaluationState] = {}

class NCCNEvaluation(BaseModel):
    """Evaluation request class for NCCN guidelines."""
    patient_id: str = Field(..., description="Unique identifier for the patient")
    start_page_id: str = Field(default="BINV-20", description="Starting page ID in NCCN guidelines")

    def to_dict(self) -> Dict[str, Any]:
        """Convert evaluation to dictionary format"""
        return self.model_dump()

class PatientData(BaseModel):
    """Model for patient data"""
    patient_id: str
    name: str
    age: int
    # Add more fields as needed

class RegimenDetails(BaseModel):
    """Model for regimen details"""
    name: str
    description: str

@dataclass
class AppContext:
    """Application context containing shared resources"""
    loader: DecisionLoader

@backoff.on_exception(
    backoff.expo,
    (ServiceUnavailable, ConnectionError),
    max_tries=5
)
async def connect_to_database(config: Neo4jConfig) -> DecisionLoader:
    """Connect to Neo4j database with retry logic"""
    try:
        print(f"Connecting to Neo4j at {config.uri}")
        print(f"Using database {config.database}")
        print(f"Using user {config.user}")
        print(f"Using password {config.password}")

        # db = neo4jDatabase(
        #     neo4j_uri=config.uri, 
        #     neo4j_username=config.user, 
        #     neo4j_password=config.password, 
        #     neo4j_database=config.database
        # )

        # logger.info("Connected to Neo4j database")

        loader = DecisionLoader(
            uri=config.uri,
            user=config.user,
            password=config.password,
            database=config.database
        )
        # Test connection
        loader.driver.verify_connectivity()
        logger.info("Connected to Neo4j database")
        return loader
    except AuthError as e:
        raise DatabaseConnectionError(f"Authentication failed: {str(e)}")
    except Exception as e:
        raise DatabaseConnectionError(f"Failed to connect to database: {str(e)}")

class ShutdownManager:
    def __init__(self):
        self.shutdown_event = Event()
        self._orig_handlers = {}
        self.is_shutting_down = False

    def setup_signal_handlers(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._orig_handlers[sig] = signal.getsignal(sig)
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.handle_shutdown(s)))

    def restore_signal_handlers(self):
        loop = asyncio.get_running_loop()
        for sig, handler in self._orig_handlers.items():
            if handler:
                try:
                    loop.remove_signal_handler(sig)
                    signal.signal(sig, handler)
                except Exception:
                    pass

    async def handle_shutdown(self, sig):
        if self.is_shutting_down:
            # If already shutting down, force exit on repeated signals
            logger.warning("Forced shutdown requested, exiting immediately")
            os._exit(1)
            
        self.is_shutting_down = True
        logger.info(f"Received signal {sig.name}. Initiating graceful shutdown...")
        self.shutdown_event.set()

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    loader = await connect_to_database(Neo4jConfig.from_env())
    try:
        yield AppContext(loader=loader)
    finally:
        # Cleanup on shutdown
        loader.close()

# @asynccontextmanager
# async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
#     """Manage application lifecycle with graceful shutdown"""
#     print("Starting application lifespan context", flush=True)
#     config = Neo4jConfig.from_env()
#     loader = None
#     cleanup_task = None

#     print("Creating shutdown manager", flush=True)
#     shutdown_manager = ShutdownManager()
    
#     try:
#         print("Connecting to database", flush=True)
#         logger.info(f"Connecting to Neo4j at {config.uri}")
#         loader = await connect_to_database(config)
#         logger.info("Successfully connected to Neo4j database")
        
#         # Set up signal handlers
#         shutdown_manager.setup_signal_handlers()
        
#         # Start cleanup task
#         cleanup_task = asyncio.create_task(cleanup_old_evaluations())
        
#         context = AppContext(loader=loader, config=config)
#         yield context
        
#     except Exception as e:
#         logger.error(f"Error during startup: {e}")
#         raise
#     finally:
#         # Wait for shutdown signal if not already triggered
#         if not shutdown_manager.shutdown_event.is_set():
#             await shutdown_manager.shutdown_event.wait()
            
#         logger.info("Starting cleanup...")
        
#         # Cancel cleanup task
#         if cleanup_task and not cleanup_task.done():
#             cleanup_task.cancel()
#             with suppress(asyncio.CancelledError):
#                 await cleanup_task
        
#         # Close database connection
#         if loader:
#             with suppress(Exception):
#                 await loader.close()
                
#         # Restore original signal handlers
#         shutdown_manager.restore_signal_handlers()
        
#         logger.info("Cleanup complete")

# Initialize MCP server with proper configuration
mcp = FastMCP(
    "NCCN MCP Server",
    # lifespan=app_lifespan
)

async def safe_evaluate_patient(loader: DecisionLoader, evaluation: NCCNEvaluation) -> Dict[str, Any]:
    """Safely evaluate patient with timeout and error handling"""
    try:
        async with asyncio.timeout(30):  # 30 second timeout
            result = loader.evaluate_patient(
                evaluation.patient_id,
                evaluation.start_page_id
            )
            return {
                "status": "success",
                "result": result
            }
    except asyncio.TimeoutError:
        logger.error(f"Evaluation timeout for patient {evaluation.patient_id}")
        return {
            "status": "error",
            "message": "Evaluation timed out"
        }
    except Exception as e:
        logger.error(f"Evaluation error for patient {evaluation.patient_id}: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
async def load_nccn_page(page: int) -> List:
    """
    Converts a specified page from a PDF guideline into an image.
    
    Args:
        page (int): Page number to convert from PDF
        
    Returns:
        str: The converted image in Base64 string format
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
        image_bytes,
        f"Page {page} loaded successfully",
        f"Image size: {images[0].size}",
    ]

@mcp.tool()
async def evaluate_patient(evaluation: NCCNEvaluation) -> Dict[str, Any]:
    """
    Evaluates patient guidelines based on provided NCCN evaluation criteria.
    This tool processes patient data against NCCN guidelines and returns evaluation results. It handles validation, 
    evaluation state management, and error cases.
    Args:
        evaluation (NCCNEvaluation): Object containing:
            - patient_id (str): ID of the patient being evaluated 
            - start_page_id (str): Starting page ID in NCCN guidelines, default is "BINV-20"
    Returns:
        Dict[str, Any]: Response dictionary containing:
            On Success:
                - status: "success"
                - evaluation: Full evaluation data dump
                - result: Evaluation results from guidelines processing
                - message: Success confirmation message
            On Error:
                - status: "error" 
                - message: Error description
    Raises:
        ValidationError: If input evaluation data is invalid
        NCCNServerError: If decision loader is not initialized
        Exception: For unexpected errors during evaluation
    Notes:
        - Stores successful evaluation states with timestamps for later reference
        - Requires initialized decision loader in context
        - Implements proper error handling and logging for various failure cases
    """
    try:
        loader =  await connect_to_database(Neo4jConfig.from_env())
        # ctx.request_context.lifespan_context["loader"]

        if not loader:
            raise NCCNServerError("Decision loader not initialized")

        # result = await safe_evaluate_patient(loader, evaluation)
        result = loader.evaluate_patient(
            evaluation.patient_id,
            evaluation.start_page_id
        )

        result.append(str({"message":"Successfully evaluated patient {evaluation.patient_id} start from page: {evaluation.start_page_id}"}))

        return result
    
        # {
        #     "status": "success",
        #     "evaluation": evaluation.model_dump(),
        #     "result": result,
        #     "message": f"Successfully evaluated patient {evaluation.patient_id}"
        # }

    except ValidationError as e:
        return {"status": "error", "message": f"Invalid input: {str(e)}"}
    except NCCNServerError as e:
        raise
        return {"status": "error", "message": str(e)}
    except Exception as e:
        raise
        logger.error(f"Unexpected error in evaluate_patient_guidelines: {e}")
        return {"status": "error", "message": "Internal server error"}

async def cleanup_old_evaluations():
    """Periodically clean up old evaluation states"""
    while True:
        current_time = asyncio.get_event_loop().time()
        expired_ids = [
            eval_id for eval_id, state in evaluation_states.items()
            if current_time - state["timestamp"] > 3600  # 1 hour TTL
        ]
        for eval_id in expired_ids:
            evaluation_states.pop(eval_id, None)
        await asyncio.sleep(300)  # Run every 5 minutes

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
    
# @mcp.tool()
# async def update_patient_data(patient_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
#     """Update patient data in the knowledge graph.

#     Args:
#         patient_id (str): ID of the patient
#         data (Dict[str, Any]): Data to update

#     Returns:
#         Dict[str, Any]: Dictionary containing updated patient details
#     """
#     # Placeholder for updating patient data in the knowledge graph
#     # Actual implementation will depend on the Neo4j database structure
#     return {
#         "status": "success",
#         "message": f"Patient {patient_id} updated successfully",
#         "data": data
#     }
    
# @mcp.tool()
# async def remove_patient_data(patient_id: str) -> Dict[str, Any]:
#     """Remove patient data from the knowledge graph.

#     Args:
#         patient_id (str): ID of the patient

#     Returns:
#         Dict[str, Any]: Dictionary containing removal status
#     """
#     # Placeholder for removing patient data from the knowledge graph
#     # Actual implementation will depend on the Neo4j database structure
#     return {
#         "status": "success",
#         "message": f"Patient {patient_id} removed successfully"
#     }
    
# @mcp.tool()
# async def remove_patient(patient_id: str) -> Dict[str, Any]:
#     """Remove patient from the knowledge graph.

#     Args:
#         patient_id (str): ID of the patient

#     Returns:
#         Dict[str, Any]: Dictionary containing removal status
#     """
#     # Placeholder for removing patient from the knowledge graph
#     # Actual implementation will depend on the Neo4j database structure
#     return {
#         "status": "success",
#         "message": f"Patient {patient_id} removed successfully"
#     }
#     # Placeholder for removing patient from the knowledge graph
    
def setup_signal_handlers(shutdown_event: asyncio.Event) -> None:
    """Setup handlers for system signals"""
    def signal_handler(signame):
        logger.info(f"Received signal {signame}. Initiating shutdown...")
        shutdown_event.set()

    for signame in ('SIGINT', 'SIGTERM'):
        asyncio.get_event_loop().add_signal_handler(
            getattr(signal, signame),
            lambda s=signame: signal_handler(s)
        )

# async def startup(config: Neo4jConfig) -> None:
#     """Initialize application with the given configuration"""
#     try:
#         loader = await connect_to_database(config)
#         logger.info("Successfully connected to database")
#         return loader
#     except Exception as e:
#         logger.error(f"Failed to initialize application: {e}")
#         raise

def main(
        neo4j_url: str, 
        neo4j_username: str, 
        neo4j_password: str, 
        neo4j_database: str = "neo4j", 
        # shutdown_event: asyncio.Event = None
    ):
    """Main entry point with improved shutdown handling"""
    try:
        logger.info("NCCN MCP Server starting...")
        os.environ["NEO4J_URI"] = neo4j_url if neo4j_url else os.getenv("NEO4J_URI", "bolt://localhost:7687")   
        os.environ["NEO4J_USER"] = neo4j_username if neo4j_username else os.getenv("NEO4J_USER", "neo4j")
        os.environ["NEO4J_PASSWORD"] = neo4j_password if neo4j_password else os.getenv("NEO4J_PASSWORD", "neo4j")
        os.environ["NEO4J_DATABASE"] = neo4j_database if neo4j_database else os.getenv("NEO4J_DATABASE", "neo4j")

        # if shutdown_event:
        #     # If shutdown_event is provided, wait for it in a background task
        #     asyncio.create_task(_wait_for_shutdown(shutdown_event))
        
        mcp.run()
    # except asyncio.CancelledError:
    #     logger.info("Server shutdown requested")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        # Clear any remaining state
        evaluation_states.clear()
        logger.info("Server shutdown complete")