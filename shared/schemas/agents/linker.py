from pydantic import BaseModel, Field
from typing import List, Literal

class LinkItem(BaseModel):
    """
    Representation of a single directed semantic connection between two notes.
    """
    target_id: int = Field(..., description="The ID of the note to connect to.")
    relation_type: Literal["REINFORCES", "CONTRADICTS", "RELATES"] = Field(
        ..., 
        description="The semantic nature of the connection."
    )
    reason: str = Field(..., description="Short justification for the relationship.")

class LinkerResult(BaseModel):
    """
    The collection of links discovered by the Linker agent.
    """
    links: List[LinkItem] = Field(
        default_factory=list, 
        description="A list of validated connections to existing notes."
    )
