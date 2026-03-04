"""Transcription router — REST save endpoint + WebSocket streaming.

WebSocket protocol: see .github/skills/fastapi_architecture/SKILL.md §WebSocket Endpoint
AWS SDK:           amazon_transcribe.client.TranscribeStreamingClient (async)
"""
import asyncio
import json
import logging
import os

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from src.agents.markdown_formatter_agent import MarkdownFormatterAgent
from src.agents.normalizer_agent import NormalizerAgent
from src.api.dependencies import get_transcription_repo
from shared.schemas.api.notes import NoteIngestResponse
from shared.schemas.api.transcription import (
    TranscriptionEnhanceRequest,
    TranscriptionEnhanceResponse,
    TranscriptionSaveRequest,
)
from src.repository.transcription_repository import transcription_repository
from src.workflows.ingest_workflow import ingest_graph
from src.workflows.transcription_workflow import transcription_workflow
from shared.schemas.models.transcription import Transcription
from shared.schemas.workflow.ingest import IngestState
from shared.schemas.workflow.transcription import TranscriptionEnhancementState

try:
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    _TRANSCRIBE_AVAILABLE = True
except ImportError:
    TranscribeStreamingClient = None  # type: ignore[assignment,misc]
    TranscriptResultStreamHandler = object  # type: ignore[assignment,misc]
    _TRANSCRIBE_AVAILABLE = False

logger = logging.getLogger(__name__)
router = APIRouter()


# ── REST: save a completed transcription and optionally ingest it ──────────────

@router.post("/transcriptions", response_model=NoteIngestResponse)
async def save_transcription(
    body: TranscriptionSaveRequest,
    transcription_repo=Depends(get_transcription_repo),
):
    # Persist the raw transcription record
    record = Transcription(
        content=body.content,
        enhanced_content=body.enhanced_content,
        duration_seconds=body.duration_seconds,
        applied_enhancements=body.applied_enhancements,
        status="completed",
    )
    transcription_repo.save_transcription(record)

    if not body.ingest:
        return NoteIngestResponse(action="SKIP", reasoning="ingest=false, transcription saved only.")

    content = body.enhanced_content or body.content
    initial_state = IngestState(content=content, source_type="transcription")  # type: ignore[call-arg]
    result: dict = await asyncio.to_thread(ingest_graph.invoke, initial_state)  # type: ignore[arg-type]

    return NoteIngestResponse(
        note_id=result.get("note_id"),
        action=result.get("action", "CREATE"),
        reasoning=result.get("reasoning"),
    )


# ── REST: enhance a transcription text with the AI pipeline ─────────────────────

@router.post("/transcriptions/enhance", response_model=TranscriptionEnhanceResponse)
async def enhance_transcription(body: TranscriptionEnhanceRequest) -> TranscriptionEnhanceResponse:
    """Run the AI enhancement pipeline on raw transcription text and return the result."""
    context_text = (
        f"[USER INSTRUCTION: {body.user_prompt}]\n\n{body.raw_text}"
        if body.user_prompt
        else body.raw_text
    )
    initial = TranscriptionEnhancementState(
        raw_text=body.raw_text,
        current_text=context_text,
        applied_layers=[],
        action_items=None,
        error=None,
        user_prompt=body.user_prompt,
    )
    final: dict = await asyncio.to_thread(transcription_workflow.invoke, initial)  # type: ignore[arg-type]

    if final.get("error"):
        return TranscriptionEnhanceResponse(
            enhanced_text=body.raw_text,
            applied_layers=[],
            error=final["error"],
        )

    return TranscriptionEnhanceResponse(
        enhanced_text=final.get("current_text", body.raw_text),
        applied_layers=final.get("applied_layers", []),
    )


# ── WebSocket: real-time audio streaming → live transcript ────────────────────

@router.websocket("/ws/transcription")
async def ws_transcription(websocket: WebSocket):
    """
    Protocol (see .github/skills/fastapi_architecture/SKILL.md §WebSocket Endpoint):
      1. Client connects.
      2. Client may send {"type": "config", "device_id": <int>}  (optional).
      3. Client streams raw PCM bytes as binary frames.
      4. Server echoes {"type": "partial"|"final", "text": "..."} text frames.
      5. Client sends {"type": "stop"} to end the audio stream.
      6. Server runs enhancement pipeline + ingest, then sends {"type": "done", ...}.
    """
    await websocket.accept()

    transcript_segments: list[str] = []
    duration_seconds: float = 0.0

    if not _TRANSCRIBE_AVAILABLE:
        await websocket.send_text(
            json.dumps({"type": "error", "message": "amazon_transcribe SDK not installed on backend."})
        )
        await websocket.close()
        return

    region = os.getenv("AWS_REGION", "eu-west-1")

    try:
        transcribe_client = TranscribeStreamingClient(region=region)  # type: ignore[misc]
        aws_stream = await transcribe_client.start_stream_transcription(
            language_code="es-ES",
            media_sample_rate_hz=16000,
            media_encoding="pcm",
        )
    except Exception as exc:
        logger.exception("Failed to open AWS Transcribe stream: %s", exc)
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        await websocket.close()
        return

    # ── Transcript event handler ───────────────────────────────────────────────
    class _WSTranscriptHandler(TranscriptResultStreamHandler):  # type: ignore[misc]
        async def handle_transcript_event(self, transcript_event) -> None:
            for result in transcript_event.transcript.results:
                for alt in (result.alternatives or []):
                    if result.is_partial:
                        await websocket.send_text(
                            json.dumps({"type": "partial", "text": alt.transcript})
                        )
                    else:
                        await websocket.send_text(
                            json.dumps({"type": "final", "text": alt.transcript})
                        )
                        transcript_segments.append(alt.transcript)

    handler = _WSTranscriptHandler(aws_stream.output_stream)

    # ── Audio writer: forwards client binary frames to AWS Transcribe ──────────
    async def _write_audio() -> None:
        nonlocal duration_seconds
        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message and message["bytes"]:
                    chunk: bytes = message["bytes"]
                    duration_seconds += len(chunk) / (2 * 16000)  # 16-bit 16 kHz mono
                    await aws_stream.input_stream.send_audio_event(audio_chunk=chunk)

                elif "text" in message and message["text"]:
                    try:
                        ctrl = json.loads(message["text"])
                    except json.JSONDecodeError:
                        continue
                    if ctrl.get("type") == "stop":
                        break
                    # "config" and other control frames are accepted silently
        finally:
            await aws_stream.input_stream.end_stream()

    try:
        write_task = asyncio.create_task(_write_audio())
        handler_task = asyncio.create_task(handler.handle_events())
        await asyncio.gather(write_task, handler_task)
    except WebSocketDisconnect:
        logger.info("Client disconnected during transcription.")
        return
    except Exception as exc:
        logger.exception("Transcription stream error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
        return

    # ── Post-processing: enhancement pipeline ─────────────────────────────────
    raw_content = " ".join(transcript_segments).strip()
    if not raw_content:
        await websocket.send_text(json.dumps({"type": "done", "note_id": None, "content": ""}))
        return

    enhanced = raw_content
    applied: list[str] = []
    try:
        # NormalizerAgent uses IngestState
        norm_result = NormalizerAgent().run(IngestState(content=raw_content))  # type: ignore[call-arg, arg-type]
        if isinstance(norm_result, dict):
            enhanced = norm_result.get("content", raw_content)
        applied.append("normalizer")

        # MarkdownFormatterAgent uses TranscriptionEnhancementState (TypedDict)
        fmt_state: TranscriptionEnhancementState = {
            "raw_text": raw_content,
            "current_text": enhanced,
            "applied_layers": [],
            "action_items": None,
            "error": None,
            "user_prompt": None,
        }
        fmt_result = MarkdownFormatterAgent().run(fmt_state)
        if fmt_result and not fmt_result.get("error"):
            enhanced = fmt_result.get("current_text", enhanced)
            applied.append("markdown_formatter")

    except Exception as exc:
        logger.warning("Enhancement pipeline failed: %s", exc)

    # Persist transcription record
    rec = Transcription(
        content=raw_content,
        enhanced_content=enhanced,
        duration_seconds=duration_seconds,
        applied_enhancements=",".join(applied),
        status="completed",
    )
    transcription_repository.save_transcription(rec)

    # Ingest enhanced content into note pipeline
    ingest_state = IngestState(content=enhanced, source_type="transcription")  # type: ignore[call-arg]
    try:
        result: dict = await asyncio.to_thread(ingest_graph.invoke, ingest_state)  # type: ignore[arg-type]
    except Exception as exc:
        logger.exception("Ingest pipeline failed after transcription: %s", exc)
        await websocket.send_text(json.dumps({"type": "error", "message": f"Ingest failed: {exc}"}))
        return

    await websocket.send_text(
        json.dumps(
            {
                "type": "done",
                "note_id": result.get("note_id"),
                "action": result.get("action", "CREATE"),
                "content": enhanced,
            }
        )
    )
