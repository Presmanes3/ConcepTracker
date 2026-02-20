from pydantic import BaseModel, Field
from typing import List, Optional

class NoteChunk(BaseModel):
    id: Optional[int] = None
    note_id: Optional[int] = None
    content: str
    embedding: Optional[List[float]] = None

class ChunkEmbedResult(BaseModel):
    chunks: List[NoteChunk] = Field(default_factory=list)
    is_indexed: bool = False
