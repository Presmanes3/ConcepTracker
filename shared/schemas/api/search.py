"""Schemas for semantic search operations."""
from typing import List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Natural language search query and settings."""
    query: str = Field(..., description="The high-level user question or keywords.")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of hits to return.")


class SearchResultItem(BaseModel):
    """Single hit in a search result set."""
    id: int = Field(..., description="Target note identifier.")
    content: str = Field(..., description="Matching note's content.")
    summary: str = Field(..., description="Summary of the matching note.")
    tags: Optional[str] = Field(default=None, description="Topic-based tags of the note.")
    score: Optional[float] = Field(default=None, description="Similarity score calculated by the search engine.")
    domain: Optional[str] = Field(default=None, description="Contextual domain of the hit.")
    archipelago_id: Optional[int] = Field(default=None, description="Parent archipelago grouping ID.")


class SearchResponse(BaseModel):
    """Encapsulated search results."""
    query: str = Field(..., description="Echoed input query after expansion or cleaning.")
    results: List[SearchResultItem] = Field(..., description="Ranked list of hits found.")
