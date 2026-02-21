from pydantic import BaseModel, Field
from typing import List

class TagRecommendations(BaseModel):
    """Schema for AI-generated tag recommendations."""
    tags: List[str] = Field(
        description="A list of 3 to 5 concise, professional tags relevant to the note's content.",
        min_items=1,
        max_items=5
    )
