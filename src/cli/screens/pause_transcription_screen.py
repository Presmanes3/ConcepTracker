"""
PauseTranscriptionScreen — minimalist inline viewer/editor.

Follows CLI_VISUAL_ASPECT.MD:
  - Status Panel at top   (render_pause_status)
  - ContentSwitcher body  (read: Rich Panel / edit: TextArea)
  - Footer at bottom      (render_pause_footer)

Modes:
  READ  — transcript as Rich Panel. Press 'e' to edit. Esc to resume.
  EDIT  — TextArea editor. Ctrl+S saves. Esc cancels.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Markdown, Static, TextArea

from src.cli.views.pause_transcription_views import (
    render_pause_footer,
    render_pause_status,
)


class PauseTranscriptionScreen(Screen):
    """Pause overlay. Dismissed with ``(action: str, edited_text: str | None)``."""

    CSS = """
    PauseTranscriptionScreen {
        layout: vertical;
        background: $surface;
    }
    #p_status {
        height: auto;
    }
    #p_body {
        height: 1fr;
    }
    #p_md {
        width: 1fr;
        padding: 1 2;
        border-right: solid $accent;
    }
    #p_edit_pane {
        width: 1fr;
        border: solid $accent;
        border-title-color: $accent;
    }
    #p_footer {
        height: auto;
    }
    """

    # priority=True intercepts BEFORE any focused child widget (Markdown, TextArea)
    BINDINGS = [
        Binding("escape", "handle_escape", "Back / Cancel", priority=True),
        Binding("ctrl+s", "save_edit",     "Save Edit",     priority=True),
        Binding("e",      "enter_edit",    "Edit Text",     priority=True, show=False),
    ]

    def _on_key(self, event) -> None:
        """Low-level key handler — fires before any widget or binding routing."""
        key = event.key
        if key == "e" and self._mode == "read":
            self.action_enter_edit()
            event.prevent_default()
            event.stop()
        elif key == "escape":
            self.action_handle_escape()
            event.prevent_default()
            event.stop()
        elif key == "ctrl+s" and self._mode == "edit":
            self.action_save_edit()
            event.prevent_default()
            event.stop()

    def __init__(self, full_text: str, time_str: str) -> None:
        super().__init__()
        self._full_text = full_text
        self._original_text = full_text
        self._time_str = time_str
        self._mode = "read"  # "read" or "edit"
        
        # Computed stats
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        """Update word/token counts based on current text."""
        self._words = len(self._full_text.split()) if self._full_text.strip() else 0
        self._tokens = int(self._words * 1.3)

    # ── Compose ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(id="p_status")                       # top — Rich Panel via View
        with Horizontal(id="p_body"):
            yield Markdown(id="p_md")                     # Textual Markdown renderer
            yield TextArea(id="p_edit_pane")              # edit sub-panel (hidden in read)
        yield Static(id="p_footer")                       # bottom — render_footer

    def on_mount(self) -> None:
        self.query_one("#p_edit_pane", TextArea).border_title = "✏  Edit"
        self.query_one("#p_edit_pane", TextArea).border_subtitle = "Ctrl+S save  ·  Esc cancel"
        self._set_mode("read")

    # ── Mode switching ─────────────────────────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        """Switch between 'read' and 'edit', updating all three UI zones."""
        self._mode = mode
        self._refresh_stats()

        # 1. Status bar
        self.query_one("#p_status", Static).update(
            render_pause_status(self._time_str, self._words, self._tokens)
        )

        # 2. Content — Markdown always visible; TextArea shown only in edit mode
        md_widget   = self.query_one("#p_md",        Markdown)
        edit_widget = self.query_one("#p_edit_pane", TextArea)

        text = self._full_text if self._full_text.strip() else "_No transcript yet._"
        md_widget.update(text)         # always refresh the Markdown preview

        if mode == "read":
            edit_widget.display = False
        else:
            edit_widget.load_text(self._full_text)
            edit_widget.display = True
            edit_widget.focus()  # safe: display=True is synchronous

        # 3. Footer
        self.query_one("#p_footer", Static).update(render_pause_footer(mode))


    # ── Actions ────────────────────────────────────────────────────────────────

    def action_handle_escape(self) -> None:
        """Esc: cancel edit → back to read, or resume recording from read."""
        if self._mode == "edit":
            self._set_mode("read")
        else:
            edited = self._full_text if self._full_text != self._original_text else None
            self.dismiss(("resume", edited))

    def action_enter_edit(self) -> None:
        """e: enter edit mode (read mode only)."""
        if self._mode == "read":
            self._set_mode("edit")

    def action_save_edit(self) -> None:
        """Ctrl+S: commit editor text and return to read mode."""
        if self._mode == "edit":
            self._full_text = self.query_one("#p_edit_pane", TextArea).text
            self._set_mode("read")

