"""POST /init — initialise DB tables and all registered services."""
from fastapi import APIRouter, Depends

from src.api.dependencies import get_service_registry
from src.api.schemas import MessageResponse
from src.utils.db import init_db

router = APIRouter()


@router.post("/init", response_model=MessageResponse)
def run_init(service_reg=Depends(get_service_registry)):
    """Create DB schema and run each active service's init function."""
    init_db()

    results: list[str] = []
    for name, data in service_reg.get_active_services().items():
        init_fn = data.get("init")
        if init_fn is None:
            continue
        try:
            init_fn()
            results.append(f"{name}: ok")
        except Exception as exc:
            results.append(f"{name}: error — {exc}")

    return MessageResponse(
        message="Initialisation complete.",
        detail=results,
    )
