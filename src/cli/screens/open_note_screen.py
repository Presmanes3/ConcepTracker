"""
Open Note Screen — TUI screen for viewing a note and its connections.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple

from typing import Dict, List

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.screen import AppScreen, SCREEN_EXIT, ScreenSignal
# No longer using _input.py for key detection, using Textual's key names.
from src.cli.views.link_views import link_table_view

console = Console()

# Which zone the cursor is on
_ZONE_TOP = "top"
_ZONE_MIDDLE = "middle"
_ZONE_MENU = "menu"


from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widgets import Static

class OpenNoteScreen(AppScreen):
    """
    Interactive screen for viewing a note.
    """
    alternate_screen = True
    
    # Reactive state
    top_expanded: reactive[bool] = reactive(False)
    middle_expanded: reactive[bool] = reactive(False)
    focus_zone: reactive[str] = reactive(_ZONE_TOP)
    menu_index: reactive[int] = reactive(0)

    def __init__(
        self,
        note,
        arch_badge: str,
        out_links: list,
        in_links: list,
        note_summaries: dict,
        actions_renderable: RenderableType,
        menu_items: List[Tuple[str, Callable[[], Any]]],
    ):
        # 1. Non-reactive data members
        self._note = note
        self._arch_badge = arch_badge
        self._out_links = out_links
        self._in_links = in_links
        self._note_summaries = note_summaries
        self.actions_renderable = actions_renderable
        self.menu_items = menu_items
        self.right_pane_renderable: Optional[RenderableType] = None
        
        # 2. Call super
        super().__init__()

        # 3. Initialise reactive attributes (only if different from class defaults)
        # top_expanded and others already have correct defaults in their reactive() call.
        # But we set them explicitly here after super to ensure they are synchronized.
        self.top_expanded = False
        self.middle_expanded = False
        self.focus_zone = _ZONE_TOP
        self.menu_index = 0

    def compose(self) -> ComposeResult:
        # Standard Rich bridge container
        yield Static(id="main_content")

    def watch_top_expanded(self, _) -> None:
        self.refresh_zones()

    def watch_middle_expanded(self, _) -> None:
        self.refresh_zones()

    def watch_focus_zone(self, _) -> None:
        self.refresh_zones()

    def watch_menu_index(self, _) -> None:
        self.refresh_zones()

    def on_mount(self) -> None:
        super().on_mount()

    # ------------------------------------------------------------------ #
    #  Layout construction                                                 #
    # ------------------------------------------------------------------ #

    def _build_renderable(self) -> Group:
        """Assemble all zones as a Group so height is driven by content."""
        parts: List[RenderableType] = []
        try:
            parts.append(self._render_top())
            parts.append(self._render_middle())
            parts.append(self._render_bottom())
            parts.append(getattr(self, "actions_renderable", ""))
        except Exception as e:
            parts.append(Panel(f"[red]Rendering error: {e}[/red]"))
        
        return Group(*parts)

    def build_layout(self) -> Group:
        return self._build_renderable()

    def refresh_zones(self) -> None:
        # Updating self.content triggers AppScreen.watch_content
        self.content = self._build_renderable()

    # ------------------------------------------------------------------ #
    #  Zone renderers                                                      #
    # ------------------------------------------------------------------ #

    def _render_top(self) -> RenderableType:
        note = getattr(self, "_note", None)
        if not note:
            return Panel("[red]Error: Note not found[/red]")
        
        is_focused = self.focus_zone == _ZONE_TOP
        border = "bold bright_yellow blink" if is_focused else "green"
        icon = "▼" if self.top_expanded else "▶"
        title_color = "bright_yellow" if is_focused else "green"
        title = f"[bold {title_color}]{icon} Note #{note.id}[/bold {title_color}]"

        try:
            date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = "(unknown date)"
            
        tags_str = f"[magenta]{note.tags}[/magenta]" if getattr(note, "tags", None) else "[dim]No Tags[/dim]"
        raw = getattr(note, "content", "") or ""

        if not self.top_expanded:
            # Meta row + multi-line markdown preview
            preview_text = (raw[:400].strip() + "\n\n…") if len(raw) > 400 else raw.strip() or "[italic dim]No content[/italic dim]"
            tbl = Table.grid(padding=(0, 4))
            tbl.add_row(
                f"[bold cyan]ID:[/bold cyan] {note.id}",
                f"[bold cyan]Arch:[/bold cyan] {getattr(self, '_arch_badge', '~')}",
                f"[bold cyan]Date:[/bold cyan] {date_str}",
                f"[bold cyan]Tags:[/bold cyan] {tags_str}",
            )
            return Panel(
                Group(tbl, "", Markdown(preview_text)),
                title=title,
                border_style=border,
                expand=True,
            )

        # Expanded: full meta + full markdown content
        meta = Table.grid(padding=(0, 4))
        meta.add_row(f"[bold cyan]ID:[/bold cyan] {note.id}", f"[bold cyan]Date:[/bold cyan] {date_str}")
        meta.add_row(f"[bold cyan]Archipelago:[/bold cyan] {getattr(self, '_arch_badge', '~')}", f"[bold cyan]Tags:[/bold cyan] {tags_str}")
        return Panel(
            Group(meta, "", Markdown(raw)),
            title=title,
            border_style=border,
            expand=True,
        )

    def _render_middle(self) -> RenderableType:
        is_focused = self.focus_zone == _ZONE_MIDDLE
        border = "bold bright_yellow blink" if is_focused else "blue"
        icon = "▼" if self.middle_expanded else "▶"
        title_color = "bright_yellow" if is_focused else "blue"
        title = f"[bold {title_color}]{icon} Connections[/bold {title_color}]"

        out_links = getattr(self, "_out_links", [])
        in_links = getattr(self, "_in_links", [])
        
        if not self.middle_expanded:
            summary = f"[dim]{len(out_links)} outgoing, {len(in_links)} incoming[/dim]"
            return Panel(Text.from_markup(summary), title=title, border_style=border, expand=True)

        # Expanded: full link table (no row limit)
        return link_table_view(
            out_links,
            in_links,
            getattr(self, "_note_summaries", {}),
            title=title,
            border_style=border,
        )

    def _render_bottom(self) -> RenderableType:
        """Render menu + content side by side, auto-sized columns."""
        menu_panel    = self._render_menu()
        content_panel = self._render_content()

        # auto-width grid: menu column is unsized (shrink-wraps),
        # content column takes everything else
        grid = Table.grid(expand=True)
        grid.add_column("menu")                         # auto / shrink-wrap
        grid.add_column("content", ratio=1)             # fills remaining space
        grid.add_row(menu_panel, content_panel)
        return grid

    def _render_menu(self) -> RenderableType:
        is_zone_focused = self.focus_zone == _ZONE_MENU
        items: list[Text] = []
        menu_items = getattr(self, "menu_items", [])
        for i, (label, _) in enumerate(menu_items):
            if is_zone_focused and i == self.menu_index:
                row = Text(f"▶ {label}", style="bold black on bright_yellow")
            else:
                row = Text(f"  {label}", style="white")
            items.append(row)

        if not items:
            items.append(Text("  (empty)", style="dim"))

        border = "bold bright_yellow blink" if is_zone_focused else "dim"
        menu_title = "[bold bright_yellow]Menu[/bold bright_yellow]" if is_zone_focused else "[bold]Menu[/bold]"
        return Panel(
            Group(*items),
            title=menu_title,
            border_style=border,
        )

    def _render_content(self) -> RenderableType:
        content = getattr(self, "right_pane_renderable", None) or Text(
            "Select a menu option to view content here.",
            style="dim italic",
        )
        return Panel(content, title="Content", border_style="dim")

    # ------------------------------------------------------------------ #
    #  Focus helpers                                                       #
    # ------------------------------------------------------------------ #

    _FOCUS_ORDER = [_ZONE_TOP, _ZONE_MIDDLE, _ZONE_MENU]

    def _focus_next(self) -> None:
        idx = self._FOCUS_ORDER.index(self.focus_zone)
        self.focus_zone = self._FOCUS_ORDER[(idx + 1) % len(self._FOCUS_ORDER)]

    def _focus_prev(self) -> None:
        idx = self._FOCUS_ORDER.index(self.focus_zone)
        self.focus_zone = self._FOCUS_ORDER[(idx - 1) % len(self._FOCUS_ORDER)]

    # ------------------------------------------------------------------ #
    #  Key handling                                                        #
    # ------------------------------------------------------------------ #

    def handle_action(self, key: str) -> ScreenSignal:
        if key == "escape":
            return SCREEN_EXIT

        if key in ("up", "k"):
            if self.focus_zone == _ZONE_MENU:
                if self.menu_index > 0:
                    self.menu_index -= 1
                else:
                    self.focus_zone = _ZONE_MIDDLE
            else:
                self._focus_prev()
            return True  # trigger refresh

        if key in ("down", "j"):
            if self.focus_zone == _ZONE_MENU:
                if self.menu_index < len(self.menu_items) - 1:
                    self.menu_index += 1
                else:
                    self.focus_zone = _ZONE_TOP
            else:
                self._focus_next()
            return True  # trigger refresh

        # SPACE — expand/collapse focused zone, or select menu item
        if key == "space":
            return self._handle_space()

        # ENTER — select focused menu item
        if key == "enter":
            if self.focus_zone == _ZONE_MENU and self.menu_items:
                _, callback = self.menu_items[self.menu_index]
                return callback()
            return None

        return None

    def _handle_space(self) -> ScreenSignal:
        if self.focus_zone == _ZONE_TOP:
            self.top_expanded = not self.top_expanded
            return True  # refresh_zones() will rebuild the Group
        elif self.focus_zone == _ZONE_MIDDLE:
            self.middle_expanded = not self.middle_expanded
            return True  # refresh_zones() will rebuild the Group
        elif self.focus_zone == _ZONE_MENU and self.menu_items:
            _, callback = self.menu_items[self.menu_index]
            return callback()
        return None
