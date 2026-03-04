"""Stats interactor — fetch and display AI usage statistics."""
from __future__ import annotations

from rich.console import Console

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.views import render_stats_dashboard

console = Console()


class StatsInteractor:
    """Fetch stats from GET /stats and render the dashboard."""

    def __init__(self, days: int = 0, hours: int = 0) -> None:
        self._days = days
        self._hours = hours

    def run(self) -> None:
        """Fetch stats and config, then render the dashboard."""
        with console.status("[yellow]Calculating usage…[/yellow]"):
            with ConcepTrackerClient() as client:
                stats = client.get_stats(days=self._days, hours=self._hours)
                config = client.get_config()

        results = stats.model_dump()
        console.print(
            render_stats_dashboard(results, config.is_configured, self._days, self._hours)
        )
