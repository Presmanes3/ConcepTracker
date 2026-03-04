"""Schemas for note management and ingestion."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class NoteIngestRequest(BaseModel):
    """Request to ingest raw content into the knowledge system."""
    content: str = Field(..., description="Raw text or source content to ingest.")
    source_type: str = Field(default="manual", description="Source of the note (e.g. manual, web, pdf, transcription).")
    source_url: Optional[str] = Field(default=None, description="Optional URI, URL or file path of the source.")


class NearMissCandidate(BaseModel):
    """Potential duplicate found during ingestion."""
    note_id: int = Field(..., description="Unique ID of the candidate note.")
    score: float = Field(..., description="Similarity score (0.0 to 1.0) with the new content.")
    summary: str = Field(..., description="Brief summary of the candidate's content.")
    tags: Optional[str] = Field(default=None, description="Tags associated with the candidate note.")
    domain: Optional[str] = Field(default=None, description="Subject domain of the candidate note.")


class NoteIngestResponse(BaseModel):
    """Result of an ingestion operation."""
    note_id: Optional[int] = Field(default=None, description="ID of the newly created or existing note.")
    action: str = Field(..., description="Resulting action: CREATE, MERGE, or SKIP.")
    reasoning: Optional[str] = Field(default=None, description="LLM justification for the chosen action.")
    near_miss_candidates: List[NearMissCandidate] = Field(
        default_factory=list, description="List of similar notes if merging was considered."
    )


class NoteResponse(BaseModel):
    """Detailed information about an atomic note."""
    id: int = Field(..., description="Primary identifier of the note.")
    content: str = Field(..., description="Full text content of the note.")
    summary: str = Field(..., description="LLM-generated concise summary.")
    tags: Optional[str] = Field(default=None, description="Space or comma-separated tags.")
    created_at: datetime = Field(..., description="Timestamp of creation.")
    domain: Optional[str] = Field(default=None, description="Primary subject area.")
    domain_family: Optional[str] = Field(default=None, description="Broader domain grouping.")
    archipelago_id: Optional[int] = Field(default=None, description="Parent archipelago ID if grouped.")


class NoteUpdateRequest(BaseModel):
    """Request to modify an existing note's metadata or content."""
    content: Optional[str] = Field(default=None, description="New text content.")
    summary: Optional[str] = Field(default=None, description="New LLM summary.")
    tags: Optional[str] = Field(default=None, description="Updated tags.")


class NoteEnhanceRequest(BaseModel):
    """Request to trigger professional AI enhancement for a note."""
    user_instruction: str = Field(..., description="The instruction provided by the user for the AI.")


class NoteListResponse(BaseModel):
    """Paginated list of notes."""
    notes: List[NoteResponse] = Field(..., description="Subsegment of retrieved notes.")
    total: int = Field(..., description="Total count of notes matching the filter.")
