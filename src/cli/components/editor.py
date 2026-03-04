from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static, TextArea
from textual.message import Message
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

class MarkdownEditor(Horizontal):
    """
    A generic horizontal split editor component.
    Left: TextArea for editing.
    Right: Static for Markdown preview.
    
    The preview updates 10 times per second (every 100ms) as requested.
    """
    
    BINDINGS = [
        ("ctrl+s", "save", "Save"),
    ]

    def action_save(self) -> None:
        """Post a SaveRequest message to the screen."""
        self.post_message(self.SaveRequest())

    class SaveRequest(Message):
        """Message sent to parent to request saving the current text."""
        pass

    DEFAULT_CSS = """
    MarkdownEditor {
        width: 1fr;
        height: 1fr;
    }
    #editor_textarea {
        width: 1fr;
        height: 100%;
        border: round #666666;
        background: transparent;
        padding: 0 1;
    }
    #editor_textarea:focus {
        border: round white 60%;
    }
    #editor_preview {
        width: 1fr;
        height: 100%;
    }
    """

    def __init__(
        self, 
        initial_text: str = "", 
        title: str = "Edit", 
        subtitle: str = "Ctrl+S \u00b7 Esc",
        id: str | None = None,
        auto_focus: bool = True,
    ):
        super().__init__(id=id)
        self._initial_text = initial_text
        self._title = title
        self._subtitle = subtitle
        self._preview_timer = None
        self._auto_focus = auto_focus

    def compose(self) -> ComposeResult:
        editor = TextArea(id="editor_textarea")
        editor.border_title = self._title
        editor.border_subtitle = self._subtitle
        yield editor
        yield Static(id="editor_preview")

    def on_mount(self) -> None:
        textarea = self.query_one("#editor_textarea", TextArea)
        if self._initial_text:
            textarea.load_text(self._initial_text)
        if self._auto_focus:
            textarea.focus()
        self._preview_timer = self.set_interval(0.1, self._update_preview)
        self._update_preview()

    def load_text(self, text: str) -> None:
        """Replace the editor's content. Safe to call after mount."""
        self._initial_text = text
        try:
            self.query_one("#editor_textarea", TextArea).load_text(text)
        except Exception:
            pass

    def _update_preview(self) -> None:
        """Fetch text from TextArea and render as Markdown in the Static panel."""
        try:
            text = self.query_one("#editor_textarea", TextArea).text
            if text.strip():
                body = Markdown(text)
            else:
                body = Text("No content.", style="dim italic")
            
            self.query_one("#editor_preview", Static).update(
                Panel(body, border_style="dim", title="[bold]Preview[/bold]")
            )
        except Exception:
            # Prevents crashes if widgets are unmounted during a timer tick
            pass

    @property
    def text(self) -> str:
        """Returns the current text in the editor."""
        return self.query_one("#editor_textarea", TextArea).text

    def focus(self) -> None:
        """Delegate focus to the internal TextArea (safe to call at any time)."""
        try:
            self.query_one("#editor_textarea", TextArea).focus()
        except Exception:
            # Not yet composed — on_mount will focus the textarea once ready
            pass
