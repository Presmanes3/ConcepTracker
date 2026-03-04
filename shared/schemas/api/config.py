"""Schemas for backend and model configuration."""
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ModelPricingSchema(BaseModel):
    """Cost breakdown for a specific LLM model configuration."""
    input: float = Field(..., description="USD per million input tokens.")
    output: float = Field(..., description="USD per million completion tokens.")


class ConfigResponse(BaseModel):
    """Full operational configuration state."""
    active_model_id: str = Field(..., description="Global LLM model identifier (e.g., titan-v2).")
    pricing: Dict[str, ModelPricingSchema] = Field(..., description="Mapping of provider IDs to pricing units.")
    is_configured: bool = Field(..., description="True if the backend has successfully initialized.")
    auto_pause_seconds: int = Field(default=0, description="Inactivity timeout for audio ingestion.")


class ConfigUpdateRequest(BaseModel):
    """Request to modify backend settings."""
    active_model_id: Optional[str] = Field(default=None, description="Update the primary model ID.")
    model_pricing: Optional[Dict[str, ModelPricingSchema]] = Field(default=None, description="Update pricing lookup table.")
