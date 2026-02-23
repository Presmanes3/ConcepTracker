"""
_transcription_async.py — async audio pipeline for live transcription.

Extracted from src/cli/commands/live_transcription.py.
Consumed by TranscriptionInteractor; not meant to be used directly by commands.

Exports:
    start_transcription(device_id, state) — async coroutine
    HAS_TRANSCRIBE_DEPS                   — bool, False if deps missing
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import time
from concurrent.futures import InvalidStateError as ConcurrentInvalidStateError

from rich.console import Console

from src.cli.screen import console

# ── Optional dependency guard ──────────────────────────────────────────────────

try:
    import sounddevice  # noqa: F401

    # Monkey-patch AwsCrtHttpResponse._on_body to silence AWS SDK cancellation noise
    import amazon_transcribe.httpsession
    _target = getattr(amazon_transcribe.httpsession, "AwsCrtHttpResponse", None)
    if _target:
        _original_on_body = _target._on_body

        def _safe_on_body(self, chunk: bytes, **kwargs):
            try:
                _original_on_body(self, chunk, **kwargs)
            except ConcurrentInvalidStateError:
                pass

        _target._on_body = _safe_on_body

    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    HAS_TRANSCRIBE_DEPS = True

except ImportError:
    HAS_TRANSCRIBE_DEPS = False
    TranscriptResultStreamHandler = object  # type: ignore[assignment, misc]
    TranscriptEvent = None  # type: ignore[assignment]


# ── AWS Handler ────────────────────────────────────────────────────────────────

class _StreamHandler(TranscriptResultStreamHandler):  # type: ignore[misc]
    """
    Bridge between AWS TranscribeStreamingClient events and LiveTranscriptionView.
    """

    def __init__(self, stream, view):
        super().__init__(stream)
        self._view = view

    async def handle_transcript_event(self, transcript_event):
        for result in transcript_event.transcript.results:
            for alt in result.alternatives:
                if result.is_partial:
                    self._view.set_partial(alt.transcript)
                else:
                    self._view.append_final(alt.transcript)


# ── Audio pipeline ─────────────────────────────────────────────────────────────

async def _mic_stream(device_id: int):
    loop = asyncio.get_event_loop()
    input_queue: asyncio.Queue = asyncio.Queue()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

    stream = sounddevice.RawInputStream(
        device=device_id,
        channels=1,
        samplerate=16000,
        callback=callback,
        blocksize=1024 * 2,
        dtype="int16",
    )
    with stream:
        while True:
            try:
                indata, status = await asyncio.wait_for(input_queue.get(), timeout=1.0)
                yield indata, status
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break


async def _write_chunks(stream, device_id: int):
    async for chunk, _status in _mic_stream(device_id):
        await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()


# ── Public coroutine ───────────────────────────────────────────────────────────

async def start_transcription(device_id: int, state: dict) -> None:
    """
    Run a single transcription session, updating `state` in place.
    """
    from src.cli.screens.recording_screen import RecordingScreen
    from src.cli.screen import TextualBridgeApp

    loop = asyncio.get_running_loop()

    def _handle_exception(loop, context):
        msg = context.get("exception", context["message"])
        if "InvalidStateError" in str(msg) or "CANCELLED" in str(msg) or "exit" in str(msg):
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(_handle_exception)

    region = os.getenv("AWS_REGION", "eu-west-1")
    client = TranscribeStreamingClient(region=region)
    stream = await client.start_stream_transcription(
        language_code="es-ES",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    screen = RecordingScreen(
        console,
        initial_duration=state.get("duration", 0.0),
    )
    # Pre-populate with any existing transcript from a previous segment
    for segment in state.get("transcript", []):
        screen.full_transcript = [*screen.full_transcript, segment]

    app = TextualBridgeApp(screen)
    handler = _StreamHandler(stream.output_stream, screen)

    try:
        # Run Textual app and Audio tasks in parallel
        # We use wait with FIRST_COMPLETED so that when the screen exits, we stop the loop.
        tasks = [
            asyncio.create_task(app.run_async()),
            asyncio.create_task(_write_chunks(stream, device_id)),
            asyncio.create_task(handler.handle_events()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Cancel any pending tasks (audio chunks/streaming)
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    except Exception as exc:
        if "InvalidStateError" not in str(exc) and "exit" not in str(exc):
            console.print(f"[red]Error during transcription: {exc}[/red]")
    finally:
        # Ensure we always update state
        state["transcript"] = screen.full_transcript
        state["duration"]   = screen.elapsed_seconds
        state["action"]     = getattr(screen, "result", "pause")
