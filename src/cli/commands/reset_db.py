"""
src/cli/commands/reset_db.py

Drop and recreate all DB tables — destructive, requires confirmation.
"""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.registry import registry

console = Console()


@registry.register(
    name="reset_db",
    description="Drop and recreate all database tables (destructive).",
    example="ct reset_db",
)
def reset_db(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
):
    """Drop and recreate all database tables. All data will be lost."""
    if not yes:
        confirmed = typer.confirm(
            "[bold red]This will delete ALL notes, links and archipelagos.[/bold red] Continue?",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit()

    from sqlmodel import SQLModel, create_engine
    import os
    from dotenv import load_dotenv
    from shared.schemas.models.archipelago import Archipelago  # noqa: F401
    from shared.schemas.models.note import Note  # noqa: F401
    from shared.schemas.models.link import Link  # noqa: F401
    from shared.schemas.models.inference_log import InferenceLog  # noqa: F401

    load_dotenv()
    engine = create_engine(os.environ["DATABASE_URL"])

    with console.status("[red]Dropping tables...[/red]"):
        SQLModel.metadata.drop_all(engine)

    with console.status("[cyan]Recreating tables...[/cyan]"):
        SQLModel.metadata.create_all(engine)

    console.print(Panel("[green]Database reset successfully.[/green]", title="reset_db"))
