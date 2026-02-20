import typer
from rich.console import Console
from rich.panel import Panel
from src.repository.note_repository import repository
from src.repository.archipelago_repository import archipelago_repository
from src.services.embedding_service import embedding_service
from src.cli.registry import registry

console = Console()

@registry.register(
    name="find",
    description="Semantic search through your knowledge.",
    example='ct find "concepts about machine learning"'
)
def find(query: str = typer.Argument(..., help="Semantic search query")):
    """Find concepts by meaning (Semantic Search) using AI."""
    with console.status(f"[cyan]Searching for '{query}'...[/cyan]"):
        # 1. Vectorize query
        vector = embedding_service.get_embedding(query)
        # 2. Semantic search in DB
        results = repository.semantic_search(vector, limit=5)

    if not results:
        console.print("[yellow]No similar concepts found.[/yellow]")
        return

    console.print(f"\n[bold]Top matches for:[/bold] [italic]'{query}'[/italic]\n")
    for note, distance in results:
        # Distance to Similarity percentage (simple inversion for UX)
        # Cosine distance 0 -> 1. Closer to 0 is more similar.
        percentage = int((1 - distance) * 100)
        percentage = max(0, min(100, percentage))

        color = "green" if percentage > 70 else "yellow"

        # Geography badge
        arch_badge = "[dim]\U0001f3dd\ufe0f  Island[/dim]"
        if note.archipelago_id:
            arch = archipelago_repository.get_archipelago_by_id(note.archipelago_id)
            if arch:
                icon = "\U0001f30d" if arch.type == "continent" else "\U0001f5fa\ufe0f"
                arch_badge = f"{icon} [yellow]{arch.name}[/yellow]"

        console.print(Panel(
            f"{note.content}\n\n[dim]Summary: {note.summary}[/dim]",
            title=f"[{color}]{percentage}% Match (ID: {note.id})[/{color}]",
            subtitle=f"[magenta]{note.tags or 'No Tag'}[/magenta]  {arch_badge}",
            border_style=color
        ))
