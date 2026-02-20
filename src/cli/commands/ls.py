import typer
from rich.console import Console
from rich.table import Table
from src.repository.note_repository import repository
from src.repository.archipelago_repository import archipelago_repository
from src.cli.registry import registry

console = Console()

@registry.register(
    name="ls",
    description="List all notes in a clean table.",
    example="ct ls --tag AI --archipelago 'Machine Learning'"
)
def ls(
    tag: str = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(15, "--limit", "-l", help="Number of notes to show"),
    archipelago: str = typer.Option(None, "--archipelago", "-a", help="Filter by archipelago name")
):
    """List recent captures in a clean table format."""
    notes = repository.get_all_notes(limit=limit, tag=tag)

    # Optional archipelago filter
    if archipelago:
        all_archs = archipelago_repository.get_all_archipelagos()
        matching = [a for a in all_archs if archipelago.lower() in a.name.lower()]
        if not matching:
            console.print(f"[yellow]No archipelago matching '{archipelago}' found.[/yellow]")
            return
        valid_ids = {a.id for a in matching}
        notes = [n for n in notes if n.archipelago_id in valid_ids]

    if not notes:
        console.print("[yellow]No notes found.[/yellow]")
        return

    table = Table(title="Recent Knowledge Captures", border_style="blue", box=None)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Tag", style="magenta")
    table.add_column("Archipelago", style="yellow")
    table.add_column("Summary", style="white")

    for n in notes:
        arch_label = "[dim]~island~[/dim]"
        if n.archipelago_id:
            arch = archipelago_repository.get_archipelago_by_id(n.archipelago_id)
            if arch:
                icon = "\U0001f30d" if arch.type == "continent" else "\U0001f3dd\ufe0f"
                arch_label = f"{icon} {arch.name}"

        table.add_row(
            str(n.id),
            n.created_at.strftime("%b %d %H:%M"),
            n.tags or "-",
            arch_label,
            n.summary
        )

    console.print(table)
