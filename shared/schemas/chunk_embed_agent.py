from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

from shared.schemas.note_chunk import NoteChunk

class ChunkEmbedAgentInput(BaseModel):
    """
    Input schema for the ChunkEmbedAgent, derived from normalized data.
    """
    clean_message: str = Field(..., description="The sanitized Markdown content to be chunked.")
    normalized_tags: List[str] = Field(default_factory=list)
    source_url: Optional[HttpUrl] = None

class ChunkEmbedAgentOutput(BaseModel):
    """
    Internal output schema for the ChunkEmbedAgent's processing.
    """
    chunks: List[NoteChunk] = Field(default_factory=list)
    is_indexed: bool = False
