import typer
from rich.console import Console
from src.cli.registry import registry
from src.services.cost_service import cost_service
from src.cli.views import render_stats_dashboard

console = Console()

@registry.register(
    name="stats",
    description="Analyze AI usage costs and performance.",
    example="ct stats --days 7"
)
def stats(
    days: int = typer.Option(0, "--days", "-d", help="Filter by last N days"),
    hours: int = typer.Option(0, "--hours", "-hr", help="Filter by last N hours")
):
    """
    Explore Inference performance and costs.
    """
    
    
    # UX degradation if no pricing is found
    if not cost_service.is_configured:
        with console.status("[yellow]Calculating token usage...[/yellow]"):
            results = cost_service.get_stats(days=days, hours=hours)
        console.print(render_stats_dashboard(results, False, days, hours))
        return

    with console.status("[yellow]Calculating costs...[/yellow]"):
        results = cost_service.get_stats(days=days, hours=hours)

    console.print(render_stats_dashboard(results, True, days, hours))
