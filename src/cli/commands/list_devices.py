"""
src/cli/commands/list_devices.py

Thin command entry point for listing and configuring audio input devices.

Usage:
    ct list-devices
"""
import typer
from rich.console import Console

from src.cli.registry import registry
from src.cli.screens.device_list_screen import run_device_list_ui
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

    Use ↑/↓ (or k/j) to navigate, Enter to set a device as active,
    and q/Esc to cancel without making changes.
    The selected device ID is persisted to config/settings.yaml.
    """
    with console.status("[dim]Scanning audio input devices…[/dim]"):
        devices    = audio_device_service.get_available_input_devices()
        current_id = audio_device_service.get_configured_device_id()

    if not devices:
        console.print("[red]No audio input devices found on this system.[/red]")
        raise typer.Exit(1)

    selected_id = run_device_list_ui(devices, current_id)

    if selected_id is None:
        console.print("[dim]No changes made.[/dim]")
        return

    if selected_id == current_id:
        name = next((d["name"] for d in devices if d["id"] == selected_id), str(selected_id))
        console.print(
            f"[yellow]Device [bold]{name}[/bold] (ID: {selected_id}) is already the active device.[/yellow]"
        )
        return

    success = audio_device_service.set_configured_device_id(selected_id)
    if success:
        name = next((d["name"] for d in devices if d["id"] == selected_id), str(selected_id))
        console.print(
            f"[green]✔[/green] Active audio device set to "
            f"[bold cyan]{name}[/bold cyan] (ID: {selected_id})"
        )
    else:
        console.print("[red]Failed to save device configuration.[/red]")
        raise typer.Exit(1)
