from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class ArchipelagoDecision(BaseModel):
    """The clustering decision made by the Archipelago agent for a newly saved note."""

    action: Literal["CREATE_ARCHIPELAGO", "CREATE_CONTINENT", "JOIN", "NONE"] = Field(
        ...,
        description=(
            "CREATE_ARCHIPELAGO: Form a new named cluster from this note and unassigned linked notes. "
            "CREATE_CONTINENT: Promote linked archipelagos into a new continent-level cluster. "
            "JOIN: Assign this note to the best existing archipelago among the linked notes. "
            "NONE: This note remains a standalone Island."
        )
    )
    archipelago_id: Optional[int] = Field(
        default=None,
        description="If JOIN, the ID of the existing archipelago to join."
    )
    name: Optional[str] = Field(
        default=None,
        description="If CREATE_ARCHIPELAGO or CREATE_CONTINENT, the proposed name."
    )
    summary: Optional[str] = Field(
        default=None,
        description="If CREATE_ARCHIPELAGO or CREATE_CONTINENT, a synthetic 1-2 sentence description of what unifies these notes."
    )
    note_ids_to_cluster: Optional[List[int]] = Field(
        default=None,
        description="If CREATE_ARCHIPELAGO, the IDs of the unassigned linked notes to include in the new cluster (besides the current note)."
    )
    archipelago_ids_for_continent: Optional[List[int]] = Field(
        default=None,
        description="If CREATE_CONTINENT, the IDs of existing archipelagos to group under the new continent."
    )
    reasoning: str = Field(..., description="Short justification for this decision.")
