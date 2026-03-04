"""list-devices command — browse and configure audio input devices."""
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.device_list_interactor import DeviceListInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="list-devices",
    description="Browse available audio input devices and set the active one.",
    example="ct list-devices",
)
def list_devices() -> None:
    """Open an interactive list of all available audio input devices."""
    try:
        DeviceListInteractor(console=console).run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)
