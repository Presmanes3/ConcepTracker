from pydantic import BaseModel, Field
from typing import Optional, Literal

class GatekeeperResult(BaseModel):
    """
    Schema for the Gatekeeper's decision on a new note.
    """
    action: Literal["CREATE", "MERGE", "SKIP"] = Field(
        ..., 
        description="The action to take for this note based on similarity analysis."
    )
    note_id: Optional[int] = Field(
        None, 
        description="The ID of the existing note if the action is MERGE or SKIP."
    )
    reasoning: Optional[str] = Field(
        None, 
        description="The LLM's justification for the decision."
    )
    updated_summary: Optional[str] = Field(
        None, 
        description="A synthesized summary if the action is MERGE."
    )
