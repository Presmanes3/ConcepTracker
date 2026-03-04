"""GET /stats — token usage and cost analytics."""
from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_cost_service
from shared.schemas.api.common import StatsResponse

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    days: int = Query(0, ge=0),
    hours: int = Query(0, ge=0),
    cost_service=Depends(get_cost_service),
):
    data = cost_service.get_stats(days=days, hours=hours)
    return StatsResponse(
        total_tokens=data["total_tokens"],
        prompt_tokens=data["prompt_tokens"],
        completion_tokens=data["completion_tokens"],
        total_cost=data["total_cost"],
        total_requests=data["total_requests"],
    )
