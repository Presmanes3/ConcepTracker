import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Repository-only data access
from src.repository.inference_repository import inference_repository
from src.repository.config_repository import config_repository
from shared.schemas.models.inference_log import InferenceLog

class CostService:
    """
    Service for calculating and auditing the financial cost of AI operations.
    Relies on ConfigRepository for SSoT on pricing.
    """
    @property
    def is_configured(self) -> bool:
        """Proxies to ConfigRepository's configuration check."""
        return config_repository.is_configured

    def log_inference(self, model_id: str, prompt_tokens: int, completion_tokens: int, task: str) -> float:
        """Calculates USD cost (if configured in config_repository) and stores audit log."""
        settings = config_repository.get_settings()
        pricing_data = settings.pricing.get(model_id)

        # Input/Output prices in ConfigRepository are now per 1M tokens
        input_p = pricing_data.input if pricing_data else 0.0
        output_p = pricing_data.output if pricing_data else 0.0
        
        cost = ( (prompt_tokens / 1_000_000) * input_p ) + \
               ( (completion_tokens / 1_000_000) * output_p )

        log = InferenceLog(
            model_id=model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            task=task
        )
        inference_repository.save_log(log)
        return cost

    def get_stats(self, days: int = 0, hours: int = 0) -> Dict[str, Any]:
        """Retrieves aggregated usage statistics from the database."""
        since = None
        if days > 0 or hours > 0:
            since = datetime.utcnow() - timedelta(days=days, hours=hours)
        
        results = inference_repository.get_stats(since=since)
        
        return {
            "total_tokens": results["total_tokens"] or 0,
            "prompt_tokens": results["prompt_tokens"] or 0,
            "completion_tokens": results["completion_tokens"] or 0,
            "total_cost": f"{results['total_cost'] or 0.0:.6f}",
            "total_requests": results['total_requests'] or 0
        }

    def get_last_session_cost(self) -> Dict[str, Any]:
        """Estimates the cost of operations performed in the last 2 minutes."""
        since = datetime.utcnow() - timedelta(minutes=2)
        results = inference_repository.get_stats(since=since)
        
        return {
            "total": results["total_tokens"] or 0,
            "input": results["prompt_tokens"] or 0,
            "output": results["completion_tokens"] or 0,
            "cost": f"{results['total_cost'] or 0.0:.6f}"
        }

cost_service = CostService()
