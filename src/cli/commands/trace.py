from rich.console import Console
from src.cli.registry import registry

from src.registry import repos
from src.services.search_service import search_service
from src.cli.views import render_trace_timeline
from src.services.embedding_service import embedding_service

console = Console()

@registry.register(
    name="trace",
    description="Trace the chronological evolution of a concept.",
    example='ct trace "Large Language Models" --threshold 0.8'
)
def trace(concept: str, threshold: float = 0.85):
    """Trace the chronological evolution of a concept."""

    console.print(f"[bold magenta]Tracing: {concept}[/bold magenta]")

    # Use SSoT vector search; embedding is computed inside search_service.
    
    vec = embedding_service.get_embedding(concept)
    similar_notes = search_service.vector_search(
        embedding=vec,
        limit=10,
        threshold=threshold,
    )
    note_ids = [n["id"] for n in similar_notes]

    # Load full Note objects sorted by creation date for chronological display.
    notes = repos.notes.get_notes_by_ids(note_ids)

    console.print(render_trace_timeline(concept, notes, note_ids, repos.links.get_links_by_source))
