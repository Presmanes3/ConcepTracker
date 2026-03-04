"""
AIEditor — generic two-pane compare + prompt component for AI enhancement.

Layout (Vertical):
  ┌──────────────────────────────────────────────┐
  │  #ai_compare  (Horizontal, 1fr)              │
  │  ┌─────────────────┐  ┌────────────────────┐ │
  │  │  #ai_orig       │  │  #ai_result        │ │
  │  │  (VerticalScroll│  │  (VerticalScroll)  │ │
  │  └─────────────────┘  └────────────────────┘ │
  ├──────────────────────────────────────────────┤
  │  #ai_prompt  (TextArea, 5 rows)              │
  └──────────────────────────────────────────────┘

Messages (bubble to parent screen):
  AIEditor.SubmitPrompt(editor, prompt)  — Ctrl+R pressed
  AIEditor.Accept(editor, result)        — Ctrl+A pressed (only when result exists)

Public API:
  set_original(text)         populate left pane
  start_loading()            start spinner + clear result pane
  update_agent(label)        update spinner label (safe via call_from_thread)
  set_result(text)           populate right pane, stop spinner
  set_error(message)         show error in right pane, stop spinner
  .result_text  -> str       current AI result
  .prompt_text  -> str       current prompt content
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static, TextArea

from rich.markdown import Markdown
from rich.text import Text


class AIEditor(Vertical):
    """Generic two-pane (original | AI result) editor with a prompt input.

    Key bindings (ctrl+r, ctrl+a) must be declared on the *host screen* with
    priority=True so they fire before TextArea consumes them. The screen then
    calls start_loading() / result_text / _has_result directly.
    """

    DEFAULT_CSS = """
    AIEditor {
        width: 1fr;
        height: 1fr;
    }
    AIEditor > #ai_compare {
        height: 1fr;
    }
    AIEditor #ai_orig {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    AIEditor #ai_orig_content  { height: auto; }
    AIEditor #ai_result {
        width: 1fr;
        border: round #808080;
        padding: 0 1;
    }
    AIEditor #ai_result_content { height: auto; }
    AIEditor #ai_prompt {
        height: 5;
        margin-top: 1;
        border: round #808080;
    }
    """

    _SPINNER = "⣾⣽⣻⢿⡿⣟⣯⣷"

    # ── Messages ─────────────────────────────────────────────────────────────

    class SubmitPrompt(Message):
        """User pressed Ctrl+R to run the AI pipeline."""

        def __init__(self, editor: "AIEditor", prompt: str) -> None:
            super().__init__()
            self.editor = editor
            self.prompt = prompt

    class Accept(Message):
        """User pressed Ctrl+A to accept the current AI result."""

        def __init__(self, editor: "AIEditor", result: str) -> None:
            super().__init__()
            self.editor = editor
            self.result = result

    # ── Init ─────────────────────────────────────────────────────────────────

    def __init__(self, original_text: str = "", id: str | None = None, auto_focus: bool = True) -> None:
        super().__init__(id=id)
        self._original_text = original_text
        self._result_text   = ""
        self._has_result    = False
        self._spinner_frame = 0
        self._spinner_timer = None
        self._current_agent = ""
        self._auto_focus    = auto_focus

    # ── Compose / lifecycle ──────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="ai_compare"):
            with VerticalScroll(id="ai_orig"):
                yield Static(id="ai_orig_content")
            with VerticalScroll(id="ai_result"):
                yield Static(id="ai_result_content")
        prompt = TextArea(id="ai_prompt", soft_wrap=True)
        prompt.border_title = "[dim]Prompt[/dim]"
        yield prompt

    def on_mount(self) -> None:
        self.query_one("#ai_orig",   VerticalScroll).border_title = "[bold dim]Original[/bold dim]"
        self.query_one("#ai_result", VerticalScroll).border_title = "[bold dim]Result[/bold dim]"
        if self._original_text:
            self.set_original(self._original_text)
        if self._auto_focus:
            self.query_one("#ai_prompt", TextArea).focus()

    def on_unmount(self) -> None:
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None

    # ── Binding actions (called by host screen, not self) ────────────────────
    # These are intentionally NOT declared as Textual BINDINGS here.
    # The host screen declares priority=True bindings and calls these directly.

    # ── Public API ───────────────────────────────────────────────────────────

    def set_original(self, text: str) -> None:
        """Populate the left (original) pane."""
        body = Markdown(text) if text.strip() else Text("(empty)", style="dim italic")
        self.query_one("#ai_orig_content", Static).update(body)

    def start_loading(self) -> None:
        """Start the spinner on the result pane and clear its content."""
        self._has_result    = False
        self._result_text   = ""
        self._current_agent = ""
        self._spinner_frame = 0
        if self._spinner_timer:
            self._spinner_timer.stop()
        self._spinner_timer = self.set_interval(0.1, self._tick_spinner)
        try:
            self.query_one("#ai_result_content", Static).update("")
        except Exception:
            pass

    def update_agent(self, label: str) -> None:
        """Update the agent label shown in the spinner.

        Safe to call from a background thread via app.call_from_thread().
        """
        self._current_agent = label

    def _tick_spinner(self) -> None:
        char  = self._SPINNER[self._spinner_frame % len(self._SPINNER)]
        self._spinner_frame += 1
        label = f"  {self._current_agent}" if self._current_agent else ""
        try:
            self.query_one("#ai_result", VerticalScroll).border_title = (
                f"[bold yellow]{char}{label}[/bold yellow]"
            )
        except Exception:
            pass

    def set_result(self, text: str) -> None:
        """Populate the right pane with the AI result and stop the spinner."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self._result_text = text
        self._has_result  = bool(text.strip())
        body  = Markdown(text) if text.strip() else Text("(empty)", style="dim italic")
        title = (
            "[bold green]✨ Result — Ctrl+A to accept[/bold green]"
            if self._has_result
            else "[bold dim]Result[/bold dim]"
        )
        self.query_one("#ai_result_content", Static).update(body)
        self.query_one("#ai_result", VerticalScroll).border_title = title

    def set_error(self, message: str) -> None:
        """Show an error in the result pane and stop the spinner."""
        if self._spinner_timer:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self._has_result = False
        self.query_one("#ai_result_content", Static).update(f"[red]{message}[/red]")
        self.query_one("#ai_result", VerticalScroll).border_title = "[bold red]Error[/bold red]"

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def result_text(self) -> str:
        return self._result_text

    @property
    def prompt_text(self) -> str:
        try:
            return self.query_one("#ai_prompt", TextArea).text
        except Exception:
            return ""
