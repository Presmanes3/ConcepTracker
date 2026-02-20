from rich.console import Console
from src.services.embedding_service import embedding_service
from src.repository.note_repository import repository
from src.repository.link_repository import link_repository
from src.cli.registry import registry

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
    similar_notes = repository.get_similar_notes(current_id=None, embedding=vec, limit=10, threshold=threshold)
    note_ids = [n["id"] for n in similar_notes]
    
    # Load all notes sorted by date
    notes = repository.get_notes_by_ids(note_ids)
    
    if not notes:
        console.print("[red]No records found for this concept.[/red]")
        return
        
    console.print("\n[bold cyan]Timeline Flow[/bold cyan]\n")
    for i, n in enumerate(notes):
        date_str = n.created_at.strftime("%Y-%m-%d %H:%M")
        # Draw vertical line
        prefix = " ┃ " if i < len(notes)-1 else " ┗ "
        console.print(f"[dim]{date_str}[/dim]")
        console.print(f"{prefix}[bold white]{n.summary}[/bold white]")
        
        # Find links for this note to others in the timeline
        links = link_repository.get_links_by_source(n.id)
        for l in links:
            if l.target_id in note_ids:
                console.print(f"   [dim]... links to note {l.target_id} ({l.relation_type})[/dim]")
        
        console.print(" ┃ ")
        
    console.print("\n[dim]Ready for more inputs. Keep tracking.[/dim]")
