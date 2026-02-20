from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

class LLMNormalizerOutput(BaseModel):
    """
    Highly structured schema for the LLM response during normalization.
    """
    clean_message: Optional[str] = Field(
        default=None,
        description="Sanitized Markdown content, preserving semantic structure and removing noise."
    )
    normalized_title: str = Field(
        ...,
        description="A concise and descriptive title for the note (max 10 words)."
    )
    normalized_tags: List[str] = Field(
        default_factory=list,
        description="Standardized, lowercased, and LLM-enriched tags."
    )
    detected_language: str = Field(
        ...,
        description="ISO 639-1 language code (e.g., 'en', 'es')."
    )
    summary: str = Field(
        ...,
        description="A 2-3 sentence summary explaining the core idea of the note."
    )
    key_concepts: List[str] = Field(
        default_factory=list,
        description="Identified entities, abstract ideas, or main topics."
    )
    action_items: List[str] = Field(
        default_factory=list,
        description="Implied actions or next steps found in the content."
    )
