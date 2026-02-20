from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional

class Link(SQLModel, table=True):
    __tablename__ = "links"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="notes.id")
    target_id: int = Field(foreign_key="notes.id")
    relation_type: str = Field(..., description="Type of semantic relation: REINFORCES, CONTRADICTS, RELATES")
    reason: str = Field(..., description="Reasoning behind this semantic link.")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    # Note: Using string references if Note is not imported yet
    source_note: "Note" = Relationship(
        back_populates="links_to", 
        sa_relationship_kwargs={"foreign_keys": "[Link.source_id]"}
    )
    target_note: "Note" = Relationship(
        back_populates="links_from", 
        sa_relationship_kwargs={"foreign_keys": "[Link.target_id]"}
    )
