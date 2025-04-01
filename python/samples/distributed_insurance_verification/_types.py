from dataclasses import dataclass
from typing import Dict

from autogen_core.models import LLMMessage
from autogen_ext.models.openai.config import OpenAIClientConfiguration
from pydantic import BaseModel


class GroupChatMessage(BaseModel):
    """Implements a sample message sent by an LLM agent"""
    body: LLMMessage


class RequestToSpeak(BaseModel):
    """Message type for agents to speak"""
    pass


@dataclass
class MessageChunk:
    message_id: str
    text: str
    author: str
    finished: bool

    def __str__(self) -> str:
        return f"{self.author}({self.message_id}): {self.text}"


# Define Host configuration model
class HostConfig(BaseModel):
    hostname: str
    port: int

    @property
    def address(self) -> str:
        return f"{self.hostname}:{self.port}"


# Define GroupChatManager configuration model
class GroupChatManagerConfig(BaseModel):
    topic_type: str
    max_rounds: int


# Define Agent configuration model
class AgentConfig(BaseModel):
    topic_type: str
    description: str
    system_message: str


# MCP SSE configuration model
class McpSseConfig(BaseModel):
    sse_url: str
    sse_headers: Dict[str, str] = {}
    sse_timeout: float = 120.0


# Define UI Agent configuration model
class UIAgentConfig(BaseModel):
    topic_type: str
    artificial_stream_delay_seconds: Dict[str, float]

    @property
    def min_delay(self) -> float:
        return self.artificial_stream_delay_seconds.get("min", 0.0)

    @property
    def max_delay(self) -> float:
        return self.artificial_stream_delay_seconds.get("max", 0.0)


# Define the overall AppConfig model
class AppConfig(BaseModel):
    host: HostConfig
    group_chat_manager: GroupChatManagerConfig
    web_navigation_agent: AgentConfig
    web_navigation_mcp: McpSseConfig
    image_analysis_agent: AgentConfig
    image_analysis_mcp: McpSseConfig
    healthcare_task_agent: AgentConfig
    healthcare_task_mcp: McpSseConfig
    ui_agent: UIAgentConfig
    client_config: OpenAIClientConfiguration = None