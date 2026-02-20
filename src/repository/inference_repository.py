from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import select, func
from src.utils.db import get_session

# Modular Schema Import
from shared.schemas.models.inference_log import InferenceLog

class InferenceRepository:
    """
    Repository for managing audit logs and cost statistics of AI inference.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InferenceRepository, cls).__new__(cls)
        return cls._instance

    def save_log(self, log: InferenceLog) -> InferenceLog:
        """Saves an inference trace (cost, tokens, task) to the audit log."""
        with get_session() as session:
            session.add(log)
            session.commit()
            session.refresh(log)
            return log

    def get_stats(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Calculates token breakdown and estimated costs for a given period."""
        with get_session() as session:
            statement = select(
                func.sum(InferenceLog.total_tokens),
                func.sum(InferenceLog.prompt_tokens),
                func.sum(InferenceLog.completion_tokens),
                func.sum(InferenceLog.cost_usd),
                func.count(InferenceLog.id)
            )
            if since:
                statement = statement.where(InferenceLog.created_at >= since)
            
            results = session.exec(statement).first()
            return {
                "total_tokens": results[0] or 0,
                "prompt_tokens": results[1] or 0,
                "completion_tokens": results[2] or 0,
                "total_cost": float(results[3] or 0.0),
                "total_requests": results[4] or 0
            }

inference_repository = InferenceRepository()
