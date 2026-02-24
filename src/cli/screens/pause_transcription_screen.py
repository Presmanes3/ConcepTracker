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

Key-handling strategy (critical):
  MarkdownEditor (which contains a TextArea) is mounted/unmounted dynamically.
  In READ mode no focusable child exists → key events always reach on_key.

Modes:
  READ  — Right panel: scrollable Markdown transcript.
  EDIT  — Right panel: MarkdownEditor component.
          Ctrl+S saves and returns to READ. Esc cancels.
"""
from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static, TextArea

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
        Binding("ctrl+c",     "discard_app",     "Discard",  priority=True, show=False),
        Binding("ctrl+r",     "submit_enhance",  "Run AI",   priority=True, show=False),
        Binding("ctrl+a",     "accept_enhance",  "Accept",   priority=True, show=False),
        Binding("escape",     "escape_mode",     "Cancel",   priority=True, show=False),
    ]

    def action_discard_app(self) -> None:
        """Ctrl+C -> discard the session entirely from the pause screen."""
        self.dismiss(("discard", None))

    def action_submit_enhance(self) -> None:
        if self._mode == "enhance_prompt":
            self._submit_enhance_prompt()

    def action_accept_enhance(self) -> None:
        if self._mode == "enhance_prompt" and self._enhanced_text:
            self._accept_enhanced()

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

    /* Left: action menu — Rich Panel draws its own border */
    #p_menu { width: 32; height: 1fr; }

    /* Right: transcript scroll container (READ mode).
       grey37 (#5f5f5f) matches the visual weight of Rich's dim border. */
    #p_flex {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    #p_flex_content { height: auto; }

    /* Right: MarkdownEditor (EDIT mode) — fills the same slot */
    MarkdownEditor { width: 1fr; }

    /* Enhance-prompt zone — replaces #p_flex while in enhance_prompt mode */
    #p_enhance_zone { width: 1fr; }
    #p_enhance_compare { height: 1fr; }
    #p_enhance_orig {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    #p_enhance_orig_content  { height: auto; }
    #p_enhance_result {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    #p_enhance_result_content { height: auto; }
    #p_enhance_input {
        height: 6;
        margin-top: 1;
        border: round #808080;
    }

    #p_footer { height: auto; dock: bottom; }
    """

    # ── Reactive state ─────────────────────────────────────────────────────
    menu_index: reactive[int] = reactive(0)

    def watch_menu_index(self, value: int) -> None:
        if self.is_mounted and self._mode == "read":
            self._update_menu()

    # ── Init ───────────────────────────────────────────────────────────────

    def __init__(self, full_text: str, time_str: str) -> None:
        super().__init__()
        self._full_text       = full_text
        self._original_text   = full_text
        self._time_str        = time_str
        self._mode            = "read"
        self._expanded: set[str] = set()
        self._enhanced_text   = ""
        self._current_agent   = ""    # name of the agent currently running
        self._spinner_frame   = 0
        self._spinner_timer   = None
        self.menu_index       = 0

    _SPINNER = "⣾⣽⣻⢿⡿⣟⣯⣷"

    def _visible_items(self) -> list:
        """Return only the menu items that should currently be visible."""
        return [
            item for item in PAUSE_MENU_ITEMS
            if item[2] is None or item[2] in self._expanded
        ]

    # ── Compose ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Static skeleton — no focusable widgets in READ mode.

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

    # ── Key handling ───────────────────────────────────────────────────────

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
            pass  # all keys handled via priority BINDINGS

    # ── Menu dispatch ──────────────────────────────────────────────────────

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

    # ── Mode transitions ───────────────────────────────────────────────────

    def _enter_edit(self) -> None:
        """EDIT mode: hide transcript scroll, mount MarkdownEditor in its place."""
        self._mode = "edit"
        self.query_one("#p_flex", VerticalScroll).display = False
        self.mount(
            MarkdownEditor(initial_text=self._full_text, id="p_edit_zone"),
            after="#p_menu",
        )
        self.call_after_refresh(self._focus_editor)
        self._refresh_status()
        self._update_menu()
        self._refresh_footer()

    def _focus_editor(self) -> None:
        """Delegate focus to the inner TextArea once the editor is fully mounted."""
        try:
            self.query_one("#editor_textarea", TextArea).focus()
        except Exception:
            pass

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

    # ── Enhance-prompt mode ────────────────────────────────────────────────

    def _enter_enhance_prompt(self) -> None:
        """Show side-by-side original/enhanced comparison + prompt TextArea."""
        self._mode = "enhance_prompt"
        self._enhanced_text = ""
        self.query_one("#p_flex", VerticalScroll).display = False

        from textual.containers import Vertical as V
        zone = V(id="p_enhance_zone")
        self.mount(zone, after="#p_menu")

        async def _build_zone() -> None:
            compare = Horizontal(id="p_enhance_compare")
            await zone.mount(compare)

            orig_scroll = VerticalScroll(id="p_enhance_orig")
            res_scroll  = VerticalScroll(id="p_enhance_result")
            await compare.mount(orig_scroll, res_scroll)

            orig_content = Static(id="p_enhance_orig_content")
            res_content  = Static(id="p_enhance_result_content")
            await orig_scroll.mount(orig_content)
            await res_scroll.mount(res_content)

            prompt_input = TextArea(
                id="p_enhance_input",
                soft_wrap=True,
            )
            await zone.mount(prompt_input)

            # Populate original transcript
            orig_scroll.border_title = "[bold dim]Original[/bold dim]"
            res_scroll.border_title  = "[bold dim]Enhanced[/bold dim]"
            orig_content.update(render_pause_transcript_body(self._full_text))
            res_content.update(render_pause_transcript_body(""))

            prompt_input.focus()

        self.call_after_refresh(lambda: self.app.call_later(_build_zone))
        self._update_menu()
        self._refresh_footer()

    def _leave_enhance_prompt(self) -> None:
        """Cancel enhance-prompt mode, restore transcript view."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self._mode = "read"
        self._enhanced_text = ""
        try:
            self.query_one("#p_enhance_zone").remove()
        except Exception:
            pass
        self.query_one("#p_flex", VerticalScroll).display = True
        self.focus()
        self._refresh_all()

    def _submit_enhance_prompt(self) -> None:
        """Read the prompt TextArea and kick off the AI worker."""
        try:
            prompt_text = self.query_one("#p_enhance_input", TextArea).text.strip()
        except Exception:
            prompt_text = ""
        self._current_agent = ""
        # Start spinner timer (100 ms)
        self._spinner_frame = 0
        self._spinner_timer = self.set_interval(0.1, self._tick_spinner)
        # Clear result panel
        try:
            self.query_one("#p_enhance_result", VerticalScroll).border_title = ""
            self.query_one("#p_enhance_result_content", Static).update("")
        except Exception:
            pass
        self._run_ai_worker(self._full_text, prompt_text or None)

    def _tick_spinner(self) -> None:
        """100 ms callback — update the border_title with spinner + agent name."""
        char = self._SPINNER[self._spinner_frame % len(self._SPINNER)]
        self._spinner_frame += 1
        agent_label = f"  {self._current_agent}" if self._current_agent else ""
        try:
            self.query_one("#p_enhance_result", VerticalScroll).border_title = (
                f"[bold yellow]{char}{agent_label}[/bold yellow]"
            )
        except Exception:
            pass

    @work(thread=True, exclusive=True)
    def _run_ai_worker(self, text: str, prompt: str | None) -> None:
        """AI enhancement in a background thread — does not block the TUI.

        Uses workflow.stream() so each completed agent node triggers a
        call_from_thread that updates the spinner title with the agent name.
        """
        try:
            from src.workflows.transcription_workflow import transcription_workflow
            from shared.schemas.workflow.transcription import TranscriptionEnhancementState

            # Human-readable label map for agent node names
            _LABELS = {
                "speech_cleaner":     "Speech cleaner",
                "markdown_formatter": "Markdown formatter",
                "no_op":              "",
            }

            context_text = (
                f"[USER INSTRUCTION: {prompt}]\n\n{text}" if prompt else text
            )
            initial = TranscriptionEnhancementState(
                raw_text=text,
                current_text=context_text,
                applied_layers=[],
                action_items=None,
                error=None,
                user_prompt=prompt,
            )

            last_state = initial
            for chunk in transcription_workflow.stream(initial):
                # chunk = {node_name: state_dict}
                for node_name, state in chunk.items():
                    label = _LABELS.get(node_name, node_name.replace("_", " ").title())
                    self.app.call_from_thread(self._on_agent_step, label)
                    last_state = state

            enhanced = last_state.get("current_text", text) if isinstance(last_state, dict) else text
            error    = last_state.get("error") if isinstance(last_state, dict) else None
            if error:
                self.app.call_from_thread(self._on_enhance_error, error)
            else:
                self.app.call_from_thread(self._on_enhance_done, enhanced)
        except Exception as exc:
            self.app.call_from_thread(self._on_enhance_error, str(exc))

    def _on_agent_step(self, agent_label: str) -> None:
        """Update the running agent name shown in the spinner title."""
        self._current_agent = agent_label

    def _on_enhance_done(self, enhanced_text: str) -> None:
        """Called on the main thread when the AI worker finishes."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self._enhanced_text = enhanced_text
        try:
            res_scroll = self.query_one("#p_enhance_result", VerticalScroll)
            res_scroll.border_title = (
                "[bold green]✨ Enhanced — Ctrl+A to accept[/bold green]"
            )
            self.query_one("#p_enhance_result_content", Static).update(
                render_pause_transcript_body(enhanced_text)
            )
        except Exception:
            pass
        self._refresh_footer()

    def _on_enhance_error(self, message: str) -> None:
        """Called on the main thread when the AI worker fails."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        try:
            res_scroll = self.query_one("#p_enhance_result", VerticalScroll)
            res_scroll.border_title = "[bold red]Error[/bold red]"
            self.query_one("#p_enhance_result_content", Static).update(
                f"[red]{message}[/red]"
            )
        except Exception:
            pass

    def _accept_enhanced(self) -> None:
        """User accepts the AI result — replace transcript and return to READ mode."""
        self._full_text = self._enhanced_text
        self._leave_enhance_prompt()

    # ── Refresh helpers ────────────────────────────────────────────────────

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
