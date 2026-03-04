"""Health interactor — query backend health and display service status."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.client.http_client import ConcepTrackerClient

console = Console()


class HealthInteractor:
    """Query GET /health and render a status table."""

    def run(self) -> None:
        """Fetch health status from the API and print it."""
        try:
            with ConcepTrackerClient() as client:
                response = client.get_health()
        except Exception as exc:
            console.print(Panel(
                f"[red]Could not reach the backend: {exc}[/red]\n\n"
                "[dim]Is the API server running? Try: docker compose up -d[/dim]",
                title="[bold]Health Check Failed[/bold]",
                border_style="red",
            ))
            return

        table = Table(
            title=f"[bold]System Health — overall: {response.status.upper()}[/bold]",
            show_header=True,
            header_style="bold",
            border_style="cyan" if response.status == "ok" else "red",
        )
        table.add_column("Service", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Message", style="dim")

        for svc in response.services:
            icon = "[green]✅[/green]" if svc.healthy else "[red]❌[/red]"
            table.add_row(svc.name.capitalize(), icon, svc.message or "")

        console.print(table)
