"""
Interactive arrow-key pager for Rich output.

Supports two modes:
  • paginate_table()  – tabular data (ls)
  • paginate_panels() – card/panel data (find)

Controls
--------
  ↑  /  k   →  move cursor up
  ↓  /  j   →  move cursor down
  →  /  n   →  next page
  ←  /  p   →  previous page
  Enter     →  select item
  q  / Esc  →  quit
"""
from __future__ import annotations

from typing import Any, Callable, List, TypeVar, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from src.cli.screen import AppScreen, SCREEN_EXIT, run_screen
# No longer using _input.py for key detection, using Textual's key names.
from src.cli.components.footer import render_footer

console = Console()

T = TypeVar("T")


# ── Navigation footer ─────────────────────────────────────────────────────────

def _footer(page: int, total: int) -> Any:
    actions = [
        ("▲/▼", "select", "yellow"),
        ("◀/▶", "page", "cyan"),
        ("Space", "expand", "magenta"),
        ("Enter", "open", "green"),
        ("Ctrl+C", "quit", "dim"),
    ]
    return render_footer(actions, (page, total), border=True, border_style="dim")


class _PagerLayout:
    """A simple mutable layout that yields its non-empty zones."""
    def __init__(self):
        self.top = ""
        self.middle = ""
        self.bottom = ""

    def __rich_console__(self, console, options):
        if self.top:
            yield self.top
        if self.middle:
            yield self.middle
        if self.bottom:
            yield self.bottom


# ── Table pager ───────────────────────────────────────────────────────────────

class _TablePagerScreen(AppScreen):
    """AppScreen backing paginate_table(). Internal — use paginate_table()."""

    alternate_screen = True

    DEFAULT_CSS = """
    _TablePagerScreen {
        layout: vertical;
        background: transparent;
    }
    #body {
        height: 1fr;
    }
    #top_panel    { height: auto; margin-bottom: 1; }
    #middle_panel { height: 1fr; }
    #bottom_panel { height: auto; dock: bottom; }
    """

    # Reactive state: when these change, the relevant UI parts will update
    global_cursor: reactive[int] = reactive(0)
    expanded_states: reactive[set] = reactive(set)

    BINDINGS = [
        # Navigation
        Binding("up", "move_cursor(-1)", "Up", show=False),
        Binding("down", "move_cursor(1)", "Down", show=False),
        Binding("k", "move_cursor(-1)", "Up", show=False),
        Binding("j", "move_cursor(1)", "Down", show=False),
        Binding("left", "page_left", "Prev Page", show=False),
        Binding("right", "page_right", "Next Page", show=False),
        Binding("p", "page_left", "Prev Page", show=False),
        Binding("n", "page_right", "Next Page", show=False),
        # Actions
        Binding("enter", "select_item", "Open", priority=True),
        Binding("space", "toggle_expand", "Expand", priority=True),
    ]

    async def action_move_cursor(self, delta: int) -> None:
        if self._move_cursor(delta):
            self.refresh_zones()

    async def action_page_left(self) -> None:
        if self._move_cursor(-self._dyn_page_size):
            self.refresh_zones()

    async def action_page_right(self) -> None:
        if self._move_cursor(self._dyn_page_size):
            self.refresh_zones()

    async def action_toggle_expand(self) -> None:
        if not self.build_preview:
            return
        idx = self.global_cursor
        new_states = set(self.expanded_states)
        if idx in new_states:
            new_states.discard(idx)
        else:
            new_states.clear()
            new_states.add(idx)
        self.expanded_states = new_states

    async def action_select_item(self) -> None:
        item = self.all_rows[self.global_cursor]
        if self.on_select:
            screen = self.on_select(item)
            if screen:
                await self.process_signal(screen)
                return
        self.result = item
        await self.process_signal(SCREEN_EXIT)

    def __init__(self, all_rows, build_table_fn, page_size, header, build_preview, on_select=None, on_refresh=None):
        super().__init__()
        self.all_rows      = all_rows
        self.build_table_fn = build_table_fn
        self.user_page_size = page_size
        self.header        = header
        self.build_preview = build_preview
        self.on_select     = on_select  # Callable[[item], AppScreen|None]
        self.on_refresh    = on_refresh # Callable[[], Tuple[List, Dict]]
        self.result        = None
        self._dyn_page_size = page_size  # updated each refresh
        self._layout       = _PagerLayout()  # Initialize BEFORE refresh_zones() is called in on_mount

    def compose(self) -> ComposeResult:
        """Compose layout with individual reactive widgets."""
        with Vertical(id="body"):
            yield Static(id="top_panel")
            yield Static(id="middle_panel")
        yield Static(id="bottom_panel")

    def on_show(self) -> None:
        """Refresh data whenever the screen becomes visible (e.g. after back)."""
        if self.on_refresh:
            try:
                # Run the refresh logic provided by the interactor
                new_rows, new_arch_cache = self.on_refresh()
                if new_rows:
                    self.all_rows = new_rows
                    
                    # Update the build_table_fn to use the new items and cache
                    # This relies on closure variables from NoteListInteractor
                    # but if we want to be safe we would need to pass these too.
                    # Since paginate_table closure rebuilds it, we just refresh.
                    self.refresh_zones()
            except Exception:
                pass

    def watch_global_cursor(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()

    def watch_expanded_states(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()

    def on_mount(self) -> None:
        """Called when the screen is active."""
        super().on_mount()
        # Ensure initial display
        self.refresh_zones()

    def _update_ui_parts(self) -> None:
        """Only update the pieces that change."""
        try:
            self.query_one("#top_panel", Static).update(self._layout.top)
            self.query_one("#middle_panel", Static).update(self._layout.middle)
            self.query_one("#bottom_panel", Static).update(self._layout.bottom)
        except Exception:
            pass

    # ── helpers ────────────────────────────────────────────────────────────

    def _compute(self):
        """Return (page, total_pages, rel_cursor, start, chunk) for current state."""
        dyn = self.user_page_size
        self._dyn_page_size = dyn

        page        = self.global_cursor // dyn
        rel_cursor  = self.global_cursor % dyn
        total_pages = max(1, (len(self.all_rows) + dyn - 1) // dyn)
        start       = page * dyn
        chunk       = self.all_rows[start : start + dyn]
        if rel_cursor >= len(chunk):
            rel_cursor = len(chunk) - 1
        return page, total_pages, rel_cursor, start, chunk

    def _move_cursor(self, delta: int) -> bool:
        new = self.global_cursor + delta
        new = max(0, min(len(self.all_rows) - 1, new))
        if new == self.global_cursor:
            return False
        self.global_cursor = new
        if self.expanded_states:
            self.expanded_states = {self.global_cursor}  # reassign to trigger watcher
        return True

    # ── AppScreen interface ────────────────────────────────────────────────

    def build_layout(self) -> Any:
        return _PagerLayout()

    def refresh_zones(self) -> None:
        page, total_pages, rel_cursor, start, chunk = self._compute()

        # Zone 1: Table
        table_content = self.build_table_fn(chunk, rel_cursor, start, self.expanded_states)
        
        # Extract title from table if it exists
        panel_title = None
        if hasattr(table_content, "title") and table_content.title:
            panel_title = table_content.title
            table_content.title = None

        # Pad the table to always have `self.user_page_size` rows
        if hasattr(table_content, "add_row"):
            rows_to_add = self.user_page_size - len(chunk)
            for _ in range(rows_to_add):
                # Add an empty row with the correct number of columns
                empty_row = [""] * len(table_content.columns)
                table_content.add_row(*empty_row)

        if self.header:
            table_content = Group(self.header, table_content)
            
        # No border style — professional look as requested
        self._layout.top = Panel(table_content, title=panel_title, border_style="dim")

        # Zone 2: Preview
        if self.build_preview and self.global_cursor in self.expanded_states:
            preview_content = self.build_preview(self.all_rows[self.global_cursor])
            self._layout.middle = preview_content if preview_content is not None else ""
        else:
            self._layout.middle = ""

        # Zone 3: Footer
        # No border style — professional look as requested
        self._layout.bottom = _footer(page, total_pages)

        # Always push layout updates to widgets (called from both watchers and process_signal)
        self._update_ui_parts()

    def handle_action(self, key: str) -> None:
        """Deprecated legacy bridge."""
        pass


def paginate_table(
    all_rows: List[T],
    build_table: Callable[[List[T], int, int, set], Any],
    page_size: int = 10,
    header: Optional[Any] = None,
    build_preview: Optional[Callable[[T], Any]] = None,
    on_select: Optional[Callable[[T], Any]] = None,
    on_refresh: Optional[Callable[[], Tuple[List[T], Dict]]] = None,
) -> Optional[T]:
    """
    Paginate a list through a Rich Table with selection.

    Parameters
    ----------
    all_rows     : full list of data items.
    build_table  : receives a *slice* of rows and the *cursor_index* (relative to chunk),
                   returns a Rich Table.
    page_size    : rows per page.
    header       : optional Rich renderable to display above the table.
    build_preview: optional function that receives an item and returns a Rich renderable
                   to display below the table when the item is expanded.
    on_select    : callback that returns an AppScreen to push.
    on_refresh   : optional callback to fetch data from the server.

    Returns
    -------
    The selected item, or None if quit.
    """
    if not all_rows:
        console.print("[yellow]No results.[/yellow]")
        return None
    
    # We create a local state for the closure since all_rows inside screen won't 
    # magically update the build_table closure unless we are careful.
    class PagerState:
        rows = all_rows
        cache = {}

    def dynamic_table_builder(chunk, cursor, start, expanded):
        return build_table(chunk, cursor, start, expanded)

    def dynamic_preview_builder(item):
        return build_preview(item) if build_preview else None

    # We need to wrap on_refresh to update local closures if needed
    def refresh_wrapper():
        nonlocal all_rows
        if on_refresh:
            new_rows, new_cache = on_refresh()
            all_rows = new_rows # Update for the screen
            return new_rows, new_cache
        return all_rows, {}

    screen = _TablePagerScreen(
        all_rows, 
        build_table, 
        page_size, 
        header, 
        build_preview, 
        on_select,
        on_refresh=on_refresh # The screen needs the original one to update its own self.all_rows
    )
    run_screen(screen)
    return screen.result


# ── Panel pager ───────────────────────────────────────────────────────────────

class _PanelPagerScreen(AppScreen):
    """AppScreen backing paginate_panels(). Internal — use paginate_panels()."""

    alternate_screen = True

    DEFAULT_CSS = """
    _PanelPagerScreen {
        layout: vertical;
        background: transparent;
    }
    #body {
        height: 1fr;
    }
    #top_panel    { height: auto; margin-bottom: 1; }
    #middle_panel { height: 1fr; }
    #bottom_panel { height: auto; dock: bottom; }
    """

    # Reactive state
    page: reactive[int] = reactive(0)
    cursor: reactive[int] = reactive(0)
    expanded_states: reactive[set] = reactive(set())

    def __init__(self, all_items, build_panel_fn, page_size, header):
        super().__init__()
        self.all_items     = all_items
        self.build_panel_fn = build_panel_fn
        self.page_size     = page_size
        self.header        = header
        self.result        = None
        self._layout       = _PagerLayout()

    def compose(self) -> ComposeResult:
        """Compose layout with individual reactive widgets."""
        with Vertical(id="body"):
            yield Static(id="top_panel")
            yield Static(id="middle_panel")
        yield Static(id="bottom_panel")

    def watch_page(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()

    def watch_cursor(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()

    def watch_expanded_states(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()

    def on_mount(self) -> None:
        super().on_mount()
        self._update_all()

    def _update_all(self) -> None:
        try:
            self.query_one("#top_panel", Static).update(self._layout.top)
            self.query_one("#middle_panel", Static).update(self._layout.middle)
            self.query_one("#bottom_panel", Static).update(self._layout.bottom)
        except Exception:
            pass

    def _total_pages(self):
        return max(1, (len(self.all_items) + self.page_size - 1) // self.page_size)

    def _chunk(self):
        start = self.page * self.page_size
        return self.all_items[start : start + self.page_size], start

    def build_layout(self) -> Any:
        return _PagerLayout()

    def refresh_zones(self) -> None:
        from rich.panel import Panel
        chunk, start = self._chunk()
        total_pages  = self._total_pages()
        cursor = min(self.cursor, len(chunk) - 1)

        parts: list = []
        if self.header:
            parts.append(self.header)
        for i, item in enumerate(chunk):
            global_idx = start + i
            p = self.build_panel_fn(item, global_idx, i == cursor, global_idx in self.expanded_states)
            if p is not None:
                parts.append(p)
            else:
                parts.append(Text(f"Error rendering item {global_idx}", style="red"))

        self._layout.top    = Panel(Group(*parts), border_style="dim")
        self._layout.middle = ""
        self._layout.bottom = _footer(self.page, total_pages)

        # Always push layout updates to widgets
        self._update_all()

    def handle_action(self, key: str) -> Any:
        chunk, start = self._chunk()
        total_pages  = self._total_pages()
        cursor = min(self.cursor, len(chunk) - 1)

        if key == "escape":
            return SCREEN_EXIT
        if key == "enter":
            self.result = chunk[cursor]
            return SCREEN_EXIT
        if key == "space":
            gidx = start + cursor
            new_states = set(self.expanded_states)
            if gidx in new_states:
                new_states.discard(gidx)
            else:
                new_states.add(gidx)
            self.expanded_states = new_states  # reassign to trigger watcher
            return None  # watcher handles refresh
        if key in ("down", "j"):
            if cursor < len(chunk) - 1:
                self.cursor = cursor + 1
                return True
            elif self.page < total_pages - 1:
                self.page  += 1
                self.cursor = 0
                return True
        if key in ("up", "k"):
            if cursor > 0:
                self.cursor = cursor - 1
                return True
            elif self.page > 0:
                self.page  -= 1
                self.cursor = self.page_size - 1
                return True
        if (key in ("right", "n")) and self.page < total_pages - 1:
            self.page  += 1
            self.cursor = 0
            return True
        if (key in ("left", "p")) and self.page > 0:
            self.page -= 1
            self.cursor = 0
            return True
        return None


def paginate_panels(
    all_items: List[T],
    build_panel: Callable[[T, int, bool, bool], Any],
    page_size: int = 3,
    header: Optional[Any] = None,
) -> Optional[T]:
    """
    Paginate a list through Rich Panels with selection and expansion.

    Parameters
    ----------
    all_items  : full list of data items.
    build_panel: receives (item, global_index, is_selected, is_expanded), returns a Rich renderable.
    page_size  : items per page.
    header     : optional Rich renderable to display above the panels.

    Returns
    -------
    The selected item, or None if quit.
    """
    if not all_items:
        console.print("[yellow]No results.[/yellow]")
        return None
    screen = _PanelPagerScreen(all_items, build_panel, page_size, header)
    run_screen(screen)
    return screen.result
