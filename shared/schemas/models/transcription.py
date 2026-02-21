from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Transcription(SQLModel, table=True):
    __tablename__ = "transcriptions"
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str = Field(..., description="The transcribed text.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    duration_seconds: Optional[float] = Field(default=None, description="Duration of the transcription in seconds.")
    status: str = Field(default="completed", description="Status of the transcription (e.g., completed, partial).")
    enhanced_content: Optional[str] = Field(default=None, description="The AI-enhanced transcribed text.")
    applied_enhancements: Optional[str] = Field(default=None, description="JSON string or comma-separated list of applied enhancement layers.")
