import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from src.repository.note_repository import repository
from src.services.embedding_service import embedding_service
from src.cli.registry import registry

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
                results = repository.semantic_search(vector, limit=5)
                notes = [r[0] for r in results]
        else:
            # Just show recent notes
            notes = repository.get_all_notes(limit=10)
        
        if not notes:
            console.print("[yellow]No notes found matching your criteria.[/yellow]")
            return
        
        table = Table(
            title="[bold red]Select a Note to Delete[/bold red]", 
            border_style="dim", 
            box=None,
            header_style="bold cyan"
        )
        table.add_column("ID", justify="right", style="bold yellow", no_wrap=True)
        table.add_column("Summary", style="white")
        table.add_column("Created At", style="dim cyan")

        for n in notes:
            table.add_row(str(n.id), n.summary, n.created_at.strftime("%Y-%m-%d %H:%M"))

        console.print(table)
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
    note = repository.get_note_by_id(note_id)
    if not note:
        console.print(f"[red]Note with ID {note_id} not found.[/red]")
        return

    # UX: Highlighting what is being deleted in a red Panel
    details = (
        f"[bold]Summary:[/bold] {note.summary}\n"
        f"[bold]Content:[/bold] [italic]{note.content}[/italic]\n\n"
        f"[red]⚠️ This will permanently remove this note and all its connections.[/red]"
    )
    
    console.print("\n")
    console.print(Panel(
        details, 
        title=f"[white]Confirm Deletion of ID: {note.id}[/white]", 
        border_style="red"
    ))

    if Confirm.ask("Are you sure?", default=False):
        if repository.delete_note(note_id):
            console.print(f"\n✅ [bold green]Concept {note_id} has been erased from your brain.[/bold green]")
        else:
            console.print(f"❌ [red]Failed to delete Note {note_id}.[/red]")
    else:
        console.print("[dim]Deletion aborted. Your memory remains intact.[/dim]")
