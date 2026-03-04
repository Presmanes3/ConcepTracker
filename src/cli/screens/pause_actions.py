"""PauseAction — strategy contract for menu items in PauseTranscriptionScreen.

Similar to NoteAction in OpenNoteScreen, this decouples the pause screen's
UI from the specific logic of each action (Edit, AI, Save, etc).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from rich.console import RenderableType


@dataclass
class PauseAction:
    """Descriptor for one item in the pause screen's action menu.

    Attributes:
        label: Text displayed in the side menu.
        action_id: Unique identifier for the action.
        hint_color: Rich color for the active cursor/mode highlight.
        mode_key: Interaction mode ("read", "edit", "enhance_prompt").
        content_widget_id: Textual ID of the widget to focus in this mode.
        enter: Called when selected. Returns a dismissal signal or None.
        leave: Called on Escape/back navigation.
        footer_view: Custom footer renderable for this mode.
        parent_id: If set, this is a child of another action.
        is_parent: True if this action has children.
    """

    label: str
    action_id: str
    hint_color: str = "green"
    mode_key: str = "read"
    content_widget_id: str | None = None
    enter: Callable[[], Any] = field(default_factory=lambda: (lambda: None))
    leave: Callable[[], None] = field(default_factory=lambda: (lambda: None))
    footer_view: Optional[Callable[[], "RenderableType"]] = None
    parent_id: Optional[str] = None
    is_parent: bool = False
    disabled: bool = False

    @property
    def is_mode(self) -> bool:
        """Return True if this action establishes a persistent mode."""
        return self.mode_key != "read"
