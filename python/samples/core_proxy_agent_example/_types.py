from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel
from enum import Enum

from autogen_core.models import LLMMessage


class AgentMode(str, Enum):
    """Agent operation modes"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class GroupChatMessage(BaseModel):
    """Core message type for group chat communication - matches distributed group chat pattern"""
    body: LLMMessage

    def __str__(self) -> str:
        return f"{self.body.source}: {self.body.content}"


class RequestToSpeak(BaseModel):
    """Request from orchestrator to an agent to participate in conversation"""
    pass

    def __str__(self) -> str:
        return "RequestToSpeak"


class MessageChunk(BaseModel):
    """UI message chunk for streaming responses"""
    message_id: str
    text: str
    author: str
    finished: bool

    def __str__(self) -> str:
        return f"{self.author}({self.message_id}): {self.text}"


class PatientData(BaseModel):
    """Medical patient data structure"""
    patient_id: str
    name: str
    age: int
    gender: str
    phone: str
    medical_history: List[str]
    current_medications: List[str]
    insurance_info: Dict[str, str]
    recent_visits: List[Dict[str, str]]
    emergency_contact: Dict[str, str]


# Configuration models
class HostConfig(BaseModel):
    hostname: str
    port: int

    @property
    def address(self) -> str:
        return f"{self.hostname}:{self.port}"


class OrchestratorConfig(BaseModel):
    topic_type: str
    max_rounds: int
    model_client_config: Dict[str, Any]


class ChatAgentConfig(BaseModel):
    topic_type: str
    description: str
    system_message: str


class TwilioProxyAgentConfig(ChatAgentConfig):
    websocket_port: int
    phone_pattern: str
    mode: AgentMode


class MedicalDataAgentConfig(ChatAgentConfig):
    search_delay_seconds: float


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
    orchestrator: OrchestratorConfig
    proxy_agent: TwilioProxyAgentConfig
    medical_data_agent: MedicalDataAgentConfig
    ui_agent: UIAgentConfig
    client_config: ClientConfig 