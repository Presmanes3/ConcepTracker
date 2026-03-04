"""Common API schemas and base models."""
from typing import Any, Optional, List
from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str = Field(..., description="Human-readable message.")
    detail: Optional[Any] = Field(None, description="Optional diagnostic details.")


class StatsResponse(BaseModel):
    """Usage statistics response."""
    total_tokens: int = Field(..., description="Total LLM tokens consumed.")
    prompt_tokens: int = Field(..., description="Tokens in the prompt.")
    completion_tokens: int = Field(..., description="Tokens in the completion.")
    total_cost: str = Field(..., description="Formatted currency string of the total cost.")
    total_requests: int = Field(..., description="Total count of API requests.")


class ServiceStatus(BaseModel):
    """Status information for a sub-service."""
    name: str = Field(..., description="Service identifier.")
    healthy: bool = Field(..., description="True if the service is operational.")
    message: Optional[str] = Field(None, description="Optional status or error message.")


class HealthResponse(BaseModel):
    """System health check response."""
    status: str = Field(..., description="Overall status: ok or degraded.")
    services: List[ServiceStatus] = Field(..., description="List of individual service statuses.")
