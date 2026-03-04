"""Init interactor — trigger backend DB and service initialization."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from src.cli.client.http_client import ConcepTrackerClient

console = Console()


class InitInteractor:
    """Call POST /init and display the result."""

    def run(self) -> None:
        """Run initialization and print the result."""
        with console.status("[yellow]Initializing services…[/yellow]"):
            with ConcepTrackerClient() as client:
                result = client.run_init()

        console.print(Panel(
            f"[green]{result.message}[/green]",
            title="[bold]Initialization[/bold]",
            border_style="green",
        ))

        if result.detail:
            for line in result.detail:
                color = "red" if "error" in str(line).lower() else "dim"
                console.print(f"  [{color}]{line}[/{color}]")
