"""Synchronous HTTP client for the ConcepTracker FastAPI backend.

Usage::

    from src.cli.client import ConcepTrackerClient

    client = ConcepTrackerClient()
    notes  = client.list_notes(limit=20)
    result = client.ingest_note(content="...", source_type="manual")

All methods raise ``httpx.HTTPStatusError`` on non-2xx responses.
Callers (interactors) are responsible for handling those exceptions.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional

import httpx

# Shared schemas used for type hints and response validation
from shared.schemas.api.notes import (
    NoteIngestRequest,
    NoteIngestResponse,
    NoteResponse,
    NoteUpdateRequest,
)
from shared.schemas.api.search import SearchRequest, SearchResponse
from shared.schemas.api.links import LinkConfirmRequest, LinkResponse
from shared.schemas.api.archipelagos import ArchipelagoResponse
from shared.schemas.api.transcription import (
    DeviceResponse,
    DeviceSetRequest,
    TranscriptionEnhanceRequest,
    TranscriptionEnhanceResponse,
    TranscriptionSaveRequest,
)
from shared.schemas.api.config import ConfigResponse, ConfigUpdateRequest
from shared.schemas.api.common import HealthResponse, MessageResponse, StatsResponse

_DEFAULT_BASE_URL = "http://localhost:8000"
_DEFAULT_TIMEOUT = 120.0  # seconds — ingest/search can be slow (LLM calls)


class ConcepTrackerClient:
    """Thin httpx wrapper around the ConcepTracker REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self._base_url = (
            base_url
            or os.environ.get("CONCEPTRACKER_API_URL", _DEFAULT_BASE_URL)
        ).rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def _get(self, path: str, **params) -> Any:
        resp = self._client.get(path, params={k: v for k, v in params.items() if v is not None})
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: Any = None) -> Any:
        resp = self._client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: Any = None) -> Any:
        resp = self._client.put(path, json=body)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> Any:
        resp = self._client.delete(path)
        resp.raise_for_status()
        return resp.json()

    # ── System ────────────────────────────────────────────────────────────────

    def get_health(self) -> HealthResponse:
        return HealthResponse.model_validate(self._get("/health"))

    def run_init(self) -> MessageResponse:
        return MessageResponse.model_validate(self._post("/init"))
    def reset_db(self) -> MessageResponse:
        """Drop all tables and recreate them. All data will be lost."""
        return MessageResponse.model_validate(self._post("/admin/reset-db"))
    # ── Notes ─────────────────────────────────────────────────────────────────

    def list_notes(
        self, limit: int = 20, tag: Optional[str] = None
    ) -> List[NoteResponse]:
        data = self._get("/notes", limit=limit, tag=tag)
        return [NoteResponse.model_validate(n) for n in data]

    def get_note(self, note_id: int) -> NoteResponse:
        return NoteResponse.model_validate(self._get(f"/notes/{note_id}"))

    def update_note(self, note_id: int, content: Optional[str] = None) -> NoteResponse:
        """Update an existing note's content and trigger re-normalization."""
        body = NoteUpdateRequest(content=content)
        data = self._put(f"/notes/{note_id}", body=body.model_dump(exclude_none=True))
        return NoteResponse.model_validate(data)


    def ingest_note(
        self,
        content: str,
        source_type: str = "manual",
        source_url: Optional[str] = None,
    ) -> NoteIngestResponse:
        body = NoteIngestRequest(
            content=content,
            source_type=source_type,
            source_url=source_url,
        )
        return NoteIngestResponse.model_validate(
            self._post("/notes", body.model_dump(exclude_none=True))
        )

    def confirm_links(
        self, note_id: int, links: List[LinkConfirmRequest]
    ) -> MessageResponse:
        return MessageResponse.model_validate(
            self._post(
                f"/notes/{note_id}/links",
                [lnk.model_dump() for lnk in links],
            )
        )

    def delete_note(self, note_id: int) -> MessageResponse:
        return MessageResponse.model_validate(self._delete(f"/notes/{note_id}"))

    # ── Links ─────────────────────────────────────────────────────────────────

    def get_links_for_note(self, note_id: int) -> List[LinkResponse]:
        data = self._get(f"/notes/{note_id}/links")
        return [LinkResponse.model_validate(lnk) for lnk in data]

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, limit: int = 10) -> SearchResponse:
        body = SearchRequest(query=query, limit=limit)
        return SearchResponse.model_validate(
            self._post("/search", body.model_dump())
        )

    # ── Archipelagos ──────────────────────────────────────────────────────────

    def list_archipelagos(self) -> List[ArchipelagoResponse]:
        data = self._get("/archipelagos")
        return [ArchipelagoResponse.model_validate(a) for a in data]

    def get_archipelago(self, arch_id: int) -> ArchipelagoResponse:
        return ArchipelagoResponse.model_validate(self._get(f"/archipelagos/{arch_id}"))

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self, days: int = 0, hours: int = 0) -> StatsResponse:
        return StatsResponse.model_validate(
            self._get("/stats", days=days or None, hours=hours or None)
        )

    # ── Config ────────────────────────────────────────────────────────────────

    def get_config(self) -> ConfigResponse:
        return ConfigResponse.model_validate(self._get("/config"))

    def update_config(self, body: ConfigUpdateRequest) -> ConfigResponse:
        return ConfigResponse.model_validate(
            self._put("/config", body.model_dump(exclude_none=True))
        )

    # ── Devices ───────────────────────────────────────────────────────────────

    def list_devices(self) -> List[DeviceResponse]:
        data = self._get("/devices")
        return [DeviceResponse.model_validate(d) for d in data]

    def set_active_device(self, device_id: int) -> MessageResponse:
        body = DeviceSetRequest(device_id=device_id)
        return MessageResponse.model_validate(
            self._put("/devices/active", body.model_dump())
        )

    # ── Transcription ─────────────────────────────────────────────────────────

    def save_transcription(self, body: TranscriptionSaveRequest) -> NoteIngestResponse:
        return NoteIngestResponse.model_validate(
            self._post("/transcriptions", body.model_dump(exclude_none=True))
        )

    def enhance_transcription(
        self,
        raw_text: str,
        user_prompt: Optional[str] = None,
    ) -> TranscriptionEnhanceResponse:
        """Run the server-side AI enhancement pipeline on raw transcription text."""
        body = TranscriptionEnhanceRequest(raw_text=raw_text, user_prompt=user_prompt)
        return TranscriptionEnhanceResponse.model_validate(
            self._post("/transcriptions/enhance", body.model_dump(exclude_none=True))
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
