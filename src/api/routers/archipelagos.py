"""GET /archipelagos + GET /archipelagos/{id}."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_arch_repo
from shared.schemas.api.archipelagos import ArchipelagoResponse

router = APIRouter()


def _to_arch_response(arch) -> ArchipelagoResponse:
    return ArchipelagoResponse(
        id=arch.id,
        name=arch.name,
        summary=arch.summary,
        type=arch.type,
        parent_id=arch.parent_id,
        needs_refresh=arch.needs_refresh,
        created_at=arch.created_at,
    )


@router.get("/archipelagos", response_model=List[ArchipelagoResponse])
def list_archipelagos(arch_repo=Depends(get_arch_repo)):
    return [_to_arch_response(a) for a in arch_repo.get_all_archipelagos()]


@router.get("/archipelagos/{arch_id}", response_model=ArchipelagoResponse)
def get_archipelago(arch_id: int, arch_repo=Depends(get_arch_repo)):
    arch = arch_repo.get_archipelago_by_id(arch_id)
    if not arch:
        raise HTTPException(status_code=404, detail=f"Archipelago {arch_id} not found.")
    return _to_arch_response(arch)
