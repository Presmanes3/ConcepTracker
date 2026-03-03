from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class LinkItem(BaseModel):
    """
    Representation of a single directed semantic connection between two notes.

    ``direction`` controls which note is the source:
      FORWARD  — new_note  → existing_note  (source=new, target=existing)
      BACKWARD — existing_note → new_note   (source=existing, target=new)

    For BACKWARD links, ``source_id`` must be set to the existing note's ID.
    ``target_id`` always holds the ID of the note on the *receiving* end of
    the arrow as stated by ``direction``.
    """

    target_id: int = Field(
        ...,
        description="ID of the note at the receiving end of the link arrow.",
    )
    relation_type: Literal["REINFORCES", "CONTRADICTS", "RELATES"] = Field(
        ...,
        description="The semantic nature of the connection.",
    )
    reason: str = Field(..., description="Short justification for the relationship.")
    direction: Literal["FORWARD", "BACKWARD"] = Field(
        default="FORWARD",
        description=(
            "FORWARD: new_note → existing_note. "
            "BACKWARD: existing_note → new_note (source_id must be set)."
        ),
    )
    source_id: Optional[int] = Field(
        default=None,
        description="For BACKWARD links: the ID of the existing note that originates the link.",
    )


class LinkerResult(BaseModel):
    """
    The collection of links discovered by the BidirectionalLinkerAgent.
    May contain both FORWARD and BACKWARD links in a single LLM call.
    """

    links: List[LinkItem] = Field(
        default_factory=list,
        description="Validated connections. Each entry specifies direction explicitly.",
    )
