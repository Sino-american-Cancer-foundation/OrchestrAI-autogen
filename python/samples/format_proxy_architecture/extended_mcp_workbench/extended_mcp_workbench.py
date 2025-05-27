from __future__ import annotations

import asyncio
import builtins
import warnings
from contextlib import AsyncExitStack
from typing import Any, List, Mapping, Optional

from autogen_core import CancellationToken, Image
from autogen_core.tools import (
    ImageResultContent,
    ParametersSchema,
    TextResultContent,
    ToolResult,
    ToolSchema,
    Workbench,
)
from mcp.types import (
    CallToolResult,
    EmbeddedResource,
    ImageContent,
    ListPromptsResult,
    ListResourcesResult,
    TextContent,
)
from pydantic import BaseModel

# Re-use the original implementation for tool interactions
from autogen_ext.tools.mcp import McpWorkbench  # type: ignore
from autogen_ext.tools.mcp._config import (
    McpServerParams,
    SseServerParams,
    StdioServerParams,
)
from autogen_ext.tools.mcp._session import create_mcp_server_session

__all__ = [
    "ExtendedMcpWorkbench",
]


class _ResourceSessionWrapper:
    """Lightweight wrapper to manage the lifetime of a *ClientSession* instance."""

    def __init__(self, server_params: McpServerParams):
        self._server_params = server_params
        self._stack: Optional[AsyncExitStack] = None
        self._session = None  # Will hold the ``ClientSession`` instance

    async def start(self) -> None:
        if self._stack is not None:
            # Already started
            return
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        # ``create_mcp_server_session`` returns an async context manager -> enter it via stack
        cm = create_mcp_server_session(self._server_params)
        self._session = await self._stack.enter_async_context(cm)
        # Perform MCP initialize handshake so the session is ready for requests
        await self._session.initialize()

    async def stop(self) -> None:
        if self._stack is None:
            return
        await self._stack.aclose()
        self._stack = None
        self._session = None

    async def list_resources(self):  # noqa: D401 – keep symmetry with MCP naming
        if self._session is None:
            raise RuntimeError("Resource session not started. Call start() first.")
        return await self._session.list_resources()

    async def get_resource(self, uri: str):
        if self._session is None:
            raise RuntimeError("Resource session not started. Call start() first.")
        # `ClientSession` exposes `read_resource` – not `get_resource`
        return await self._session.read_resource(uri=uri)

    async def list_prompts(self):  # noqa: D401
        if self._session is None:
            raise RuntimeError("Resource session not started. Call start() first.")
        return await self._session.list_prompts()

    async def get_prompt(self, name: str, arguments: Optional[Mapping[str, Any]] | None = None):
        if self._session is None:
            raise RuntimeError("Resource session not started. Call start() first.")
        arguments = arguments or {}
        return await self._session.get_prompt(name=name, arguments=arguments)


class ExtendedMcpWorkbench(McpWorkbench):
    """MCP workbench with *tool* + *resource* + *prompt* support."""

    def __init__(self, server_params: McpServerParams):
        super().__init__(server_params=server_params)
        self._resource_session = _ResourceSessionWrapper(server_params)

    async def start(self) -> None:  # type: ignore[override]
        """Start both the parent workbench *and* the resource session."""
        # Start the tool-handling actor (parent implementation)
        await super().start()
        # Open dedicated session for resources/prompts
        await self._resource_session.start()

    async def stop(self) -> None:  # type: ignore[override]
        """Shutdown resource session first, then the parent workbench."""
        await self._resource_session.stop()
        await super().stop()

    async def list_resources(self) -> List[Mapping[str, Any]]:
        """Return a list of available resources exposed by the MCP server."""
        try:
            raw = await self._resource_session.list_resources()
            # ``raw`` is expected to be a ``ListResourcesResult`` (or simple list).
            if isinstance(raw, ListResourcesResult):
                resources = raw.resources  # type: ignore[attr-defined]
            else:
                resources = raw  # Fall-back – assume it is already a list-like structure.
            return [self._normalise_resource(r) for r in resources]
        except Exception as e:  # pragma: no cover – generic safeguard
            raise RuntimeError(f"Failed to list resources: {e}") from e

    async def get_resource(self, uri: str) -> Mapping[str, Any]:
        """Fetch a single resource by *URI*."""
        try:
            raw = await self._resource_session.get_resource(uri=uri)
            return self._normalise_resource(raw)
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Failed to get resource '{uri}': {e}") from e
        
    async def list_prompts(self) -> List[Mapping[str, Any]]:
        """Return a list of available prompts exposed by the MCP server."""
        try:
            raw = await self._resource_session.list_prompts()
            if isinstance(raw, ListPromptsResult):
                prompts = raw.prompts  # type: ignore[attr-defined]
            else:
                prompts = raw
            return [self._normalise_prompt(p) for p in prompts]
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Failed to list prompts: {e}") from e

    async def get_prompt(self, name: str, arguments: Optional[Mapping[str, Any]] | None = None) -> Mapping[str, Any]:
        """Fetch a single prompt definition by *name*."""
        try:
            raw = await self._resource_session.get_prompt(name=name, arguments=arguments or {})
            return self._normalise_prompt(raw)
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"Failed to get prompt '{name}': {e}") from e

    @staticmethod
    def _normalise_resource(resource: Any) -> Mapping[str, Any]:
        if isinstance(resource, dict):
            return resource
        # Pydantic v2 uses ``model_dump`` – fall back to v1's ``dict``
        if hasattr(resource, "model_dump"):
            return resource.model_dump()  # type: ignore[attr-defined]
        return dict(resource)  # type: ignore[arg-type]

    @staticmethod
    def _normalise_prompt(prompt: Any) -> Mapping[str, Any]:
        if isinstance(prompt, dict):
            return prompt
        if hasattr(prompt, "model_dump"):
            return prompt.model_dump()  # type: ignore[attr-defined]
        return dict(prompt)  # type: ignore[arg-type]
