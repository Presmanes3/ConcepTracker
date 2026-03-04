"""
src/cli/commands/ls.py

List command — delegates fully to NoteListInteractor.
"""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.note_list_interactor import NoteListInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="ls",
    description="List all notes in a clean table.",
    example="ct ls --tag AI --archipelago 'Machine Learning'",
    aliases=["l"],
    group="Search & Discovery"
)
def ls(
    tag: str = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max notes to fetch from DB (0 = all)"),
    page_size: int = typer.Option(10, "--page-size", "-p", help="Rows per page"),
    archipelago: str = typer.Option(None, "--archipelago", "-a", help="Filter by archipelago name"),
):
    """List recent captures with interactive arrow-key pagination."""
    try:
        NoteListInteractor(
            tag=tag,
            limit=limit,
            archipelago=archipelago,
            page_size=page_size,
        ).run()
    except ValueError as exc:
        console.print(Panel(str(exc), title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)