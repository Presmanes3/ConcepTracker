"""add command â€” capture a note with auto-linking."""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.add_interactor import AddInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="add",
    description="Capture a note with auto-linking.",
    example='ct add "DeepSeek-R1 uses RL" --tag "AI"',
    aliases=["a"],
    group="Note Management"
)
def add(
    content: str,
    tag: str = None,
    review: bool = typer.Option(
        False,
        "--review", "-r",
        help="After saving, interactively review near-miss candidates for manual linking.",
    ),
):
    """Capture a new concept atomically and link it to the past."""
    try:
        AddInteractor(content=content, tag=tag, review=review).run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)
