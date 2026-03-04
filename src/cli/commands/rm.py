"""rm command â€” remove a note by ID or search."""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.note_remove_interactor import NoteRemoveInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="rm",
    description="Remove a note by ID or search.",
    example="ct rm 12 --search 'biography'",
    no_args_is_help=True,
)
def rm(
    note_id: int = typer.Argument(None, help="The ID of the note to remove."),
    search: str = typer.Option(None, "--search", "-s", help="Search for a concept to find its ID to delete."),
):
    """Remove a note and its links from the graph."""
    try:
        NoteRemoveInteractor(note_id=note_id, search=search).run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)

