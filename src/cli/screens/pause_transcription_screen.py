"""
PauseTranscriptionScreen — minimalist inline viewer/editor.

Follows CLI_VISUAL_ASPECT.MD and CLI_ARCHITECTURE.MD:
  - Views produce all Rich renderables (Panels, Text).
  - Screen only wires Textual widgets and delegates to Views.
  - Status Panel at top   → render_pause_status()
  - Content → Static (read) or [Static + TextArea] (edit) — mounted dynamically
  - Footer at bottom      → render_pause_footer()

Key-handling strategy (critical):
  The TextArea is mounted/unmounted dynamically instead of toggled via
  display=False.  This guarantees that in READ mode there are zero focusable
  child widgets → key events reach the Screen's on_key unconditionally.

Modes:
  READ  — full-width Rich-Markdown Panel (via View). Press 'e' to edit.
  EDIT  — left half: live preview Static; right half: TextArea editor.
          Ctrl+S saves and returns to READ. Esc cancels.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Static, TextArea

from src.cli.views.pause_transcription_views import (
    render_pause_footer,
    render_pause_status,
    render_pause_transcript,
)


class PauseTranscriptionScreen(Screen):
    """Pause overlay.  Dismissed with ``(action: str, edited_text: str | None)``."""

    # Ctrl+C needs priority=True to override Textual's app-level quit.
    # All other keys are handled contextually in on_key.
    BINDINGS = [
        Binding("ctrl+c", "discard_app", "Discard", priority=True, show=False),
    ]

    def action_discard_app(self) -> None:
        """Ctrl+C → discard the session entirely from the pause screen."""
        self.dismiss(("discard", None))

    # Minimal CSS — pure layout + TextArea restyled to match Rich Panel aesthetic.
    # All other visual structure (borders, titles, colours) comes from Rich Panels.
    CSS = """
    PauseTranscriptionScreen { layout: vertical; background: $surface; }
    #p_status { height: auto; }
    #p_body   { height: 1fr; }
    #p_read   { width: 1fr; height: 100%; }

    /* TextArea restyled to look like a Rich Panel:
       - round corners  →  ╭─ Edit ──╮  (same as Rich Panel default)
       - green border   →  matches the Preview panel on the right
       - no inner padding offset, transparent background               */
    #p_edit {
        width: 1fr;
        height: 100%;
        border: round $success;
        border-title-color: $success;
        border-title-align: left;
        background: $surface;
        padding: 0 1;
    }
    #p_edit:focus {
        border: round $success;
    }

    #p_footer { height: auto; }
    """

    # ── Init ──────────────────────────────────────────────────────────────────

    def __init__(self, full_text: str, time_str: str) -> None:
        super().__init__()
        self._full_text     = full_text
        self._original_text = full_text
        self._time_str      = time_str
        self._mode          = "read"

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """READ-mode skeleton.  TextArea is mounted dynamically on edit entry."""
        yield Static(id="p_status")
        with Horizontal(id="p_body"):
            yield Static(id="p_read")   # Rich Panel — always present
        yield Static(id="p_footer")

    def on_mount(self) -> None:
        self._refresh_read_panel()
        self._refresh_status()
        self._refresh_footer()

    # ── Key handling ──────────────────────────────────────────────────────────

    def on_key(self, event: Key) -> None:
        """
        Mnemonic key scheme — consistent with the rest of the app:

        READ mode (no focusable child → all keys arrive here):
          Esc     Resume live transcription
          e       Edit transcript text
          a       Enhance with AI  (not yet implemented — stub)
          s       Save note
          ctrl+x  Discard / cancel session  (ctrl = destructive guard)

        EDIT mode (TextArea has focus):
          ctrl+s  Commit edit and return to READ
          Esc     Cancel edit without saving
        """
        key = event.key

        if self._mode == "read":
            if key == "escape":
                self._dismiss("resume")
            elif key == "e":
                self._enter_edit()
            elif key == "s":
                self._dismiss("save")
            elif key == "ctrl+x":
                self._dismiss("discard")
            if key in {"escape", "e", "s", "ctrl+x"}:
                event.stop()
        elif self._mode == "edit":
            if key == "ctrl+s":
                self._save_edit()
                event.stop()
            elif key == "escape":
                self._leave_edit()
                event.stop()
            elif key == "ctrl+x":
                self._dismiss("discard")
                event.stop()

    # ── Mode transitions ──────────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Live preview: re-render the Rich Markdown panel on every keystroke."""
        if self._mode == "edit":
            self.query_one("#p_read", Static).update(
                render_pause_transcript(event.text_area.text, title="Preview")
            )

    def _enter_edit(self) -> None:
        """Switch to EDIT mode: mount TextArea to the LEFT of the preview."""
        read = self.query_one("#p_read", Static)
        # Refresh preview label before showing split
        read.update(render_pause_transcript(self._full_text, title="Preview"))

        edit = TextArea(id="p_edit")
        edit.border_title    = "✏  Edit"
        edit.border_subtitle = "Ctrl+S · Esc"
        body = self.query_one("#p_body", Horizontal)
        # before=read → editor appears on the left, preview stays on the right
        body.mount(edit, before=read)

        def _ready() -> None:
            edit.load_text(self._full_text)
            edit.focus()
            self._mode = "edit"
            self._refresh_status()
            self._refresh_footer()

        self.call_after_refresh(_ready)

    def _leave_edit(self) -> None:
        """Unmount TextArea and return to full-width READ mode."""
        try:
            self.query_one("#p_edit", TextArea).remove()
        except Exception:
            pass

        self._mode = "read"
        self._refresh_read_panel()   # back to full-width "Transcript" label
        self._refresh_status()
        self._refresh_footer()

    def _dismiss(self, action: str) -> None:
        """Dismiss the screen with the given action and the current text."""
        edited = self._full_text if self._full_text != self._original_text else None
        self.dismiss((action, edited))

    def _save_edit(self) -> None:
        if self._mode == "edit":
            try:
                self._full_text = self.query_one("#p_edit", TextArea).text
            except Exception:
                pass
            self._leave_edit()

    # ── UI refresh helpers ────────────────────────────────────────────────────

    def _refresh_stats(self) -> tuple[int, int]:
        words  = len(self._full_text.split()) if self._full_text.strip() else 0
        tokens = int(words * 1.3)
        return words, tokens

    def _refresh_status(self) -> None:
        words, tokens = self._refresh_stats()
        self.query_one("#p_status", Static).update(
            render_pause_status(self._time_str, words, tokens)
        )

    def _refresh_read_panel(self) -> None:
        self.query_one("#p_read", Static).update(
            render_pause_transcript(self._full_text)
        )

    def _refresh_footer(self) -> None:
        self.query_one("#p_footer", Static).update(
            render_pause_footer(self._mode)
        )

