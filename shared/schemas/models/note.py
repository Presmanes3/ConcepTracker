from sqlmodel import SQLModel, Field, Column, Relationship
from typing import List, Optional
from datetime import datetime
from pgvector.sqlalchemy import Vector
from shared.config.embedding_config import EMBEDDING_DIMENSIONS

class Note(SQLModel, table=True):
    __tablename__ = "notes"
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str = Field(..., description="The main content of the note.")
    summary: str = Field(..., description="A concise summary of the note.")
    tags: Optional[str] = Field(default=None, description="Comma-separated string of tags.")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Taxonomy fingerprint — populated by ConceptTaxonomyAgent at ingest time.
    # Used by the LinkerAgent to apply hard domain-family guards on candidates.
    domain: Optional[str] = Field(default=None, description="Primary knowledge domain slug (e.g. 'pkm', 'devops', 'nutrition').")
    domain_family: Optional[str] = Field(default=None, description="Coarse domain family: technology | knowledge_work | life_sciences | business | arts_humanities | other.")

    # Geography: which Archipelago does this Island belong to?
    archipelago_id: Optional[int] = Field(default=None, foreign_key="archipelagos.id")

    embedding: Optional[List[float]] = Field(
        sa_column=Column(Vector(EMBEDDING_DIMENSIONS))
    )

    # Relationships
    # Using string references to avoid circular imports during definition
    links_to: List["Link"] = Relationship(
        back_populates="source_note", 
        sa_relationship_kwargs={"primaryjoin": "Note.id==Link.source_id"}
    )
    links_from: List["Link"] = Relationship(
        back_populates="target_note", 
        sa_relationship_kwargs={"primaryjoin": "Note.id==Link.target_id"}
    )
    archipelago: Optional["Archipelago"] = Relationship(back_populates="notes")
