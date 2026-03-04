"""Reset-DB interactor — drop and recreate all database tables."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.client.http_client import ConcepTrackerClient

console = Console()


class ResetDbInteractor:
    """Call POST /admin/reset-db after confirmation and display the result."""

    def __init__(self, yes: bool = False) -> None:
        self._yes = yes

    def run(self) -> None:
        """Confirm (unless --yes) and reset the database."""
        if not self._yes:
            confirmed = typer.confirm(
                "This will delete ALL notes, links and archipelagos. Continue?",
                default=False,
            )
            if not confirmed:
                console.print("[dim]Aborted.[/dim]")
                raise typer.Exit()

        with console.status("[red]Resetting database…[/red]"):
            with ConcepTrackerClient() as client:
                result = client.reset_db()

        console.print(Panel(
            f"[green]{result.message}[/green]",
            title="[bold]reset_db[/bold]",
            border_style="green",
        ))
