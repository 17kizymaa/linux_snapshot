from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import socket
from typing import Any

from .paths import ensure_dirs, pid_path, secure_chmod, socket_path
from .protocol import handle_request


def _socket_alive(path: object) -> bool:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            sock.connect(str(path))
        return True
    except OSError:
        return False


async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            line = await reader.readline()
            if not line:
                return

            request_id: Any = None
            try:
                request = json.loads(line.decode("utf-8"))
                request_id = request.get("id")
                method = request["method"]
                params = request.get("params") or {}
                result = handle_request(method, params)
                response = {"jsonrpc": "2.0", "result": result, "id": request_id}
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(exc)},
                    "id": request_id,
                }

            writer.write((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))
            await writer.drain()
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


async def serve_forever() -> None:
    ensure_dirs()
    sock_path = socket_path()

    if sock_path.exists():
        if _socket_alive(sock_path):
            raise RuntimeError(f"awareness daemon already running at {sock_path}")
        sock_path.unlink()

    old_umask = os.umask(0o177)
    try:
        server = await asyncio.start_unix_server(_handle_client, path=str(sock_path))
    finally:
        os.umask(old_umask)

    secure_chmod(sock_path, 0o600)
    pid_path().write_text(f"{os.getpid()}\n", encoding="utf-8")
    secure_chmod(pid_path(), 0o600)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    with contextlib.suppress(NotImplementedError, RuntimeError):
        loop.add_signal_handler(signal.SIGTERM, stop_event.set)
        loop.add_signal_handler(signal.SIGINT, stop_event.set)

    try:
        async with server:
            await server.start_serving()
            await stop_event.wait()
    finally:
        server.close()
        await server.wait_closed()
        with contextlib.suppress(FileNotFoundError):
            sock_path.unlink()
        with contextlib.suppress(FileNotFoundError):
            pid_path().unlink()
