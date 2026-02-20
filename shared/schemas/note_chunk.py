from pydantic import BaseModel, Field
from typing import List

class NoteChunk(BaseModel):
    """
    Represents a granular segment (chunk) of a note with its corresponding 
    vector embedding for semantic operations.
    """
    content: str = Field(
        ..., 
        description="The actual text content of the fragment."
    )
    embedding: List[float] = Field(
        default_factory=list, 
        description="The high-dimensional vector representation for similarity search."
    )
    index: int = Field(
        ..., 
        description="The positional order of this chunk within the source note."
    )
