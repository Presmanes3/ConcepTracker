from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class InferenceLog(SQLModel, table=True):
    __tablename__ = "inference_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: str = Field(..., description="The ID of the model used (e.g., Nova Micro).")
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    task: str = Field(..., description="Task category: normalization, gatekeeping, linking, etc.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
