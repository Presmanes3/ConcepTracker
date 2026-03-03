"""GET /notes/{id}/links — retrieve all links for a note."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_link_repo, get_note_repo
from src.api.schemas import LinkResponse

router = APIRouter()


def _to_link_response(link) -> LinkResponse:
    return LinkResponse(
        id=link.id,
        source_id=link.source_id,
        target_id=link.target_id,
        relation_type=link.relation_type,
        reason=link.reason,
        created_at=link.created_at,
    )


@router.get("/notes/{note_id}/links", response_model=List[LinkResponse])
def get_links_for_note(
    note_id: int,
    note_repo=Depends(get_note_repo),
    link_repo=Depends(get_link_repo),
):
    if not note_repo.get_note_by_id(note_id):
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found.")

    outgoing = link_repo.get_links_by_source(note_id)
    incoming = link_repo.get_links_by_target(note_id)

    # De-duplicate by id (a link cannot be both incoming and outgoing)
    seen: set[int] = set()
    result: list[LinkResponse] = []
    for link in list(outgoing) + list(incoming):
        if link.id not in seen:
            seen.add(link.id)
            result.append(_to_link_response(link))

    return result
