from typing import List, Dict, Any, Optional
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from src.cli.screen import AppScreen, SCREEN_EXIT, run_screen
from src.cli._input import _getch_with_timeout, _is_up, _is_down, _is_select, _is_quit

console = Console()


class _DeviceSelectorScreen(AppScreen):
    """AppScreen for interactive audio device selection."""

    def __init__(self, devices: List[Dict[str, Any]], current_device_id: Optional[int]):
        self.devices           = devices
        self.current_device_id = current_device_id
        self.result: Optional[int] = None
        self._running = True

        # Start cursor on currently-configured device
        self.cursor = 0
        if current_device_id is not None:
            for i, d in enumerate(devices):
                if d["id"] == current_device_id:
                    self.cursor = i
                    break

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_group(self) -> Group:
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Sel", justify="center", width=4)
        table.add_column("ID",  justify="right",  width=4)
        table.add_column("Device Name", style="cyan")
        table.add_column("Channels",    justify="right", width=10)

        for i, device in enumerate(self.devices):
            is_cursor = (i == self.cursor)
            sel_text  = "[bold green]>[/bold green]" if is_cursor else " "
            row_style = "reverse" if is_cursor else ""

            name = device["name"]
            if device.get("default"):
                name += " [dim](System Default)[/dim]"
            if device["id"] == self.current_device_id:
                name += " [bold yellow](Current)[/bold yellow]"

            table.add_row(
                sel_text,
                str(device["id"]),
                name,
                str(device["channels"]),
                style=row_style,
            )

        instructions = Text(
            "↑/↓: Move | Enter: Select | Esc/q: Cancel",
            style="dim italic",
            justify="center",
        )
        return Group(
            Panel(table, title="[bold]Select Audio Input Device[/bold]", border_style="blue"),
            instructions,
        )

    # ── AppScreen interface ───────────────────────────────────────────────────

    def build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(Layout(name="content"))
        return layout

    def refresh_zones(self) -> None:
        self._layout["content"].update(self._build_group())

    def handle_key(self, kind, key):  # type: ignore[override]
        if _is_quit(kind, key):
            return SCREEN_EXIT
        if _is_select(kind, key):
            self.result = self.devices[self.cursor]["id"]
            return SCREEN_EXIT
        if _is_up(kind, key):
            self.cursor = max(0, self.cursor - 1)
            return True
        if _is_down(kind, key):
            self.cursor = min(len(self.devices) - 1, self.cursor + 1)
            return True
        return None


def select_audio_device_ui(
    devices: List[Dict[str, Any]],
    current_device_id: Optional[int] = None,
) -> Optional[int]:
    """Interactive UI for selecting an audio input device."""
    if not devices:
        console.print("[red]No input devices found.[/red]")
        return None

    screen = _DeviceSelectorScreen(devices, current_device_id)
    run_screen(screen)
    return screen.result
