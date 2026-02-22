from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.console import Group, RenderableType

from src.cli._input import _is_down, _is_expand, _is_quit, _is_select, _is_up
from src.cli.screen import SCREEN_EXIT, AppScreen, ScreenSignal, run_screen
from src.cli.views.device_views import render_device_nav_panel, render_device_table


class DeviceListScreen(AppScreen):
    """
    AppScreen subclass that renders an audio device list with two stacked Panels:
      1. A table of available input devices (cursor ▶, pending ●, saved ★).
      2. A navigation hint panel.

    The user navigates with ↑/↓, presses Space to mark a pending selection,
    and Enter to confirm + exit. q/Esc exits without saving.
    The confirmed device ID is written to ``self.result`` before exit.
    """

    def __init__(
        self,
        devices: List[Dict[str, Any]],
        current_device_id: Optional[int],
    ) -> None:
        self.devices           = devices
        self.current_device_id = current_device_id
        self.result: Optional[int] = None
        self._running          = True

        # pending_id: Space-selected device (not yet saved to disk)
        self.pending_id: Optional[int] = current_device_id

        # Initialise cursor on the currently configured device (fallback: 0)
        self.cursor = 0
        if current_device_id is not None:
            for i, d in enumerate(devices):
                if d["id"] == current_device_id:
                    self.cursor = i
                    break

    def _build_renderable(self) -> Group:
        """Assemble the two panels as a Group (height driven by content)."""
        return Group(
            render_device_table(
                self.devices,
                self.current_device_id,
                self.cursor,
                pending_id=self.pending_id,
            ),
            render_device_nav_panel(),
        )

    def build_layout(self) -> RenderableType:
        self._layout = self._build_renderable()
        return self._layout

    def refresh_zones(self) -> None:
        self._layout = self._build_renderable()

    def handle_key(self, kind: Optional[str], key: Optional[bytes]) -> ScreenSignal:  # type: ignore[override]
        if _is_quit(kind, key):
            return SCREEN_EXIT
        if _is_up(kind, key):
            self.cursor = max(0, self.cursor - 1)
            return True  # type: ignore[return-value]
        if _is_down(kind, key):
            self.cursor = min(len(self.devices) - 1, self.cursor + 1)
            return True  # type: ignore[return-value]
        if _is_expand(kind, key):  # Space → mark pending
            self.pending_id = self.devices[self.cursor]["id"]
            return True  # type: ignore[return-value]
        if _is_select(kind, key):  # Enter → save & exit
            self.result = self.pending_id
            return SCREEN_EXIT
        return None


def run_device_list_ui(
    devices: List[Dict[str, Any]],
    current_device_id: Optional[int] = None,
) -> Optional[int]:
    """Launch the interactive device-list screen.

    Returns the device ID the user confirmed with Enter,
    or ``None`` if they cancelled with q/Esc.
    """
    if not devices:
        return None
    screen = DeviceListScreen(devices, current_device_id)
    run_screen(screen)
    return screen.result
