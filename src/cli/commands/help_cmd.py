import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.cli.registry import registry

console = Console()

@registry.register(
    name="help",
    description="Show this help menu with all commands.",
    example="ct help"
)
def help_command():
    """
    Explore ConcepTracker - Atomic knowledge capture & semantic traceability.
    """
    console.print(Panel.fit(
        "[bold cyan]ConcepTracker 🧠[/bold cyan]\n[dim]The atomic knowledge network for your personal brain.[/dim]",
        border_style="cyan"
    ))

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Command", style="bold yellow", width=12)
    table.add_column("Description", style="white")
    table.add_column("Example Usage", style="dim cyan")

    # The registry provides the source of truth for all commands
    for cmd in registry.commands:
        table.add_row(
            cmd.name,
            cmd.description,
            cmd.example
        )

    console.print(table)
    console.print("\n[italic dim]Try 'ct <command> --help' for more detailed options.[/italic dim]")
