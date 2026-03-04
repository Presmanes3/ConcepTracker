"""
PauseTranscriptionScreen — minimalist inline viewer/editor.

Follows CLI_VISUAL_ASPECT.MD and CLI_ARCHITECTURE.MD:
  - Views produce all Rich renderables (Panels, Text).
  - Screen only wires Textual widgets and delegates to Views.

Layout:
  Row 1  #p_status       → status bar (PAUSED, time, words, tokens)
  Row 2  #p_main_row     → Horizontal container (height: 1fr)
           #p_menu       → menu panel  (left, fixed width)
           #p_flex       → flexible zone (right, 1fr):
                           READ  → VerticalScroll with rendered Markdown transcript
                           EDIT  → MarkdownEditor (TextArea left | preview right)
  Footer #p_footer       → context-sensitive key hints (dock: bottom)
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
from src.cli.screens.pause_actions import PauseAction
from src.cli.views.pause_transcription_views import (
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
        Binding("ctrl+left",  "nav_left",  "To Menu",    priority=True, show=False),
        Binding("ctrl+right", "nav_right", "To Content", priority=True, show=False),
        Binding("escape",  "escape_mode",  "Cancel",  priority=True, show=False),
        Binding("up,k",    "nav_up",       "Up",     show=False),
        Binding("down,j",  "nav_down",     "Down",   show=False),
        Binding("enter,space", "select",   "Select", show=False),
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

    def action_nav_left(self) -> None:
        """Jump focus back to the menu from interactive modes."""
        if self._active_action and self._active_action.is_mode:
            self._active_action.leave()
            self._active_action = None
        self.focus()
        self._refresh_all()

    def action_nav_right(self) -> None:
        """Jump focus to the content area (not applicable in READ mode)."""
        if self._active_action and self._active_action.content_widget_id:
            try:
                self.query_one(f"#{self._active_action.content_widget_id}").focus()
            except Exception:
                pass

    def action_escape_mode(self) -> None:
        if self._active_action and self._active_action.is_mode:
            self._active_action.leave()
            self._active_action = None
        else:
            self._dismiss("resume")

    def action_nav_up(self) -> None:
        """Move menu selection up."""
        if self._mode == "read" and self.menu_index > 0:
            self.menu_index -= 1

    def action_nav_down(self) -> None:
        """Move menu selection down."""
        if self._mode == "read":
            self.menu_index = min(len(self._visible_items()) - 1, self.menu_index + 1)

    def action_select(self) -> None:
        """Execute selected menu action."""
        if self._mode == "read":
            self._trigger_menu_action()

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

    /* Left: action menu — Rich Panel draws its own border */
    #p_menu { width: 32; height: 1fr; }

    /* Right: transcript scroll container (READ mode). */
    #p_flex {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    #p_flex_content { height: auto; }

    /* Right: MarkdownEditor (EDIT mode) — fills the same slot */
    MarkdownEditor { width: 1fr; }

    /* Enhance-prompt zone — AIEditor mounts here, uses its own CSS */
    #p_enhance_zone { width: 1fr; height: 1fr; }

    #p_footer { height: auto; dock: bottom; }
    """

    menu_index: reactive[int] = reactive(0)

    def watch_menu_index(self, value: int) -> None:
        if self.is_mounted and self._mode == "read":
            self._update_menu()

    def __init__(self, full_text: str, time_str: str) -> None:
        super().__init__()
        self._full_text     = full_text
        self._original_text = full_text
        self._time_str      = time_str
        self._expanded: set[str] = set()
        self.menu_index     = 0
        self.actions: list[PauseAction] = []
        self._active_action: PauseAction | None = None
        self._init_actions()

    def _init_actions(self) -> None:
        """Define the strategy actions for this screen, mirroring OpenNoteScreen."""
        self.actions = [
            PauseAction("Edit", "edit", mode_key="edit", content_widget_id="p_edit_zone", 
                       enter=self._enter_edit, leave=self._leave_edit),
            PauseAction("Resume", "resume", enter=lambda: self._dismiss("resume")),
            PauseAction("AI", "ai", is_parent=True, enter=self._toggle_ai_expand),
            PauseAction("Enhance", "enhance", parent_id="ai", enter=lambda: self._dismiss("enhance")),
            PauseAction("Enhance with prompt", "enhance_prompt", parent_id="ai", 
                       mode_key="enhance_prompt", content_widget_id="p_enhance_zone",
                       enter=self._enter_enhance_prompt, leave=self._leave_enhance_prompt),
            PauseAction("Save", "save", enter=lambda: self._dismiss("save")),
            PauseAction("Cancel", "discard", enter=lambda: self._dismiss("discard")),
        ]

    def _toggle_ai_expand(self) -> None:
        if "ai" in self._expanded:
            self._expanded.discard("ai")
        else:
            self._expanded.add("ai")
        self._update_menu()

    @property
    def _mode(self) -> str:
        """Current mode string, derived from the active action."""
        return self._active_action.mode_key if self._active_action else "read"

    def _visible_items(self) -> list[PauseAction]:
        """Return actions that should currently be visible in the menu."""
        return [
            a for a in self.actions
            if a.parent_id is None or a.parent_id in self._expanded
        ]

    def compose(self) -> ComposeResult:
        yield Static(id="p_status")
        with Horizontal(id="p_main_row"):
            yield Static(id="p_menu")
            with VerticalScroll(id="p_flex"):
                yield Static(id="p_flex_content")
        yield Static(id="p_footer")

    def on_mount(self) -> None:
        self.focus()
        self._refresh_all()

    def _trigger_menu_action(self) -> None:
        visible = self._visible_items()
        if not visible:
            return
        action = visible[self.menu_index]
        if action.is_parent:
            action.enter()
            return
        if action.is_mode:
            self._active_action = action
            action.enter()
        else:
            action.enter()

    # ── Mode Transitions ──────────────────────────────────────────────────

    def _enter_edit(self) -> None:
        """EDIT mode transition."""
        if self.query("#p_edit_zone"):
            return
        self.query_one("#p_flex", VerticalScroll).display = False
        editor = MarkdownEditor(initial_text=self._full_text, id="p_edit_zone")
        self.mount(editor, after="#p_menu")

    def _leave_edit(self) -> None:
        """Return to READ mode from EDIT."""
        self._active_action = None
        try:
            for widget in self.query("#p_edit_zone"):
                widget.remove()
        except: pass
        self.query_one("#p_flex", VerticalScroll).display = True
        self.focus()
        self._refresh_all()

    def _enter_enhance_prompt(self) -> None:
        """AI mode transition."""
        if self.query("#p_enhance_zone"):
            return
        self.query_one("#p_flex", VerticalScroll).display = False
        ai = AIEditor(original_text=self._full_text, id="p_enhance_zone")
        self.mount(ai, after="#p_menu")

    def _leave_enhance_prompt(self) -> None:
        """Return to READ mode from AI."""
        self._active_action = None
        try:
            for widget in self.query("#p_enhance_zone"):
                widget.remove()
        except: pass
        self.query_one("#p_flex", VerticalScroll).display = True
        self.focus()
        self._refresh_all()

    # ── Components Callbacks ─────────────────────────────────────────────

    def on_markdown_editor_save_request(self, message: MarkdownEditor.SaveRequest) -> None:
        message.stop()
        self._save_edit()

    def _save_edit(self) -> None:
        try:
            self._full_text = self.query_one("#p_edit_zone", MarkdownEditor).text
        except Exception:
            pass
        self._leave_edit()

    def on_ai_editor_submit_prompt(self, message: AIEditor.SubmitPrompt) -> None:
        message.editor.start_loading()
        self._run_ai_worker(self._full_text, message.prompt or None)

    def on_ai_editor_accept(self, message: AIEditor.Accept) -> None:
        self._full_text = message.result
        self._leave_enhance_prompt()

    @work(thread=True, exclusive=True)
    def _run_ai_worker(self, text: str, prompt: str | None) -> None:
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
        try:
            self.query_one("#p_enhance_zone", AIEditor).update_agent(agent_label)
        except Exception:
            pass

    def _on_enhance_done(self, enhanced_text: str) -> None:
        try:
            self.query_one("#p_enhance_zone", AIEditor).set_result(enhanced_text)
        except Exception:
            pass
        self._refresh_footer()

    def _on_enhance_error(self, error_msg: str) -> None:
        try:
            self.query_one("#p_enhance_zone", AIEditor).set_error(error_msg)
        except Exception:
            pass

    # ── Refresh Helpers ──────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._refresh_status()
        self._refresh_transcript()
        self._update_all_menu_and_footer()

    def _refresh_status(self) -> None:
        words  = len(self._full_text.split()) if self._full_text.strip() else 0
        tokens = int(words * 1.3)
        self.query_one("#p_status", Static).update(
            render_pause_status(self._time_str, words, tokens)
        )

    def _refresh_transcript(self) -> None:
        try:
            scroll = self.query_one("#p_flex", VerticalScroll)
            scroll.border_title = "[bold dim]Transcript[/bold dim]"
            self.query_one("#p_flex_content", Static).update(
                render_pause_transcript_body(self._full_text)
            )
        except Exception:
            pass

    def _update_all_menu_and_footer(self) -> None:
        self._update_menu()
        self._refresh_footer()

    def _update_menu(self) -> None:
        visible = self._visible_items()
        view_items = [(a.label, a.action_id, a.parent_id) for a in visible]
        self.query_one("#p_menu", Static).update(
            render_pause_menu(view_items, self.menu_index, self._mode == "read", self._expanded)
        )

    def _refresh_footer(self) -> None:
        self.query_one("#p_footer", Static).update(render_pause_footer(self._mode))

    def _dismiss(self, action: str) -> None:
        edited = self._full_text if self._full_text != self._original_text else None
        self.dismiss((action, edited))
