"""trace command â€” trace the chronological evolution of a concept."""
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.note_trace_interactor import NoteTraceInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="trace",
    description="Trace the chronological evolution of a concept.",
    example='ct trace "Large Language Models" --threshold 0.8',
    aliases=["t"]
)
def trace(concept: str, threshold: float = 0.85):
    """Trace the chronological evolution of a concept."""
    try:
        NoteTraceInteractor(concept=concept, threshold=threshold).run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)

