import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from src.cli.registry import registry
from src.registry import repos
from src.services.embedding_service import embedding_service
from src.cli.views import render_delete_selection_table, render_delete_confirmation

console = Console()

@registry.register(
    name="rm",
    description="Remove a note by ID or search.",
    example="ct rm 12 --search 'biography'",
    no_args_is_help=True
)
def rm(
    note_id: int = typer.Argument(None, help="The ID of the note to remove."),
    search: str = typer.Option(None, "--search", "-s", help="Search for a concept to find its ID to delete.")
):
    """
    Remove a note and its links from the graph.
    """

    
    if note_id is None:
        if search:
            # Semantic search to find the ID
            with console.status(f"[cyan]Searching for '{search}' to delete...[/cyan]"):
                vector = embedding_service.get_embedding(search)
                results = repos.notes.semantic_search(vector, limit=5)
                notes = [r[0] for r in results]
        else:
            # Just show recent notes
            notes = repos.notes.get_all_notes(limit=10)
        
        if not notes:
            console.print("[yellow]No notes found matching your criteria.[/yellow]")
            return
        
        console.print(render_delete_selection_table(notes))
        
        note_id_str = Prompt.ask("\n[bold red]Enter the ID to delete[/bold red]", default="")
        if not note_id_str:
            console.print("[dim]Action cancelled.[/dim]")
            return
        try:
            note_id = int(note_id_str)
        except ValueError:
            console.print("[red]Invalid ID format.[/red]")
            return

    # Delete confirmation
    note = repos.notes.get_note_by_id(note_id)
    if not note:
        console.print(f"[red]Note with ID {note_id} not found.[/red]")
        return

    console.print(render_delete_confirmation(note))

    if Confirm.ask("Are you sure?", default=False):
        if repos.notes.delete_note(note_id):
            console.print(f"\n✅ [bold green]Concept {note_id} has been erased from your brain.[/bold green]")
        else:
            console.print(f"❌ [red]Failed to delete Note {note_id}.[/red]")
    else:
        console.print("[dim]Deletion aborted. Your memory remains intact.[/dim]")
