from typing import Callable, Awaitable

from autogen_core import RoutedAgent, MessageContext, message_handler

from .types import MessageChunk


class UIAgent(RoutedAgent):
    """Handles UI-related tasks and message processing for the distributed group chat system."""
    
    def __init__(self, on_message_chunk_func: Callable[[MessageChunk], Awaitable[None]]) -> None:
        super().__init__("UI Agent")
        self._on_message_chunk_func = on_message_chunk_func
    
    @message_handler
    async def handle_message_chunk(self, message: MessageChunk, ctx: MessageContext) -> None:
        await self._on_message_chunk_func(message) 