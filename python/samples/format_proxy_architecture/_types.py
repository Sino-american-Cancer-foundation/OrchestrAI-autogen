from dataclasses import dataclass
from typing import Dict, Optional, List, Any
from pydantic import BaseModel

from autogen_core.models import LLMMessage


@dataclass
class MessageChunk:
    message_id: str
    text: str
    author: str
    finished: bool

    def __str__(self) -> str:
        return f"{self.author}({self.message_id}): {self.text}"


class UserMessage(BaseModel):
    content: str
    source: str


class AssistantMessage(BaseModel):
    content: str
    source: str


class CallRequest(BaseModel):
    call_id: str
    to_number: str
    context: str


class GroupChatMessage(BaseModel):
    """Message sent within the group chat system"""
    body: LLMMessage


# Configuration models
class HostConfig(BaseModel):
    hostname: str
    port: int

    @property
    def address(self) -> str:
        return f"{self.hostname}:{self.port}"


class AgentConfig(BaseModel):
    topic_type: str
    description: str
    system_message: str


class UIAgentConfig(BaseModel):
    topic_type: str
    artificial_stream_delay_seconds: Dict[str, float]

    @property
    def min_delay(self) -> float:
        return self.artificial_stream_delay_seconds.get("min", 0.0)

    @property
    def max_delay(self) -> float:
        return self.artificial_stream_delay_seconds.get("max", 0.0)


class AppConfig(BaseModel):
    host: HostConfig
    fpa: AgentConfig
    orchestrator: AgentConfig
    domain_agent: AgentConfig
    ui_agent: UIAgentConfig
    client_config: Dict[str, Any] = {}  # For model client configuration