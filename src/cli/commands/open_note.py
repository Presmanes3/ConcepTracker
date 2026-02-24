"""
Command to open a note in a dedicated TUI screen.
"""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.open_note_interactor import OpenNoteInteractor
from src.cli.registry import registry

console = Console()

@registry.register(
    name="open_note",
    description="Open a note in a dedicated TUI screen.",
    example='ct open_note 42'
)
def open_note(
    note_id: int = typer.Argument(..., help="ID of the note to open"),
):
    """Open a note and view its details, connections, and actions."""
    try:
        OpenNoteInteractor(note_id=note_id).run()
    except ValueError as exc:
        console.print(Panel(str(exc), title="[bold]Error[/bold]", border_style="red"))
