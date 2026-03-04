"""
Enhancement Agent Schema — structured output for the enhancement process.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class LLMEnhancementOutput(BaseModel):
    """Structured output from the professional enhancement agent."""
    
    enhanced_content: str = Field(..., description="The professionally refactored markdown content.")
    suggested_tags: List[str] = Field(default_factory=list, description="A list of tags that fit the new content.")
    reasoning: str = Field(..., description="Brief explanation of the changes made for professional clarity.")
