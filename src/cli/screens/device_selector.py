from typing import List, Dict, Any, Optional
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from src.cli.screen import AppScreen, SCREEN_EXIT, run_screen
# No longer using _input.py for key detection, using Textual's key names.

console = Console()


from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widgets import Static

class _DeviceSelectorScreen(AppScreen):
    """AppScreen for interactive audio device selection."""
    
    # Reactive state
    cursor: reactive[int] = reactive(0)

    def __init__(self, devices: List[Dict[str, Any]], current_device_id: Optional[int]):
        super().__init__()
        self.devices           = devices
        self.current_device_id = current_device_id
        self.result: Optional[int] = None

        # Start cursor on currently-configured device
        initial_cursor = 0
        if current_device_id is not None:
            for i, d in enumerate(devices):
                if d["id"] == current_device_id:
                    initial_cursor = i
                    break
        self.cursor = initial_cursor

    def compose(self) -> ComposeResult:
        yield Static(id="device_selector_main")

    def watch_cursor(self, _) -> None:
        if self.is_mounted:
            try:
                self.query_one("#device_selector_main").update(self._build_group())
            except Exception:
                pass

    def on_mount(self) -> None:
        super().on_mount()
        # Initial draw
        if self.is_mounted:
            try:
                self.query_one("#device_selector_main").update(self._build_group())
            except Exception:
                pass

    def build_layout(self) -> None:
        return None

    def refresh_zones(self) -> None:
        pass

    def handle_action(self, key: str):  # type: ignore[override]
        if key == "escape":
            return SCREEN_EXIT
        if key == "enter":
            self.result = self.devices[self.cursor]["id"]
            return SCREEN_EXIT
        if key in ("up", "k"):
            self.cursor = max(0, self.cursor - 1)
            return True
        if key in ("down", "j"):
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
