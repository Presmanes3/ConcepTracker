"""TranscriptionAction — strategy contract for menu items in RecordingScreen.

Each item visible in the recording screen's side menu is a TranscriptionAction 
instance. The screen is agnostic about what any action does; it calls ``enter()`` 
on selection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from rich.console import RenderableType


@dataclass
class TranscriptionAction:
    """Descriptor for one item in the recording screen's action menu.

    Attributes:
        label: Text displayed in the side menu.
        hint_color: Rich border-style color for the preview hint panel.
        hint_text: Rich markup shown in the content panel when highlighted.
        mode_key: Identifies a persistent mode (empty for one-shot).
        content_widget_id: Textual CSS ID of the widget receiving focus.
        enter: Called when the user activates this item.
        leave: Called when the user presses Escape while mode is active.
        footer_view: Returns the Rich renderable for the footer bar.
        hover_footer: Returns the Rich renderable when item is hovered.
        disabled: True if item is shown dim and not selectable.
    """

    label: str
    hint_color: str = "dim"
    hint_text: str = "Press Enter to execute."
    mode_key: str = ""
    content_widget_id: str | None = None
    enter: Callable[[], Any] = field(default_factory=lambda: (lambda: None))
    leave: Callable[[], None] = field(default_factory=lambda: (lambda: None))
    confirm: Optional[Callable[[], Any]] = None
    footer_view: Optional[Callable[[], "RenderableType"]] = None
    hover_footer: Optional[Callable[[], "RenderableType"]] = None
    disabled: bool = False

    @property
    def is_mode(self) -> bool:
        """Return True if this action establishes a persistent mode."""
        return bool(self.mode_key)
