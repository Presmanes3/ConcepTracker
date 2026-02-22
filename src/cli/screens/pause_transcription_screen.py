"""
PauseTranscriptionScreen — TUI pause menu for live transcription.

Uses Layout (terminal-filling) so height is always stable — no scroll, no blink:

  ┌─────────────────────────────────────────────────────────┐
  │  Status  (size=3)                                       │
  ├────────────────────┬────────────────────────────────────┤
  │  Actions (size=26) │  Transcription / Edit pane         │
  │  ▶ Enhance…        │  (fills remaining width+height)    │
  │    Save            │                                    │
  │    Edit Text       │  → inline editor in "edit" mode    │
  │    …               │                                    │
  └────────────────────┴────────────────────────────────────┘

After run_screen() returns:
  screen.result      str           — enhance / save / modify / continue / restart / discard
  screen.edited_text Optional[str] — set when the user confirms an inline edit; else None
"""
from __future__ import annotations

from typing import Optional

from rich.layout import Layout

from src.cli._input import _is_down, _is_quit, _is_select, _is_up
from src.cli.screen import SCREEN_EXIT, AppScreen, ScreenSignal, run_screen
from src.cli.views.pause_transcription_views import (
    PAUSE_MENU_COL_WIDTH,
    PAUSE_MENU_ITEMS,
    render_pause_content_editor,
    render_pause_content_text,
    render_pause_menu,
    render_pause_status,
)


class PauseTranscriptionScreen(AppScreen):
    """
    Interactive pause-menu screen.  Retrieve results via
    ``screen.result`` and ``screen.edited_text`` after run_screen() returns.
    """

    alternate_screen = True

    def __init__(self, full_text: str, time_str: str) -> None:
        self._full_text = full_text
        self._time_str  = time_str
        self._words     = len(full_text.split()) if full_text.strip() else 0
        self._tokens    = int(self._words * 1.3)

        self._mode        : str = "menu"   # "menu" | "edit"
        self._menu_index  : int = 0

        self._edit_buffer : str = full_text
        self._edit_cursor : int = len(full_text)

        self.result       : str           = "discard"
        self.edited_text  : Optional[str] = None

    # ── AppScreen interface ────────────────────────────────────────────────────

    def build_layout(self) -> Layout:
        """
        Build the Layout tree ONCE.  refresh_zones() updates zones in-place —
        no object recreation on every keypress → stable height → no blink.
        """
        root = Layout()
        root.split_column(
            Layout(name="status", size=3),
            Layout(name="body"),
        )
        root["body"].split_row(
            Layout(name="menu",    size=PAUSE_MENU_COL_WIDTH),
            Layout(name="content"),
        )
        return root

    def refresh_zones(self) -> None:
        self._layout["status"].update(  # type: ignore[index]
            render_pause_status(self._time_str, self._words, self._tokens)
        )
        self._layout["menu"].update(    # type: ignore[index]
            render_pause_menu(self._menu_index, is_edit_mode=self._mode == "edit")
        )
        self._layout["content"].update( # type: ignore[index]
            render_pause_content_editor(self._edit_buffer, self._edit_cursor)
            if self._mode == "edit" else
            render_pause_content_text(self._full_text)
        )

    def handle_key(
        self, kind: Optional[str], key: Optional[bytes]
    ) -> ScreenSignal:
        if self._mode == "edit":
            return self._handle_edit_key(kind, key)
        return self._handle_menu_key(kind, key)

    # ── Key handlers ───────────────────────────────────────────────────────────

    def _handle_menu_key(
        self, kind: Optional[str], key: Optional[bytes]
    ) -> ScreenSignal:
        if _is_quit(kind, key):
            self.result = "discard"
            return SCREEN_EXIT

        if _is_up(kind, key):
            self._menu_index = max(0, self._menu_index - 1)
            return True

        if _is_down(kind, key):
            self._menu_index = min(len(PAUSE_MENU_ITEMS) - 1, self._menu_index + 1)
            return True

        if _is_select(kind, key):
            _, action = PAUSE_MENU_ITEMS[self._menu_index]
            if action == "modify":
                self._edit_buffer = self._full_text
                self._edit_cursor = len(self._full_text)
                self._mode = "edit"
                return True
            self.result = action
            return SCREEN_EXIT

        return None

    def _handle_edit_key(
        self, kind: Optional[str], key: Optional[bytes]
    ) -> ScreenSignal:
        if kind == "char" and key is not None:
            # Esc / Ctrl-C → cancel, back to menu
            if key in (b"\x1b", b"\x03"):
                self._mode = "menu"
                return True

            # Enter → confirm, back to menu
            if key in (b"\r", b"\n"):
                self._full_text  = self._edit_buffer
                self._words      = len(self._full_text.split()) if self._full_text.strip() else 0
                self._tokens     = int(self._words * 1.3)
                self.edited_text = self._full_text
                self._mode       = "menu"
                return True

            # Backspace
            if key in (b"\x7f", b"\x08"):
                if self._edit_cursor > 0:
                    self._edit_buffer = (
                        self._edit_buffer[: self._edit_cursor - 1]
                        + self._edit_buffer[self._edit_cursor :]
                    )
                    self._edit_cursor -= 1
                return True

            # Printable character
            char = key.decode("utf-8", errors="ignore")
            if char and ord(char) >= 32:
                self._edit_buffer = (
                    self._edit_buffer[: self._edit_cursor]
                    + char
                    + self._edit_buffer[self._edit_cursor :]
                )
                self._edit_cursor += 1
                return True

        # Left arrow  (Windows arrow/K · Unix escape/[D)
        if (kind == "arrow" and key == b"K") or (kind == "escape" and key == b"[D"):
            self._edit_cursor = max(0, self._edit_cursor - 1)
            return True

        # Right arrow  (Windows arrow/M · Unix escape/[C)
        if (kind == "arrow" and key == b"M") or (kind == "escape" and key == b"[C"):
            self._edit_cursor = min(len(self._edit_buffer), self._edit_cursor + 1)
            return True

        return None


# ── Public helper ──────────────────────────────────────────────────────────────

def run_pause_transcription_ui(
    full_text: str,
    time_str: str,
) -> PauseTranscriptionScreen:
    """
    Open the pause-menu screen and block until the user makes a choice.
    Returns the screen so the caller can read ``.result`` and ``.edited_text``.
    """
    screen = PauseTranscriptionScreen(full_text=full_text, time_str=time_str)
    run_screen(screen)
    return screen
