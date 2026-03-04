"""GET /health — runs health checks for all registered services."""
from fastapi import APIRouter, Depends

from src.api.dependencies import get_service_registry
from shared.schemas.api.common import HealthResponse, ServiceStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(service_reg=Depends(get_service_registry)):
    statuses: list[ServiceStatus] = []

    for name, data in service_reg.get_active_services().items():
        health_fn = data.get("health")
        if health_fn is None:
            statuses.append(ServiceStatus(name=name, healthy=True, message="no health check"))
            continue
        try:
            result = health_fn()
            if isinstance(result, dict):
                healthy = result.get("status") == "healthy"
                msg = result.get("message")
            else:
                healthy = bool(result)
                msg = None
            statuses.append(ServiceStatus(name=name, healthy=healthy, message=msg))
        except Exception as exc:
            statuses.append(ServiceStatus(name=name, healthy=False, message=str(exc)))

    overall = "ok" if all(s.healthy for s in statuses) else "degraded"
    return HealthResponse(status=overall, services=statuses)
