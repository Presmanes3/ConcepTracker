"""NoteAction — strategy contract for menu items in OpenNoteScreen.

Each item visible in the note screen's side menu is a NoteAction instance.
The screen is completely agnostic about what any action does; it only calls
``enter()`` on selection and ``leave()`` on Escape.

Adding a new mode (e.g. "Summarise", "Export") requires only:
1. Defining a lifecycle method pair on OpenNoteScreen (``_enter_X / _leave_X``).
2. Creating a NoteAction and passing it to ``screen.set_actions()``.
Nothing else in the screen needs to change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from rich.console import RenderableType


@dataclass
class NoteAction:
    """Self-contained descriptor for one item in the note screen's action menu.

    Attributes:
        label: Text displayed in the side menu.
        hint_color: Rich border-style colour for the preview hint panel.
        hint_text: Rich markup shown in the content panel when this item is
            highlighted (but before Enter is pressed).
        mode_key: Non-empty string identifies this as a *persistent mode*
            (e.g. ``"edit"``, ``"ai"``).  The screen records which action is
            active and routes ``Escape`` to ``leave()``.  Empty string means
            a one-shot action whose result is processed immediately.
        content_widget_id: Textual CSS ID of the widget that should receive
            focus when ``ZONE_CONTENT`` is entered.  ``None`` for modes without
            an interactive widget (read-only panels, one-shots).
        enter: Called when the user activates this item.  For one-shot actions
            it may return a ``ScreenSignal``; for modes it returns ``None``.
        leave: Called when the user presses Escape while this mode is active.
        footer_view: Returns the Rich renderable for the footer bar while this
            mode is active.  ``None`` falls back to the default footer.
        disabled: When ``True`` the item is shown dim and is not selectable.
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
