"""Partial re-normalisation workflow — used by PUT /notes to reprocess content."""
from langgraph.graph import StateGraph, START, END

from shared.schemas.workflow.ingest import IngestState
from src.workflows.ingest_workflow import normalize_and_embed, classify_concept

_graph = StateGraph(IngestState)
_graph.add_node("normalize", normalize_and_embed)
_graph.add_node("classify_concept", classify_concept)
_graph.add_edge(START, "normalize")
_graph.add_edge("normalize", "classify_concept")
_graph.add_edge("classify_concept", END)

normalize_graph = _graph.compile()


def run_normalize(content: str, note_id: int | None = None) -> dict:
    """Run normalize → classify for content re-processing without full ingest.

    Invoke when updating an existing note's content; produces a fresh summary,
    tags, embedding, domain, and domain_family without triggering the gatekeeper,
    link detection, or geography sub-workflow.

    Args:
        content: Raw text content to reprocess.
        note_id: Optional ID of the existing note being updated.

    Returns:
        Dict with updated ``content``, ``summary``, ``tags``, ``embedding``,
        ``domain``, and ``domain_family`` keys.
    """
    state = IngestState(content=content, note_id=note_id)
    return normalize_graph.invoke(state)
