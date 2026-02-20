from rich.console import Console
from src.utils.db import init_db, health_check
from src.cli.registry import registry

console = Console()

@registry.register(
    name="init",
    description="Build the brain. Initialize database and pgvector extension.",
    example="ct init"
)
def init():
    """Build the brain. Initialize database and pgvector extension."""
    console.print("[yellow]Initializing database...[/yellow]")
    init_db()
    if health_check():
        console.print("[green]Success! Database is ready to track concepts.[/green]")
    else:
        console.print("[red]Critical Error: Database connection failed. Is Docker running?[/red]")
