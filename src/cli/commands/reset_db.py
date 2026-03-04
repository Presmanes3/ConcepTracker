"""reset_db command — drop and recreate all database tables (destructive)."""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.reset_db_interactor import ResetDbInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="reset-db",
    description="Drop and recreate all database tables (destructive).",
    example="ct reset-db",
)
def reset_db(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
):
    """Drop and recreate all database tables. All data will be lost."""
    try:
        ResetDbInteractor(yes=yes).run()
    except SystemExit:
        raise
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)
