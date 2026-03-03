"""API request/response Pydantic schemas.

These are NOT the SQLModel table models from shared/schemas/models/.
They define the HTTP contract between backend and frontend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Notes ─────────────────────────────────────────────────────────────────────

class NoteIngestRequest(BaseModel):
    content: str = Field(..., description="Raw note content to ingest.")
    source_type: str = Field("manual", description="Source type: manual, web, pdf, transcription, etc.")
    source_url: Optional[str] = Field(None, description="Optional URL or file path of the source.")


class NearMissCandidate(BaseModel):
    note_id: int
    score: float
    summary: str
    tags: Optional[str] = None
    domain: Optional[str] = None


class NoteIngestResponse(BaseModel):
    note_id: Optional[int] = None
    action: str = Field(..., description="CREATE, MERGE, or SKIP.")
    reasoning: Optional[str] = None
    near_miss_candidates: List[NearMissCandidate] = Field(default_factory=list)


class NoteResponse(BaseModel):
    id: int
    content: str
    summary: str
    tags: Optional[str] = None
    created_at: datetime
    domain: Optional[str] = None
    domain_family: Optional[str] = None
    archipelago_id: Optional[int] = None


class NoteListResponse(BaseModel):
    notes: List[NoteResponse]
    total: int


# ── Links ─────────────────────────────────────────────────────────────────────

class LinkConfirmRequest(BaseModel):
    target_id: int
    relation_type: str = Field(..., description="REINFORCES, CONTRADICTS, or RELATES.")
    reason: str = Field(..., description="Human-readable reason for the link.")


class LinkResponse(BaseModel):
    id: int
    source_id: int
    target_id: int
    relation_type: str
    reason: str
    created_at: datetime


# ── Search ────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language search query.")
    limit: int = Field(10, ge=1, le=50)


class SearchResultItem(BaseModel):
    id: int
    content: str
    summary: str
    tags: Optional[str] = None
    score: Optional[float] = None
    domain: Optional[str] = None
    archipelago_id: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]


# ── Archipelagos ──────────────────────────────────────────────────────────────

class ArchipelagoResponse(BaseModel):
    id: int
    name: str
    summary: str
    type: str
    parent_id: Optional[int] = None
    needs_refresh: bool
    created_at: datetime


# ── Stats ─────────────────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost: str
    total_requests: int


# ── Config ────────────────────────────────────────────────────────────────────

class ModelPricingSchema(BaseModel):
    input: float
    output: float


class ConfigResponse(BaseModel):
    active_model_id: str
    pricing: Dict[str, ModelPricingSchema]
    is_configured: bool


class ConfigUpdateRequest(BaseModel):
    active_model_id: Optional[str] = None
    model_pricing: Optional[Dict[str, ModelPricingSchema]] = None


# ── Health ────────────────────────────────────────────────────────────────────

class ServiceStatus(BaseModel):
    name: str
    healthy: bool
    message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="overall: ok or degraded")
    services: List[ServiceStatus]


# ── Devices ───────────────────────────────────────────────────────────────────

class DeviceResponse(BaseModel):
    id: int
    name: str
    channels: int
    default: bool
    active: bool = False


class DeviceSetRequest(BaseModel):
    device_id: int


# ── Transcription ─────────────────────────────────────────────────────────────

class TranscriptionSaveRequest(BaseModel):
    content: str = Field(..., description="Raw transcribed text.")
    enhanced_content: Optional[str] = None
    duration_seconds: Optional[float] = None
    applied_enhancements: Optional[str] = None
    ingest: bool = Field(True, description="Run ingest pipeline on the transcription content.")


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    detail: Optional[Any] = None
