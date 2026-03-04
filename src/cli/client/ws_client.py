"""Async WebSocket client for the ConcepTracker transcription endpoint.

Designed to run inside Textual's async event loop.

Protocol: see .github/skills/fastapi_architecture/SKILL.md  §WebSocket Endpoint

Usage::

    from src.cli.client.ws_client import TranscriptionWSClient

    async def record(on_partial, on_final, on_done, on_error):
        async with TranscriptionWSClient() as ws:
            await ws.send_config(device_id=1)

            # Stream raw PCM bytes from sounddevice callback
            async for chunk in audio_queue:
                if stop_requested:
                    await ws.send_stop()
                    break
                await ws.send_audio(chunk)

            result = await ws.receive_until_done(
                on_partial=on_partial,
                on_final=on_final,
                on_done=on_done,
                on_error=on_error,
            )
"""
from __future__ import annotations

import json
import logging
import os
from typing import Awaitable, Callable, Optional

from websockets.asyncio.client import connect, ClientConnection

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8000"
_WS_PATH = "/ws/transcription"


def _ws_url() -> str:
    http_url = os.environ.get("CONCEPTRACKER_API_URL", _DEFAULT_BASE_URL).rstrip("/")
    return http_url.replace("http://", "ws://").replace("https://", "wss://") + _WS_PATH


class TranscriptionWSClient:
    """Async context manager that wraps the /ws/transcription WebSocket."""

    def __init__(self, url: Optional[str] = None):
        self._url = url or _ws_url()
        self._ws: Optional[ClientConnection] = None

    async def __aenter__(self) -> "TranscriptionWSClient":
        self._ws = await connect(self._url)
        return self

    async def __aexit__(self, *_):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    # ── Sending ───────────────────────────────────────────────────────────────

    async def send_config(self, device_id: Optional[int] = None) -> None:
        """Send an optional config frame before streaming audio."""
        assert self._ws is not None, "Client not connected. Use as async context manager."
        payload: dict = {"type": "config"}
        if device_id is not None:
            payload["device_id"] = device_id
        await self._ws.send(json.dumps(payload))

    async def send_audio(self, chunk: bytes) -> None:
        """Send a raw PCM audio chunk (binary frame)."""
        assert self._ws is not None, "Client not connected."
        await self._ws.send(chunk)

    async def send_stop(self) -> None:
        """Signal the server to end the session and run the enhancement pipeline."""
        assert self._ws is not None, "Client not connected."
        await self._ws.send(json.dumps({"type": "stop"}))

    # ── Receiving ─────────────────────────────────────────────────────────────

    async def receive_until_done(
        self,
        on_partial: Optional[Callable[[str], Awaitable[None]]] = None,
        on_final: Optional[Callable[[str], Awaitable[None]]] = None,
        on_done: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Optional[dict]:
        """
        Read server messages until a "done" or "error" frame arrives.

        Returns the "done" payload dict or None on error/disconnect.
        """
        assert self._ws is not None, "Client not connected."
        async for raw in self._ws:
            if isinstance(raw, bytes):
                logger.debug("Ignoring unexpected binary frame from server.")
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON frame: %r", raw)
                continue

            event_type = msg.get("type")

            if event_type == "partial" and on_partial:
                await on_partial(msg.get("text", ""))

            elif event_type == "final" and on_final:
                await on_final(msg.get("text", ""))

            elif event_type == "done":
                if on_done:
                    await on_done(msg)
                return msg

            elif event_type == "error":
                msg_text = msg.get("message", "Unknown error from server.")
                logger.error("Server transcription error: %s", msg_text)
                if on_error:
                    await on_error(msg_text)
                return None

        return None
