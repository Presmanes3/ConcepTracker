"""
PauseTranscriptionScreen â€” minimalist inline viewer/editor.

Follows CLI_VISUAL_ASPECT.MD and CLI_ARCHITECTURE.MD:
  - Views produce all Rich renderables (Panels, Text).
  - Screen only wires Textual widgets and delegates to Views.

Layout:
  Row 1  #p_status       â†’ status bar (PAUSED, time, words, tokens)
  Row 2  #p_main_row     â†’ Horizontal container (height: 1fr)
           #p_menu       â†’ menu panel  (left, fixed width)
           #p_flex       â†’ flexible zone (right, 1fr):
                           READ  â†’ VerticalScroll with rendered Markdown transcript
                           EDIT  â†’ MarkdownEditor (TextArea left | preview right)
  Footer #p_footer       â†’ context-sensitive key hints (dock: bottom)

Key-handling strategy (critical):
  MarkdownEditor (which contains a TextArea) is mounted/unmounted dynamically.
  In READ mode no focusable child exists â†’ key events always reach on_key.

Modes:
  READ  â€” Right panel: scrollable Markdown transcript.
  EDIT  â€” Right panel: MarkdownEditor component.
          Ctrl+S saves and returns to READ. Esc cancels.
"""
from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.events import Key
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static

from src.cli.components.ai_editor import AIEditor
from src.cli.components.editor import MarkdownEditor
from src.cli.views.pause_transcription_views import (
    PAUSE_MENU_ITEMS,
    _PARENT_IDS,
    render_pause_footer,
    render_pause_menu,
    render_pause_status,
    render_pause_transcript_body,
)


class PauseTranscriptionScreen(Screen):
    """Pause overlay.  Dismissed with ``(action: str, edited_text: str | None)``."""

    BINDINGS = [
        Binding("ctrl+c",  "discard_app",  "Discard", priority=True, show=False),
        Binding("ctrl+r",  "run_ai",       "Run AI",  priority=True, show=False),
        Binding("ctrl+a",  "accept_ai",    "Accept",  priority=True, show=False),
        Binding("escape",  "escape_mode",  "Cancel",  priority=True, show=False),
    ]

    def action_discard_app(self) -> None:
        """Ctrl+C -> discard the session entirely from the pause screen."""
        self.dismiss(("discard", None))

    def action_run_ai(self) -> None:
        """Ctrl+R — submit the prompt to the AI pipeline."""
        if self._mode != "enhance_prompt":
            return
        try:
            editor = self.query_one("#p_enhance_zone", AIEditor)
            editor.start_loading()
            self._run_ai_worker(self._full_text, editor.prompt_text or None)
        except Exception:
            pass

    def action_accept_ai(self) -> None:
        """Ctrl+A — accept the current AI result."""
        if self._mode != "enhance_prompt":
            return
        try:
            editor = self.query_one("#p_enhance_zone", AIEditor)
            if editor._has_result:
                self._full_text = editor.result_text
                self._leave_enhance_prompt()
        except Exception:
            pass

    def action_escape_mode(self) -> None:
        if self._mode == "enhance_prompt":
            self._leave_enhance_prompt()
        elif self._mode == "edit":
            self._leave_edit()
        else:
            self._dismiss("resume")

    CSS = """
    PauseTranscriptionScreen {
        layout: vertical;
        background: $background;
    }

    #p_status {
        height: auto;
        margin-bottom: 1;
    }

    /* Main content row: menu + flexible right zone */
    #p_main_row { height: 1fr; }

    /* Left: action menu â€” Rich Panel draws its own border */
    #p_menu { width: 32; height: 1fr; }

    /* Right: transcript scroll container (READ mode).
       grey37 (#5f5f5f) matches the visual weight of Rich's dim border. */
    #p_flex {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    #p_flex_content { height: auto; }

    /* Right: MarkdownEditor (EDIT mode) â€” fills the same slot */
    MarkdownEditor { width: 1fr; }

    /* Enhance-prompt zone â€” AIEditor mounts here, uses its own CSS */
    #p_enhance_zone { width: 1fr; height: 1fr; }

    #p_footer { height: auto; dock: bottom; }
    """

    # â”€â”€ Reactive state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    menu_index: reactive[int] = reactive(0)

    def watch_menu_index(self, value: int) -> None:
        if self.is_mounted and self._mode == "read":
            self._update_menu()

    # â”€â”€ Init â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def __init__(self, full_text: str, time_str: str) -> None:
        super().__init__()
        self._full_text     = full_text
        self._original_text = full_text
        self._time_str      = time_str
        self._mode          = "read"
        self._expanded: set[str] = set()
        self.menu_index     = 0


    def _visible_items(self) -> list:
        """Return only the menu items that should currently be visible."""
        return [
            item for item in PAUSE_MENU_ITEMS
            if item[2] is None or item[2] in self._expanded
        ]

    # â”€â”€ Compose â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def compose(self) -> ComposeResult:
        """Static skeleton â€” no focusable widgets in READ mode.

        In EDIT mode MarkdownEditor is mounted dynamically after #p_menu
        and removed on exit.
        """
        yield Static(id="p_status")
        with Horizontal(id="p_main_row"):
            yield Static(id="p_menu")
            with VerticalScroll(id="p_flex"):
                yield Static(id="p_flex_content")
        yield Static(id="p_footer")

    def on_mount(self) -> None:
        self.focus()
        self._refresh_all()

    # â”€â”€ Key handling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_key(self, event: Key) -> None:
        key = event.key

        if self._mode == "read":
            if key in ("up", "k"):
                if self.menu_index > 0:
                    self.menu_index -= 1
                event.stop()

            elif key in ("down", "j"):
                self.menu_index = min(len(self._visible_items()) - 1, self.menu_index + 1)
                event.stop()

            elif key in ("enter", "space"):
                self._trigger_menu_action()
                event.stop()

            elif key == "e":
                self._enter_edit()
                event.stop()

            elif key == "s":
                self._dismiss("save")
                event.stop()

            elif key == "ctrl+x":
                self._dismiss("discard")
                event.stop()

        elif self._mode == "edit":
            if key == "ctrl+s":
                self._save_edit()
                event.stop()

        elif self._mode == "enhance_prompt":
            pass  # ctrl+r / ctrl+a handled by priority BINDINGS on this Screen

    # â”€â”€ Menu dispatch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _trigger_menu_action(self) -> None:
        visible = self._visible_items()
        if not visible:
            return
        _, action_id, _parent = visible[self.menu_index]

        if action_id in _PARENT_IDS:
            # Toggle expand/collapse; keep cursor on this item.
            if action_id in self._expanded:
                self._expanded.discard(action_id)
                # If cursor was on a now-hidden child, move back to parent.
                new_visible = self._visible_items()
                self.menu_index = min(self.menu_index, len(new_visible) - 1)
            else:
                self._expanded.add(action_id)
            self._update_menu()
            return

        if action_id == "edit":
            self._enter_edit()
        elif action_id == "resume":
            self._dismiss("resume")
        elif action_id == "enhance":
            self._dismiss("enhance")
        elif action_id == "enhance_prompt":
            self._enter_enhance_prompt()
        elif action_id == "save":
            self._dismiss("save")
        elif action_id == "discard":
            self._dismiss("discard")

    # â”€â”€ Mode transitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _enter_edit(self) -> None:
        """EDIT mode: hide transcript scroll, mount MarkdownEditor in its place."""
        self._mode = "edit"
        self.query_one("#p_flex", VerticalScroll).display = False
        self.mount(
            MarkdownEditor(initial_text=self._full_text, id="p_edit_zone"),
            after="#p_menu",
        )
        # MarkdownEditor.on_mount focuses its TextArea automatically.
        self._refresh_status()
        self._update_menu()
        self._refresh_footer()

    def _leave_edit(self) -> None:
        """READ mode: remove MarkdownEditor, restore transcript viewer."""
        self._mode = "read"
        try:
            self.query_one("#p_edit_zone", MarkdownEditor).remove()
        except Exception:
            pass
        self.query_one("#p_flex", VerticalScroll).display = True
        self.focus()
        self._refresh_all()

    def _save_edit(self) -> None:
        """Persist edits from MarkdownEditor, then leave edit mode."""
        try:
            self._full_text = self.query_one("#p_edit_zone", MarkdownEditor).text
        except Exception:
            pass
        self._leave_edit()

    def _dismiss(self, action: str) -> None:
        edited = self._full_text if self._full_text != self._original_text else None
        self.dismiss((action, edited))

    # â”€â”€ Enhance-prompt mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _enter_enhance_prompt(self) -> None:
        """Show AIEditor for side-by-side AI enhancement with prompt."""
        self._mode = "enhance_prompt"
        self.query_one("#p_flex", VerticalScroll).display = False
        self.mount(
            AIEditor(original_text=self._full_text, id="p_enhance_zone"),
            after="#p_menu",
        )
        # AIEditor.on_mount focuses the prompt TextArea automatically.
        self._update_menu()
        self._refresh_footer()

    def _leave_enhance_prompt(self) -> None:
        """Cancel enhance-prompt mode, restore transcript view."""
        self._mode = "read"
        try:
            self.query_one("#p_enhance_zone", AIEditor).remove()
        except Exception:
            pass
        self.query_one("#p_flex", VerticalScroll).display = True
        self.focus()
        self._refresh_all()

    # â”€â”€ AIEditor message handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def on_ai_editor_submit_prompt(self, message: AIEditor.SubmitPrompt) -> None:
        """User pressed Ctrl+R in the AIEditor prompt â€” kick off the AI worker."""
        message.editor.start_loading()
        self._run_ai_worker(self._full_text, message.prompt or None)

    def on_ai_editor_accept(self, message: AIEditor.Accept) -> None:
        """User pressed Ctrl+A â€” accept the result and return to READ mode."""
        self._full_text = message.result
        self._leave_enhance_prompt()

    @work(thread=True, exclusive=True)
    def _run_ai_worker(self, text: str, prompt: str | None) -> None:
        """AI enhancement in a background thread â€” does not block the TUI.

        Uses workflow.stream() so each completed agent node triggers a
        call_from_thread that updates the spinner title with the agent name.
        """
        try:
            from src.cli.client.http_client import ConcepTrackerClient
            with ConcepTrackerClient() as client:
                result = client.enhance_transcription(text, prompt)
            if result.error:
                self.app.call_from_thread(self._on_enhance_error, str(result.error))
            else:
                self.app.call_from_thread(self._on_enhance_done, result.enhanced_text)
        except Exception as exc:
            self.app.call_from_thread(self._on_enhance_error, str(exc))

    def _on_agent_step(self, agent_label: str) -> None:
        """Update the running agent label in the AIEditor spinner."""
        try:
            self.query_one("#p_enhance_zone", AIEditor).update_agent(agent_label)
        except Exception:
            pass

    def _on_enhance_done(self, enhanced_text: str) -> None:
        """Called on the main thread when the AI worker finishes."""
        try:
            self.query_one("#p_enhance_zone", AIEditor).set_result(enhanced_text)
        except Exception:
            pass
        self._refresh_footer()

    def _on_enhance_error(self, error_msg: str) -> None:
        """Called on the main thread when the AI worker fails."""
        try:
            self.query_one("#p_enhance_zone", AIEditor).set_error(error_msg)
        except Exception:
            pass

    # â”€â”€ Refresh helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def refresh_zones(self) -> None:
        """Public entry-point for external callers (e.g. after resume)."""
        self._refresh_all()

    def _refresh_all(self) -> None:
        self._refresh_status()
        self._refresh_transcript()
        self._update_menu()
        self._refresh_footer()

    def _refresh_status(self) -> None:
        words  = len(self._full_text.split()) if self._full_text.strip() else 0
        tokens = int(words * 1.3)
        self.query_one("#p_status", Static).update(
            render_pause_status(self._time_str, words, tokens)
        )

    def _refresh_transcript(self) -> None:
        """Update the transcript VerticalScroll (READ mode only)."""
        try:
            scroll = self.query_one("#p_flex", VerticalScroll)
            scroll.border_title = "[bold dim]Transcript[/bold dim]"
            self.query_one("#p_flex_content", Static).update(
                render_pause_transcript_body(self._full_text)
            )
        except Exception:
            pass

    def _update_menu(self) -> None:
        self.query_one("#p_menu", Static).update(
            render_pause_menu(
                self._visible_items(),
                self.menu_index,
                has_focus=(self._mode == "read"),
                expanded_ids=self._expanded,
            )
        )

    def _refresh_footer(self) -> None:
        self.query_one("#p_footer", Static).update(
            render_pause_footer(self._mode)
        )
