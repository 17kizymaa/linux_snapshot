from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from typing import Any

from . import __version__
from .protocol import handle_request


MCP_PROTOCOL_VERSION = "2024-11-05"


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "awareness.health",
        "description": "Return local daemon health and local paths.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "awareness.status",
        "description": "Return daemon, store, and current project status.",
        "inputSchema": {
            "type": "object",
            "properties": {"cwd": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "awareness.context.project",
        "description": "Return project metadata inferred from the local filesystem and git state.",
        "inputSchema": {
            "type": "object",
            "properties": {"cwd": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "awareness.memory.recall",
        "description": "Recall local memories for the current project context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "cwd": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "awareness.memory.remember",
        "description": "Store an explicit local memory. This write-capable tool should remain opt-in.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "category": {"type": "string"},
                "context": {"type": "string"},
                "rationale": {"type": "string"},
                "source": {"type": "string", "enum": ["user", "agent"]},
                "cwd": {"type": "string"},
            },
            "required": ["text"],
        },
    },
]

TOOL_TO_METHOD = {
    "awareness.health": "health",
    "awareness.status": "status",
    "awareness.context.project": "context.project",
    "awareness.memory.recall": "memory.recall",
    "awareness.memory.remember": "memory.remember",
}


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _text_result(value: Any, *, error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": _json_text(value)}],
        "isError": error,
    }


def _call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    method = TOOL_TO_METHOD.get(name)
    if method is None:
        raise ValueError(f"unknown awareness tool: {name}")
    return handle_request(method, arguments or {})


async def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "awareness-agent", "version": __version__},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOL_DEFINITIONS},
        }

    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        try:
            result = _call_tool(name, arguments if isinstance(arguments, dict) else {})
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": _text_result(result),
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": _text_result({"error": str(exc)}, error=True),
            }

    if request_id is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"method not found: {method}"},
    }


async def serve_forever() -> None:
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_running_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_running_loop())

    try:
        while True:
            line = await reader.readline()
            if not line:
                return
            try:
                message = json.loads(line.decode("utf-8"))
                response = await _handle_message(message if isinstance(message, dict) else {})
            except Exception as exc:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
            if response is not None:
                writer.write((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))
                await writer.drain()
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
