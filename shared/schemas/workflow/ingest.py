from typing import List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl
from shared.schemas.agents.linker import LinkItem
from shared.schemas.agents.taxonomy import ConceptTaxonomy

class IngestState(BaseModel):
    """
    Main state for the note ingestion workflow. 
    Encapsulates input, normalization, decision making, and linking data.
    """
    # 1. Input Context
    source_type: Optional[str] = Field(
        default="manual", 
        description="The source category: manual, web, pdf, etc."
    )
    source_url: Optional[HttpUrl] = Field(
        None, 
        description="Optional URL or file path for the source."
    )
    
    # 2. Content Evolution
    content: str = Field(..., description="The current version of the note content.")
    original_content: Optional[str] = Field(
        None, 
        description="The raw uncleaned content for traceability."
    )
    summary: Optional[str] = Field(
        None, 
        description="A concise narrative summary of the note."
    )
    embedding: Optional[List[float]] = Field(
        None, 
        description="Titan v2 vector representation (1024 dimensions)."
    )
    tags: Optional[str] = Field(
        None, 
        description="Comma-separated list of normalized and enriched tags."
    )
    language: Optional[str] = Field(
        default="en", 
        description="ISO 639-1 code of the detected language."
    )
    
    # 2.5 Concept Taxonomy (pre-retrieval classifier)
    taxonomy: Optional[ConceptTaxonomy] = Field(
        None,
        description="Semantic fingerprint extracted before retrieval: domain, concept_type, is_component_of."
    )

    # 3. Decision Data (Gatekeeper)
    note_id: Optional[int] = Field(
        None, 
        description="The resulting ID after saving or for merge operations."
    )
    action: Literal["CREATE", "MERGE", "SKIP"] = Field(
        default="CREATE", 
        description="The structural decision made by the Gatekeeper."
    )
    reasoning: Optional[str] = Field(
        None, 
        description="Internal logic for the gatekeeping decision."
    )
    
    # 4. Contextual Relations (Linker)
    similar_notes: List[dict] = Field(
        default_factory=list, 
        description="Candidate notes retrieved via semantic search for comparison."
    )
    links: List[LinkItem] = Field(
        default_factory=list, 
        description="Forward semantic links (new note → existing notes)."
    )
    retrospective_links: List[dict] = Field(
        default_factory=list,
        description="Retroactive links from existing notes → new note (reverse direction)."
    )

    # 5. Geography (Archipelago Agent)
    archipelago_action: Optional[str] = Field(
        None,
        description="The decision from the Archipelago agent: CREATE_ARCHIPELAGO, CREATE_CONTINENT, JOIN, NONE."
    )
    archipelago_id: Optional[int] = Field(
        None,
        description="ID of archipelago this note was assigned to (new or existing)."
    )
    archipelago_name: Optional[str] = Field(
        None,
        description="Name of the new archipelago or continent, if one was created."
    )
    archipelago_summary: Optional[str] = Field(
        None,
        description="Synthetic summary of the archipelago."
    )

    # 6. Metadata for Traceability
    pipeline_errors: List[str] = Field(
        default_factory=list,
        description="Registry of any warnings or errors during the execution."
    )
