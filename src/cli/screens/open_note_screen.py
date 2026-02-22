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

from src.cli._input import _is_up, _is_down, _is_select, _is_quit
from src.cli.screen import AppScreen, SCREEN_EXIT, ScreenSignal
from src.cli.views.link_views import link_table_view

console = Console()

# Which zone the cursor is on
_ZONE_TOP = "top"
_ZONE_MIDDLE = "middle"
_ZONE_MENU = "menu"


class OpenNoteScreen(AppScreen):
    """
    Interactive screen for viewing a note.
    Opens in an alternate terminal buffer so ls/find output is preserved on exit.
    """

    alternate_screen = True  # full-page: restores previous terminal content on Back/quit

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
        super().__init__()
        self._note = note
        self._arch_badge = arch_badge
        self._out_links = out_links
        self._in_links = in_links
        self._note_summaries = note_summaries
        self.actions_renderable = actions_renderable
        self.menu_items = menu_items

        # Expand state for collapsible zones
        self.top_expanded = False
        self.middle_expanded = False

        # Cursor: which zone is focused
        # Order: _ZONE_TOP → _ZONE_MIDDLE → _ZONE_MENU (index 0..N)
        self._focus_zone: str = _ZONE_TOP
        self._menu_index: int = 0

        self.right_pane_renderable: Optional[RenderableType] = None
        self._layout = self._build_renderable()

    # ------------------------------------------------------------------ #
    #  Layout construction                                                 #
    # ------------------------------------------------------------------ #

    def _build_renderable(self) -> Group:
        """Assemble all zones as a Group so height is driven by content."""
        return Group(
            self._render_top(),
            self._render_middle(),
            self._render_bottom(),
            self.actions_renderable,
        )

    def build_layout(self) -> Group:
        self._layout = self._build_renderable()
        return self._layout

    def refresh_zones(self) -> None:
        # Group is immutable — rebuild and let live.update() pick it up
        self._layout = self._build_renderable()

    # ------------------------------------------------------------------ #
    #  Zone renderers                                                      #
    # ------------------------------------------------------------------ #

    def _render_top(self) -> RenderableType:
        note = self._note
        is_focused = self._focus_zone == _ZONE_TOP
        border = "bold bright_yellow blink" if is_focused else "green"
        icon = "▼" if self.top_expanded else "▶"
        title_color = "bright_yellow" if is_focused else "green"
        title = f"[bold {title_color}]{icon} Note #{note.id}[/bold {title_color}]"

        date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
        tags_str = f"[magenta]{note.tags}[/magenta]" if note.tags else "[dim]No Tags[/dim]"

        if not self.top_expanded:
            # Meta row + multi-line markdown preview
            raw = (note.content or "").strip()
            preview_text = (raw[:400] + "\n\n…") if len(raw) > 400 else raw
            tbl = Table.grid(padding=(0, 4))
            tbl.add_row(
                f"[bold cyan]ID:[/bold cyan] {note.id}",
                f"[bold cyan]Arch:[/bold cyan] {self._arch_badge}",
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
        meta.add_row(f"[bold cyan]Archipelago:[/bold cyan] {self._arch_badge}", f"[bold cyan]Tags:[/bold cyan] {tags_str}")
        return Panel(
            Group(meta, "", Markdown(note.content)),
            title=title,
            border_style=border,
            expand=True,
        )

    def _render_middle(self) -> RenderableType:
        is_focused = self._focus_zone == _ZONE_MIDDLE
        border = "bold bright_yellow blink" if is_focused else "blue"
        icon = "▼" if self.middle_expanded else "▶"
        title_color = "bright_yellow" if is_focused else "blue"
        title = f"[bold {title_color}]{icon} Connections[/bold {title_color}]"

        total = len(self._out_links) + len(self._in_links)
        if not self.middle_expanded:
            summary = f"[dim]{len(self._out_links)} outgoing, {len(self._in_links)} incoming[/dim]"
            return Panel(Text.from_markup(summary), title=title, border_style=border, expand=True)

        # Expanded: full link table (no row limit)
        return link_table_view(
            self._out_links,
            self._in_links,
            self._note_summaries,
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
        is_zone_focused = self._focus_zone == _ZONE_MENU
        items: list[Text] = []
        for i, (label, _) in enumerate(self.menu_items):
            if is_zone_focused and i == self._menu_index:
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
        content = self.right_pane_renderable or Text(
            "Select a menu option to view content here.",
            style="dim italic",
        )
        return Panel(content, title="Content", border_style="dim")

    # ------------------------------------------------------------------ #
    #  Focus helpers                                                       #
    # ------------------------------------------------------------------ #

    _FOCUS_ORDER = [_ZONE_TOP, _ZONE_MIDDLE, _ZONE_MENU]

    def _focus_next(self) -> None:
        idx = self._FOCUS_ORDER.index(self._focus_zone)
        self._focus_zone = self._FOCUS_ORDER[(idx + 1) % len(self._FOCUS_ORDER)]

    def _focus_prev(self) -> None:
        idx = self._FOCUS_ORDER.index(self._focus_zone)
        self._focus_zone = self._FOCUS_ORDER[(idx - 1) % len(self._FOCUS_ORDER)]

    # ------------------------------------------------------------------ #
    #  Key handling                                                        #
    # ------------------------------------------------------------------ #

    def handle_key(self, kind: Optional[str], key: Optional[bytes]) -> ScreenSignal:
        if _is_quit(kind, key):
            return SCREEN_EXIT

        if _is_up(kind, key):
            if self._focus_zone == _ZONE_MENU:
                if self._menu_index > 0:
                    self._menu_index -= 1
                else:
                    self._focus_zone = _ZONE_MIDDLE
            else:
                self._focus_prev()
            return True  # trigger refresh

        if _is_down(kind, key):
            if self._focus_zone == _ZONE_MENU:
                if self._menu_index < len(self.menu_items) - 1:
                    self._menu_index += 1
                else:
                    self._focus_zone = _ZONE_TOP
            else:
                self._focus_next()
            return True  # trigger refresh

        # SPACE — expand/collapse focused zone, or select menu item
        if kind == "char" and key in (b" ",):
            return self._handle_space()

        # ENTER — select focused menu item
        if _is_select(kind, key):
            if self._focus_zone == _ZONE_MENU and self.menu_items:
                _, callback = self.menu_items[self._menu_index]
                return callback()
            return None

        return None

    def _handle_space(self) -> ScreenSignal:
        if self._focus_zone == _ZONE_TOP:
            self.top_expanded = not self.top_expanded
            return True  # refresh_zones() will rebuild the Group
        elif self._focus_zone == _ZONE_MIDDLE:
            self.middle_expanded = not self.middle_expanded
            return True  # refresh_zones() will rebuild the Group
        elif self._focus_zone == _ZONE_MENU and self.menu_items:
            _, callback = self.menu_items[self._menu_index]
            return callback()
        return None
