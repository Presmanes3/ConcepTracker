"""Notes router — CRUD + two-phase ingest."""
import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_note_repo, get_link_repo
from src.api.schemas import (
    LinkConfirmRequest,
    MessageResponse,
    NearMissCandidate,
    NoteIngestRequest,
    NoteIngestResponse,
    NoteResponse,
)
from shared.schemas.models.link import Link
from shared.schemas.workflow.ingest import IngestState
from src.workflows.ingest_workflow import ingest_graph

router = APIRouter()


def _to_note_response(note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        content=note.content,
        summary=note.summary,
        tags=note.tags,
        created_at=note.created_at,
        domain=note.domain,
        domain_family=note.domain_family,
        archipelago_id=note.archipelago_id,
    )


# ── List notes ────────────────────────────────────────────────────────────────

@router.get("/notes", response_model=List[NoteResponse])
def list_notes(
    limit: int = Query(20, ge=1, le=200),
    tag: Optional[str] = Query(None),
    note_repo=Depends(get_note_repo),
):
    notes = note_repo.get_all_notes(limit=limit, tag=tag)
    return [_to_note_response(n) for n in notes]


# ── Get single note ───────────────────────────────────────────────────────────

@router.get("/notes/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, note_repo=Depends(get_note_repo)):
    note = note_repo.get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found.")
    return _to_note_response(note)


# ── Delete note ───────────────────────────────────────────────────────────────

@router.delete("/notes/{note_id}", response_model=MessageResponse)
def delete_note(note_id: int, note_repo=Depends(get_note_repo), link_repo=Depends(get_link_repo)):
    # Remove all links first (FK constraint)
    link_repo.delete_links_for_note(note_id)
    deleted = note_repo.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found.")
    return MessageResponse(message=f"Note {note_id} deleted.")


# ── Phase 1 ingest: run pipeline, return near-miss candidates ─────────────────

@router.post("/notes", response_model=NoteIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_note(body: NoteIngestRequest):
    initial_state = IngestState(  # type: ignore[call-arg]
        content=body.content,
        source_type=body.source_type,
        source_url=body.source_url,
    )

    # LangGraph invoke is synchronous — run in a thread to avoid blocking the event loop.
    # Pass the IngestState object directly (LangGraph accepts typed state or dict).
    result: dict = await asyncio.to_thread(ingest_graph.invoke, initial_state)  # type: ignore[arg-type]

    candidates = [
        NearMissCandidate(
            note_id=c.get("id") or c.get("note_id"),
            score=round(1.0 - c.get("distance", 0.0), 4),
            summary=c.get("summary", ""),
            tags=c.get("tags"),
            domain=c.get("domain"),
        )
        for c in result.get("near_miss_candidates", [])
        if (c.get("id") or c.get("note_id"))
    ]

    return NoteIngestResponse(
        note_id=result.get("note_id"),
        action=result.get("action", "CREATE"),
        reasoning=result.get("reasoning"),
        near_miss_candidates=candidates,
    )


# ── Phase 2 ingest: save manually confirmed links ─────────────────────────────

@router.post("/notes/{note_id}/links", response_model=MessageResponse)
def confirm_links(
    note_id: int,
    body: List[LinkConfirmRequest],
    note_repo=Depends(get_note_repo),
    link_repo=Depends(get_link_repo),
):
    if not note_repo.get_note_by_id(note_id):
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found.")

    saved = 0
    for req in body:
        link = Link(
            source_id=note_id,
            target_id=req.target_id,
            relation_type=req.relation_type,
            reason=req.reason,
        )
        link_repo.save_link(link)
        saved += 1

    return MessageResponse(message=f"Saved {saved} link(s) for note {note_id}.")
