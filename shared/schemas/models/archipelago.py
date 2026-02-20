from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, Literal
from datetime import datetime


class Archipelago(SQLModel, table=True):
    __tablename__ = "archipelagos"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(..., description="LLM-generated name for this cluster.")
    summary: str = Field(..., description="Synthetic summary of what unifies the notes in this cluster.")
    type: str = Field(default="archipelago", description="'archipelago' (Island cluster) or 'continent' (Archipelago cluster).")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Self-referential: an Archipelago can belong to a Continent (also an Archipelago with type='continent')
    parent_id: Optional[int] = Field(default=None, foreign_key="archipelagos.id")

    # Dirty-flag fields for lazy refresh (incremented on each new assignment, reset by `ct refresh`)
    islands_since_refresh: int = Field(default=0, description="Notes added since last summary refresh.")
    needs_refresh: bool = Field(default=False, description="True when summary is considered stale.")

    # Notes that belong to this archipelago
    notes: List["Note"] = Relationship(back_populates="archipelago")
