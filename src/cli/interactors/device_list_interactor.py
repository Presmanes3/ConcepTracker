"""DeviceListInteractor — fetch devices via REST API, show selector, persist choice."""
from __future__ import annotations

from typing import List, Optional

import typer
from rich.console import Console

from shared.schemas.api.transcription import DeviceResponse
from src.cli.client.http_client import ConcepTrackerClient
from src.cli.screens.device_list_screen import run_device_list_ui


class DeviceListInteractor:
    """Fetch available audio devices, open the selector UI, and persist the choice."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Scan local hardware and sync selection with backend.
        
        Raises:
            typer.Exit: When no devices are found.
        """
        # 1. Try to fetch from backend (SSoT for configuration)
        # 2. ALSO scan local devices (since CLI runs where the mic is)
        with ConcepTrackerClient() as client:
            with self.console.status("[dim]Scanning audio input devices…[/dim]"):
                try:
                    backend_devices = client.list_devices()
                except Exception:
                    backend_devices = []

        # Scan local devices using sounddevice
        local_devices = []
        try:
            import sounddevice as sd
            sd_devices = sd.query_devices()
            for i, d in enumerate(sd_devices):
                if d.get("max_input_channels", 0) > 0:
                    local_devices.append({
                        "id": i,
                        "name": d.get("name", f"Device {i}"),
                        "channels": d.get("max_input_channels"),
                        "default": i == sd.default.device[0]
                    })
        except ImportError:
            self.console.print("[yellow]Warning: 'sounddevice' not installed. Local device detection disabled.[/yellow]")
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not scan local devices: {e}[/yellow]")

        # Merge results: use local devices for the list, but preserve 'active' state from backend
        configured_id = next((d.id for d in backend_devices if d.active), None)
        
        # If no local devices found, and no backend devices, error out
        if not local_devices and not backend_devices:
            self.console.print("[red]No audio input devices found on this system.[/red]")
            raise typer.Exit(1)

        # Build DeviceResponse list from local devices if available
        device_responses: List[DeviceResponse] = []
        if local_devices:
            for ld in local_devices:
                device_responses.append(DeviceResponse(
                    id=ld["id"],
                    name=ld["name"],
                    channels=ld["channels"],
                    default=ld["default"],
                    active=(ld["id"] == configured_id)
                ))
        else:
            device_responses = backend_devices

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
