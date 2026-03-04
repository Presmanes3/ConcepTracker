"""Schemas for Archipelago groupings."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ArchipelagoResponse(BaseModel):
    """Container for a group of semantically related notes."""
    id: int = Field(..., description="Unique archipelago identifier.")
    name: str = Field(..., description="LLM-generated name for the grouping.")
    summary: str = Field(..., description="Core consensus or theme of the group.")
    type: str = Field(..., description="Classification (e.g., ISLAND, OCEAN).")
    parent_id: Optional[int] = Field(default=None, description="Identifier of the containing group.")
    needs_refresh: bool = Field(..., description="True if the group metadata is outdated.")
    created_at: datetime = Field(..., description="Timestamp of the grouping calculation.")
