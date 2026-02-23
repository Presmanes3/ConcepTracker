"""
src/cli/interactors/device_list_interactor.py

DeviceListInteractor — business logic for the `ct list-devices` command.
Orchestrates the Textual device-list screen and persists the user's choice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.console import Console

from src.cli.screens.device_list_screen import run_device_list_ui


class DeviceListInteractor:
    """
    Encapsulates the full flow of the `list-devices` command:
      1. Launch the Textual device-list screen.
      2. Persist the selected device via AudioDeviceService.
      3. Print a contextual status message to the terminal.
    """

    def __init__(
        self,
        devices: List[Dict[str, Any]],
        current_device_id: Optional[int],
        console: Optional[Console] = None,
    ) -> None:
        self.devices = devices
        self.current_device_id = current_device_id
        self.console = console or Console()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Launch the UI and handle the result."""
        selected_id = run_device_list_ui(self.devices, self.current_device_id)
        self._handle_result(selected_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _device_name(self, device_id: int) -> str:
        return next(
            (d["name"] for d in self.devices if d["id"] == device_id),
            str(device_id),
        )

    def _handle_result(self, selected_id: Optional[int]) -> None:
        if selected_id is None:
            self.console.print("[dim]No changes made.[/dim]")
            return

        if selected_id == self.current_device_id:
            name = self._device_name(selected_id)
            self.console.print(
                f"[yellow]{name} (ID: {selected_id}) is already the active device.[/yellow]"
            )
            return

        from src.services.audio_device_service import audio_device_service

        success = audio_device_service.set_configured_device_id(selected_id)
        name = self._device_name(selected_id)
        if success:
            self.console.print(
                f"[green]✔[/green] Active device → "
                f"[bold cyan]{name}[/bold cyan]  [dim](ID: {selected_id})[/dim]"
            )
        else:
            self.console.print("[red]✖ Failed to save device configuration.[/red]")
            import typer; raise typer.Exit(1)
