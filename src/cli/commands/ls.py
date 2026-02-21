import typer
from rich.console import Console
from rich.table import Table
from src.cli.registry import registry
from src.cli.pager import paginate_table
from src.cli.interactors.note_menu_interactor import NoteMenuInteractor
from src.cli.views import note_card_view, prefetch_arch_cache
from src.registry import repos

console = Console()

@registry.register(
    name="ls",
    description="List all notes in a clean table.",
    example="ct ls --tag AI --archipelago 'Machine Learning'"
)
def ls(
    tag: str = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max notes to fetch from DB (0 = all)"),
    page_size: int = typer.Option(10, "--page-size", "-p", help="Rows per page"),
    archipelago: str = typer.Option(None, "--archipelago", "-a", help="Filter by archipelago name")
):
    """List recent captures with interactive arrow-key pagination."""

    
    fetch_limit = limit if limit > 0 else 9999
    
    while True:
        notes = repos.notes.get_all_notes(limit=fetch_limit, tag=tag)

        # Optional archipelago filter
        if archipelago:
            all_archs = repos.archipelagos.get_all_archipelagos()
            matching = [a for a in all_archs if archipelago.lower() in a.name.lower()]
            if not matching:
                console.print(f"[yellow]No archipelago matching '{archipelago}' found.[/yellow]")
                return
            valid_ids = {a.id for a in matching}
            notes = [n for n in notes if n.archipelago_id in valid_ids]

        if not notes:
            console.print("[yellow]No notes found.[/yellow]")
            return

        # Pre-resolve archipelago labels once (avoids N+1 inside the builder)
        arch_cache = prefetch_arch_cache(notes, repos.archipelagos)

        def build_table(chunk, cursor_index, start_idx, expanded_states):
            table = Table(
                title=f"Knowledge Captures  [dim]({len(notes)} total)[/dim]",
                border_style="blue",
                box=None,
            )
            table.add_column("ID", style="cyan", justify="right")
            table.add_column("Date", style="dim")
            table.add_column("Tag", style="magenta")
            table.add_column("Archipelago", style="yellow")
            table.add_column("Summary", style="white")

            for i, n in enumerate(chunk):
                global_idx = start_idx + i
                arch_label = arch_cache.get(n.archipelago_id, "[dim]~island~[/dim]")
                
                # Highlight the row if it's the cursor
                style = "reverse" if i == cursor_index else None
                
                # Add expand indicator
                is_expanded = global_idx in expanded_states
                expand_indicator = "[-]" if is_expanded else "[+]"
                id_str = f"{expand_indicator} {n.id}"
                
                # Truncate summary for the table view to keep it clean
                summary = n.summary
                if len(summary) > 60:
                    summary = summary[:57] + "..."
                
                table.add_row(
                    id_str,
                    n.created_at.strftime("%b %d %H:%M"),
                    n.tags or "-",
                    arch_label,
                    summary,
                    style=style
                )
            return table

        def build_preview(note):
            return note_card_view(note, arch_badge=arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]"))

        selected_note = paginate_table(notes, build_table, page_size=page_size, build_preview=build_preview)
        
        if selected_note:
            NoteMenuInteractor(note_id=selected_note.id).run()
        else:
            break # User quit the pager
