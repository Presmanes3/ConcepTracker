"""init command — initialise database and all registered services."""
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.init_interactor import InitInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="init",
    description="Build the brain. Initialize database and pgvector extension.",
    example="ct init"
)
def init():
    """Build the brain. Initialize database and pgvector extension."""
    try:
        InitInteractor().run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)
