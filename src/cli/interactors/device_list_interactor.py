"""DeviceListInteractor — fetch devices via REST API, show selector, persist choice."""
from __future__ import annotations

from typing import Optional

from rich.console import Console

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.screens.device_list_screen import run_device_list_ui


class DeviceListInteractor:
    """Fetch available audio devices, open the selector UI, and persist the choice."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Fetch devices from the API, open the UI, and persist selection."""
        import typer

        with ConcepTrackerClient() as client:
            with self.console.status("[dim]Scanning audio input devices…[/dim]"):
                device_responses = client.list_devices()

        if not device_responses:
            self.console.print("[red]No audio input devices found on this system.[/red]")
            raise typer.Exit(1)

        # Convert DeviceResponse → dict for the screen (legacy interface)
        devices = [d.model_dump() for d in device_responses]
        current_id = next((d["id"] for d in devices if d["active"]), None)

        selected_id = run_device_list_ui(devices, current_id)
        self._handle_result(selected_id, devices, current_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _device_name(self, device_id: int, devices: list) -> str:
        return next(
            (d["name"] for d in devices if d["id"] == device_id),
            str(device_id),
        )

    def _handle_result(
        self,
        selected_id: Optional[int],
        devices: list,
        current_id: Optional[int],
    ) -> None:
        if selected_id is None:
            self.console.print("[dim]No changes made.[/dim]")
            return

        if selected_id == current_id:
            name = self._device_name(selected_id, devices)
            self.console.print(
                f"[yellow]{name} (ID: {selected_id}) is already the active device.[/yellow]"
            )
            return

        import typer

        with ConcepTrackerClient() as client:
            result = client.set_active_device(selected_id)

        name = self._device_name(selected_id, devices)
        self.console.print(
            f"[green]✔[/green] Active device → "
            f"[bold cyan]{name}[/bold cyan]  [dim](ID: {selected_id})[/dim]"
        )
