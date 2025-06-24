"""Quick test-driver for :class:`~fast_mcp_example.extended_mcp_workbench.ExtendedMcpWorkbench`.

Run this script while your *FastMCP* server is up (e.g. by executing the
`proxy-mcp-server` app you provided).  It demonstrates that the new workbench
can:

• list tools
• list resources & fetch one example resource
• list prompts   & fetch one example prompt
• invoke a couple of tools (``make_call`` & ``transcribe_audio``)

Adjust the server URL / parameters as necessary.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Mapping

from autogen_ext.tools.mcp import SseServerParams

# Local import – make sure PYTHONPATH includes the *samples* folder or run the
# script via ``python -m python.samples.fast_mcp_example.test_extended_mcp_workbench``
from extended_mcp_workbench.extended_mcp_workbench import (
    ExtendedMcpWorkbench,
)

# --------------------------------------------------------------------------- helpers #

def _parse_response(response: Any) -> Mapping[str, Any]:
    """Coerce *ToolResult.result* (list of ResultContent) into a JSONable dict."""
    if isinstance(response, list) and response:
        first = response[0]
        # ``TextResultContent`` comes through as an object with ``content`` attr
        text = getattr(first, "content", None) or getattr(first, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except Exception:  # noqa: BLE001 – fall back to raw text
                return {"raw_response": text}
    if isinstance(response, dict):
        return response
    return {"raw_response": str(response)}


def _pretty(obj: Mapping[str, Any]) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:  # pragma: no cover – should not really happen
        return str(obj)


# ----------------------------------------------------------------------------- main #


async def main() -> None:
    server_url = os.getenv("FAST_MCP_SERVER", "http://localhost:8931/sse")

    workbench = ExtendedMcpWorkbench(SseServerParams(url=server_url))
    await workbench.start()
    try:
        print("\n=== Connected to MCP server ===\n")

        # ---------------------------------------------------------------- tools #
        print("--- Tools ---")
        tools = await workbench.list_tools()
        for t in tools:
            print(f"• {t['name']}: {t.get('description', '')}")
        print()

        # ------------------------------------------------------------ resources #
        try:
            print("--- Resources ---")
            resources = await workbench.list_resources()
            if resources:
                for r in resources:
                    print(f"• {r.get('uri', r.get('name'))}: {r.get('description', '')}")
                # Fetch the first resource as demo
                first_uri = resources[0]["uri"]
                resource = await workbench.get_resource(first_uri)
                print("\nFetched resource (truncated):")
                print(_pretty(resource)[:500] + "…")
            else:
                print("No resources available")
            print()
        except Exception as exc:
            print(f"Error while handling resources: {exc}\n")

        # ---------------------------------------------------------------- prompts #
        try:
            print("--- Prompts ---")
            prompts = await workbench.list_prompts()
            if prompts:
                for p in prompts:
                    print(f"• {p['name']}: {p.get('description', '')}")
                # Fetch the first prompt as demo
                first_name = prompts[0]["name"]
                prompt = await workbench.get_prompt(first_name)
                print("\nFetched prompt:")
                print(_pretty(prompt))
            else:
                print("No prompts available")
            print()
        except Exception as exc:
            print(f"Error while handling prompts: {exc}\n")

        # -------------------------------------------------------------- call tool #
        print("--- Sample tool calls ---")
        try:
            make_call_res = await workbench.call_tool(
                "make_call",
                {"to_number": "+12132841509", "information": "Test call information"},
            )
            parsed = _parse_response(make_call_res.result)
            print("make_call =>")
            print(_pretty(parsed))
        except Exception as exc:
            print(f"make_call failed: {exc}")

        try:
            transcribe_res = await workbench.call_tool(
                "transcribe_audio",
                {"audio_data": "base64_encoded_test_data", "model": "whisper"},
            )
            parsed = _parse_response(transcribe_res.result)
            print("\ntranscribe_audio =>")
            print(_pretty(parsed))
        except Exception as exc:
            print(f"transcribe_audio failed: {exc}")

    finally:
        await workbench.stop()


if __name__ == "__main__":
    asyncio.run(main()) 