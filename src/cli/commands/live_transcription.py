"""
live_transcription.py -- thin command wrapper.
� thin command wrapper (~25 lines).

All business logic has been moved to:
  src/cli/interactors/transcription_interactor.py   (FSM / UX)
  src/cli/interactors/_transcription_async.py        (async audio pipeline)
  src/cli/views/transcription_views.py               (LiveTranscriptionView)
"""
from rich.console import Console
from rich.panel import Panel

from src.cli.registry import registry
from src.cli.interactors.transcription_interactor import TranscriptionInteractor

console = Console()


@registry.register(
    name="live_transcription",
    description="Start a real-time transcription session using AWS Transcribe.",
    example="ct live_transcription",
)
def live_transcription():
    """Start a real-time transcription session using AWS Transcribe."""
    try:
        TranscriptionInteractor().run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)
