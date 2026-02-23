from __future__ import annotations

from typing import Any, Dict, List, Optional

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from src.cli.screen import SCREEN_EXIT, AppScreen, ScreenSignal, run_screen
from src.cli.views.device_views import render_device_nav_panel, render_device_table


class DeviceListScreen(AppScreen):
    """
    Interactive audio device selector.

    Navigation:
      ↑ / k   — move cursor up
      ↓ / j   — move cursor down
      Enter   — confirm selection and exit
      Esc / q — cancel without changes
    """

    cursor:     reactive[int] = reactive(0)
    status_msg: reactive[str] = reactive("")

    def __init__(
        self,
        devices: List[Dict[str, Any]],
        current_device_id: Optional[int],
    ) -> None:
        super().__init__()
        self.devices           = devices
        self.current_device_id = current_device_id
        self.result: Optional[int] = None

        # Start cursor on the currently saved device
        self.cursor = 0
        if current_device_id is not None:
            for i, d in enumerate(devices):
                if d["id"] == current_device_id:
                    self.cursor = i
                    break

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(id="device_table_zone")
        yield Static(id="device_nav_zone")

    def build_layout(self) -> None:
        return None

    def refresh_zones(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Reactive watchers → re-render affected zones
    # ------------------------------------------------------------------

    def watch_cursor(self, _: int) -> None:
        if self.is_mounted:
            self._render_table()

    def watch_status_msg(self, msg: str) -> None:
        if self.is_mounted:
            self._render_footer(msg)

    def on_mount(self) -> None:
        super().on_mount()
        self._render_table()
        self._render_footer()

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def handle_action(self, key: str) -> ScreenSignal:  # type: ignore[override]
        n = len(self.devices)
        if key in ("escape", "q"):
            return SCREEN_EXIT
        if key in ("up", "k"):
            self.cursor = max(0, self.cursor - 1)
        elif key in ("down", "j"):
            self.cursor = min(n - 1, self.cursor + 1)
        elif key == "enter" and n:
            self.result = self.devices[self.cursor]["id"]
            return SCREEN_EXIT
        return None  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _render_table(self) -> None:
        try:
            self.query_one("#device_table_zone", Static).update(
                render_device_table(
                    self.devices,
                    self.current_device_id,
                    self.cursor,
                )
            )
        except Exception:
            pass

    def _render_footer(self, status_msg: str = "") -> None:
        try:
            self.query_one("#device_nav_zone", Static).update(
                render_device_nav_panel(status_msg=status_msg or None)
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def run_device_list_ui(
    devices: List[Dict[str, Any]],
    current_device_id: Optional[int] = None,
) -> Optional[int]:
    """Launch the interactive device-list screen.

    Returns the confirmed device ID, or ``None`` if the user cancelled.
    """
    if not devices:
        return None
    screen = DeviceListScreen(devices, current_device_id)
    run_screen(screen)
    return screen.result
