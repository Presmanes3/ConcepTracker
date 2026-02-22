from rich.console import Console
from src.cli.registry import registry

from src.services.embedding_service import embedding_service
from src.registry import repos
from src.cli.views import render_trace_timeline

console = Console()

@registry.register(
    name="trace",
    description="Trace the chronological evolution of a concept.",
    example='ct trace "Large Language Models" --threshold 0.8'
)
def trace(concept: str, threshold: float = 0.85):
    """Trace the chronological evolution of a concept."""

    
    console.print(f"[bold magenta]Tracing: {concept}[/bold magenta]")
    
    # Search relevant notes using vector similarity with threshold
    vec = embedding_service.get_embedding(concept)
    similar_notes = repos.notes.get_similar_notes(current_id=None, embedding=vec, limit=10, threshold=threshold)
    note_ids = [n["id"] for n in similar_notes]
    
    # Load all notes sorted by date
    notes = repos.notes.get_notes_by_ids(note_ids)
    
    console.print(render_trace_timeline(concept, notes, note_ids, repos.links.get_links_by_source))
