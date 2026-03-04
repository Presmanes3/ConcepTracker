"""
Enhancement Workflow Schema — state model for AI-driven note professional utility.
"""
from typing import Optional
from pydantic import BaseModel, Field

class EnhancementState(BaseModel):
    """State for the note enhancement/refactoring workflow."""
    
    note_id: int = Field(..., description="The ID of the note being enhanced")
    current_content: str = Field(..., description="The original markdown content of the note")
    user_instruction: str = Field(default="Refactor for professional clarity and structure", description="The instruction provided by the user for the AI")
    
    enhanced_content: Optional[str] = Field(default=None, description="The resulting content after AI processing")
    suggested_tags: list[str] = Field(default_factory=list, description="New tags suggested by the AI based on the content")
    
    error: Optional[str] = Field(default=None, description="Error message if any step in the workflow fails")
    is_complete: bool = Field(default=False, description="Whether the workflow has finished processing")
