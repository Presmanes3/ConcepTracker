"""Schemas for semantic links between notes."""
from datetime import datetime
from pydantic import BaseModel, Field


class LinkConfirmRequest(BaseModel):
    """Instruction to establish a new manual or user-verified link."""
    target_id: int = Field(..., description="Destination note ID.")
    relation_type: str = Field(..., description="Link category: REINFORCES, CONTRADICTS, or RELATES.")
    reason: str = Field(..., description="Explanation for how the notes are linked.")


class LinkResponse(BaseModel):
    """Detailed metadata for a link in the graph."""
    id: int = Field(..., description="Primary identifier of the link record.")
    source_id: int = Field(..., description="Originating note ID.")
    target_id: int = Field(..., description="Receiving note ID.")
    relation_type: str = Field(..., description="Interaction mode (e.g., REINFORCES).")
    reason: str = Field(..., description="Self-documented purpose for the link.")
    created_at: datetime = Field(..., description="When the link was created.")
