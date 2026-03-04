"""stats command â€” analyze AI usage costs and performance."""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.stats_interactor import StatsInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="stats",
    description="Analyze AI usage costs and performance.",
    example="ct stats --days 7"
)
def stats(
    days: int = typer.Option(0, "--days", "-d", help="Filter by last N days"),
    hours: int = typer.Option(0, "--hours", "-hr", help="Filter by last N hours"),
):
    """Explore inference performance and costs."""
    try:
        StatsInteractor(days=days, hours=hours).run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)

