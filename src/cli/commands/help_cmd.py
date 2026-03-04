import typer
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from src.cli.registry import registry

console = Console()

@registry.register(
    name="help",
    description="Show this dashboard help menu with categorized commands.",
    example="ct help",
    group="Common Commands"
)
def help_command():
    """
    Explore ConcepTracker - Atomic knowledge capture & semantic traceability.
    """
    # Header: Professional layout
    console.print(Panel(
        Group(
            "[bold cyan]ConcepTracker CLI Dashboard 🧠[/bold cyan]",
            "[dim]The atomic knowledge network for your personal brain.[/dim]"
        ),
        border_style="cyan",
        expand=True
    ))

    # Categorize commands
    groups = {}
    for cmd in registry.commands:
        if cmd.group not in groups:
            groups[cmd.group] = []
        groups[cmd.group].append(cmd)

    # Build panels for each group
    panels = []
    for group_name, commands in groups.items():
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Command", style="bold yellow", width=12)
        table.add_column("Description", style="white")

        for cmd in commands:
            table.add_row(cmd.name, cmd.description)
        
        panels.append(Panel(
            table, 
            title=f"[bold white]{group_name}[/bold white]", 
            border_style="blue",
            expand=True
        ))

    # Display in columns for a "Dashboard" feel
    console.print(Columns(panels, equal=True, expand=True))
    
    # Global tips panel
    console.print(Panel(
        "[italic dim]Quick Start:[/italic dim] [cyan]ct add \"my idea\"[/cyan] | [italic dim]Search:[/italic dim] [cyan]ct find \"query\"[/cyan]\n"
        "[bold white]Pro Tip:[/bold white] Use [yellow]ct <command> --help[/yellow] for detailed flags and options.",
        title="[bold yellow]Hints[/bold yellow]",
        border_style="yellow"
    ))

