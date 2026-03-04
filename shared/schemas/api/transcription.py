"""Schemas for audio transcription and enhancement."""
from typing import List, Optional
from pydantic import BaseModel, Field


class DeviceResponse(BaseModel):
    """Audio input hardware information."""
    id: int = Field(..., description="System device index.")
    name: str = Field(..., description="Human-readable device label.")
    channels: int = Field(..., description="Available audio input channels.")
    default: bool = Field(..., description="True if the system default.")
    active: bool = Field(default=False, description="True if currently recording.")


class DeviceSetRequest(BaseModel):
    """Request to change the active recording device."""
    device_id: int = Field(..., description="System device index to activate.")


class TranscriptionSaveRequest(BaseModel):
    """Request to save or ingest external transcription text."""
    content: str = Field(..., description="Original transcribed output.")
    enhanced_content: Optional[str] = Field(default=None, description="Cleaned or LLM-improved text.")
    duration_seconds: Optional[float] = Field(default=None, description="Audio length in seconds.")
    applied_enhancements: Optional[str] = Field(default=None, description="Comma-separated cleaning tasks applied.")
    ingest: bool = Field(default=True, description="Run atomic note ingestion after saving.")


class TranscriptionEnhanceRequest(BaseModel):
    """Instruction to clean or restructure raw transcription."""
    raw_text: str = Field(..., description="Noisy raw text from the ASR system.")
    user_prompt: Optional[str] = Field(default=None, description="Optional custom instruction (e.g., 'keep medical terms').")


class TranscriptionEnhanceResponse(BaseModel):
    """Result of an enhancement workflow."""
    enhanced_text: str = Field(..., description="Final clean version of the text.")
    applied_layers: List[str] = Field(..., description="Sequential processing steps taken.")
    error: Optional[str] = Field(default=None, description="Failure reason if partial.")
