from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class McpServerParams:
    """Base class for MCP server connection parameters."""
    pass


@dataclass
class StdioServerParams(McpServerParams):
    """Parameters for connecting to a command-line MCP tool."""
    command: List[str]
    working_directory: Optional[str] = None
    environment: Optional[Dict[str, str]] = None


@dataclass
class SseServerParams(McpServerParams):
    """Parameters for connecting to an HTTP/SSE MCP service."""
    base_url: str
    timeout: float = 30.0
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    auth: Optional[Dict[str, str]] = None


@dataclass
class ResourceConfig:
    """Configuration for an MCP resource."""
    type: str
    metadata: Dict[str, Any]
    content_type: str = "application/json"


@dataclass
class PromptConfig:
    """Configuration for an MCP prompt template."""
    template: str
    variables: List[str]
    metadata: Dict[str, Any]
    model: Optional[str] = None


@dataclass
class SamplingConfig:
    """Configuration for LLM response sampling."""
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: Optional[int] = None
    stop_sequences: Optional[List[str]] = None