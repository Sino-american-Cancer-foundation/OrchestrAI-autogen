from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel
from enum import Enum


class FlowType(str, Enum):
    """Types of conversation flows the wrapper can handle"""
    SINGLE_RESPONSE = "single_response"
    WEBSOCKET_CONVERSATION = "websocket_conversation"


@dataclass
class MessageChunk:
    """UI message chunk for streaming responses"""
    message_id: str
    text: str
    author: str
    finished: bool

    def __str__(self) -> str:
        return f"{self.author}({self.message_id}): {self.text}"


class UserMessage(BaseModel):
    """Message from user"""
    content: str
    source: str


class AssistantMessage(BaseModel):
    """Message from assistant/agent"""
    content: str
    source: str


class WebSocketSession(BaseModel):
    """Tracks active WebSocket session state"""
    session_id: str
    call_sid: str
    websocket_url: str
    original_request: str
    conversation_history: List[Dict[str, str]] = []
    is_active: bool = True


# Configuration models
class HostConfig(BaseModel):
    hostname: str
    port: int

    @property
    def address(self) -> str:
        return f"{self.hostname}:{self.port}"


class WrapperAgentConfig(BaseModel):
    topic_type: str
    description: str


class UIAgentConfig(BaseModel):
    topic_type: str
    artificial_stream_delay_seconds: Dict[str, float]

    @property
    def min_delay(self) -> float:
        return self.artificial_stream_delay_seconds.get("min", 0.0)

    @property
    def max_delay(self) -> float:
        return self.artificial_stream_delay_seconds.get("max", 0.0)


class ClientConfig(BaseModel):
    """MCP server connection configuration"""
    mcp_server_url: str = "http://localhost:8931/sse"


class AppConfig(BaseModel):
    host: HostConfig
    wrapper_agent: WrapperAgentConfig
    ui_agent: UIAgentConfig
    client_config: ClientConfig 