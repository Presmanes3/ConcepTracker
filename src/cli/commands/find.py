"""
src/cli/commands/find.py

Semantic search command — delegates fully to NoteFindInteractor.
"""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.note_find_interactor import NoteFindInteractor
from src.cli.registry import registry

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
    try:
        NoteFindInteractor(
            query=query,
            limit=limit,
            page_size=page_size,
        ).run()
    except ValueError as exc:
        console.print(Panel(str(exc), title="[bold]Error[/bold]", border_style="red"))
