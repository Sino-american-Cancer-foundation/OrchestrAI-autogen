# messages.py
from dataclasses import dataclass

@dataclass
class GroupChatMessage:
    """Message sent in group chat"""
    content: str
    source: str

@dataclass
class GroupChatReply:
    """Reply to a message in group chat"""
    content: str
    
@dataclass
class ManagerSelectionRequest:
    """Request to select the next speaker"""
    current_messages: list[GroupChatMessage]
    
@dataclass
class ManagerSelectionResponse:
    """Response with next speaker selection"""
    next_speaker: str
    reason: str