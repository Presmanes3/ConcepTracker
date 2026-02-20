from pydantic import BaseModel, Field


class GeoNamerOutput(BaseModel):
    """Structured output for the GeoNamerAgent (archipelago or continent naming)."""

    name: str = Field(
        ...,
        description="Short, evocative name for the cluster (3-5 words, title-case)."
    )
    summary: str = Field(
        ...,
        description="One-sentence synthesis of what conceptually unifies this group."
    )
