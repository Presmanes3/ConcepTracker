from pydantic import BaseModel, Field
from typing import Dict

class ModelPricing(BaseModel):
    """Pricing details for a specific AI model."""
    input: float = Field(0.0, description="Cost per 1,000,000 (1M) input tokens (USD).")
    output: float = Field(0.0, description="Cost per 1,000,000 (1M) output tokens (USD).")

class AppSettings(BaseModel):
    """Root configuration for non-sensitive application settings."""
    pricing: Dict[str, ModelPricing] = Field(default_factory=dict)
    active_model_id: str = Field("eu.amazon.nova-micro-v1:0", description="Currently active model ID.")
