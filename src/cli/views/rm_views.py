from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def render_delete_selection_table(notes):
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

def render_delete_confirmation(note):
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
