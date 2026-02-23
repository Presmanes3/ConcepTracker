"""
src/cli/commands/list_devices.py

Thin command entry point for listing and configuring audio input devices.

Usage:
    ct list-devices
"""
import typer
from rich.console import Console

from src.cli.interactors.device_list_interactor import DeviceListInteractor
from src.cli.registry import registry
from src.services.audio_device_service import audio_device_service

console = Console()


@registry.register(
    name="list-devices",
    description="Browse available audio input devices and set the active one.",
    example="ct list-devices",
)
def list_devices() -> None:
    """
    Open an interactive list of all available audio input devices.

    Use ↑/↓ (or k/j) to navigate, Enter to confirm selection,
    and Esc to cancel without making changes.
    """
    with console.status("[dim]Scanning audio input devices…[/dim]"):
        devices    = audio_device_service.get_available_input_devices()
        current_id = audio_device_service.get_configured_device_id()

    if not devices:
        console.print("[red]No audio input devices found on this system.[/red]")
        raise typer.Exit(1)

    DeviceListInteractor(devices, current_id, console=console).run()
