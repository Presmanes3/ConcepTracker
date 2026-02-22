from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def render_delete_selection_table(notes) -> Table:
    """Return a Rich Table listing notes available for deletion."""
    table = Table(
        title="[bold red]Select a Note to Delete[/bold red]",
        border_style="dim",
        box=None,
        header_style="bold cyan",
    )
    table.add_column("ID", justify="right", style="bold yellow", no_wrap=True)
    table.add_column("Summary", style="white")
    table.add_column("Created At", style="dim cyan")
    for n in notes:
        table.add_row(str(n.id), n.summary, n.created_at.strftime("%Y-%m-%d %H:%M"))
    return table


def render_delete_confirmation(note) -> RenderableType:
    """Return a Rich Group with a blank line then a confirmation Panel."""
    details = (
        f"[bold]Summary:[/bold] {note.summary}\n"
        f"[bold]Content:[/bold] [italic]{note.content}[/italic]\n\n"
        f"[red]This will permanently remove this note and all its connections.[/red]"
    )
    return Group(
        Text(""),
        Panel(
            details,
            title=f"[white]Confirm Deletion of ID: {note.id}[/white]",
            border_style="red",
        ),
    )