"""health command — verify system health."""
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.health_interactor import HealthInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="health",
    description="Verify system health (DB connection & AI connectivity).",
    example="ct health"
)
def health():
    """Verify system health (DB connection & AI connectivity)."""
    try:
        HealthInteractor().run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)
