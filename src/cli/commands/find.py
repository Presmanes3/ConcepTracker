import typer
from rich.console import Console
from rich.table import Table
from src.cli.registry import registry
from src.cli.pager import paginate_table
from src.cli.interactors.note_menu_interactor import NoteMenuInteractor
from src.cli.views import note_card_view, prefetch_arch_cache
from src.registry import repos
from src.services.embedding_service import embedding_service

console = Console()

@registry.register(
    name="find",
    description="Semantic search through your knowledge.",
    example='ct find "concepts about machine learning"'
)
def find(
    query: str = typer.Argument(..., help="Semantic search query"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to retrieve"),
    page_size: int = typer.Option(10, "--page-size", "-p", help="Rows per page"),
):
    """Find concepts by meaning (Semantic Search) using AI."""

    
    while True:
        with console.status(f"[cyan]Searching for '{query}'...[/cyan]"):
            vector = embedding_service.get_embedding(query)
            results = repos.notes.semantic_search(vector, limit=limit)

        if not results:
            console.print("[yellow]No similar concepts found.[/yellow]")
            return

        # Pre-resolve archipelago badges
        arch_cache = prefetch_arch_cache(results, repos.archipelagos)

        def build_table(chunk, cursor_index, start_idx, expanded_states):
            table = Table(
                title=f"Top {len(results)} matches for: [italic]'{query}'[/italic]",
                border_style="blue",
                box=None,
            )
            table.add_column("Match", style="green", justify="right")
            table.add_column("ID", style="cyan", justify="right")
            table.add_column("Date", style="dim")
            table.add_column("Tag", style="magenta")
            table.add_column("Archipelago", style="yellow")
            table.add_column("Summary", style="white")

            for i, item in enumerate(chunk):
                note, distance = item
                global_idx = start_idx + i
                
                percentage = max(0, min(100, int((1 - distance) * 100)))
                match_color = "green" if percentage > 70 else "yellow"
                match_str = f"[{match_color}]{percentage}%[/{match_color}]"
                
                arch_label = arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]")
                
                # Highlight the row if it's the cursor
                style = "reverse" if i == cursor_index else None
                
                # Add expand indicator
                is_expanded = global_idx in expanded_states
                expand_indicator = "[-]" if is_expanded else "[+]"
                id_str = f"{expand_indicator} {note.id}"
                
                # Truncate summary for the table view to keep it clean
                summary = note.summary
                if len(summary) > 50:
                    summary = summary[:47] + "..."
                
                table.add_row(
                    match_str,
                    id_str,
                    note.created_at.strftime("%b %d %H:%M"),
                    note.tags or "-",
                    arch_label,
                    summary,
                    style=style
                )
            return table

        def build_preview(item):
            note, distance = item
            percentage = max(0, min(100, int((1 - distance) * 100)))
            color = "green" if percentage > 70 else "yellow"
            title = f"[{color} bold]Preview: Note #{note.id} ({percentage}% Match)[/{color} bold]"
            return note_card_view(note, arch_badge=arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]"), title=title, border_style=color)

        selected_item = paginate_table(results, build_table, page_size=page_size, build_preview=build_preview)
        
        if selected_item:
            note, _ = selected_item
            NoteMenuInteractor(note_id=note.id).run()
        else:
            break # User quit the pager
