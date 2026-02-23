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

from src.cli.screen import AppScreen, SCREEN_EXIT, run_screen
# No longer using _input.py for key detection, using Textual's key names.
from src.cli.components.footer import render_footer

console = Console()

T = TypeVar("T")


# ── Navigation footer ─────────────────────────────────────────────────────────

def _footer(page: int, total: int) -> Any:
    actions = [
        ("▲/▼", "[yellow]select[/yellow]", "yellow"),
        ("◀/▶", "[cyan]page[/cyan]", "cyan"),
        ("Space", "expand", "magenta"),
        ("Enter", "open", "green"),
        ("Ctrl+C", "quit", "dim"),
    ]
    return render_footer(actions, (page, total), border=False)


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

from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widgets import Static

class _TablePagerScreen(AppScreen):
    """AppScreen backing paginate_table(). Internal — use paginate_table()."""

    alternate_screen = True
    
    # Reactive state: when these change, the relevant UI parts will update
    global_cursor: reactive[int] = reactive(0)
    expanded_states: reactive[set] = reactive(set)

    def __init__(self, all_rows, build_table_fn, page_size, header, build_preview, on_select=None):
        super().__init__()
        self.all_rows      = all_rows
        self.build_table_fn = build_table_fn
        self.user_page_size = page_size
        self.header        = header
        self.build_preview = build_preview
        self.on_select     = on_select  # Callable[[item], AppScreen|None]
        self.result        = None
        self._dyn_page_size = page_size  # updated each refresh
        self._layout       = _PagerLayout()  # Initialize BEFORE refresh_zones() is called in on_mount

    def compose(self) -> ComposeResult:
        """Compose layout with individual reactive widgets."""
        yield Static(id="top_panel")
        yield Static(id="middle_panel")
        yield Static(id="bottom_panel")

    def watch_global_cursor(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()
            self._update_ui_parts()

    def watch_expanded_states(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()
            self._update_ui_parts()

    def on_mount(self) -> None:
        """Called when the screen is active."""
        super().on_mount()
        # Ensure initial display
        self._update_ui_parts()

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
            self.expanded_states.clear()
            self.expanded_states.add(self.global_cursor)
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
        # This keeps the panel height constant
        if hasattr(table_content, "add_row"):
            rows_to_add = self.user_page_size - len(chunk)
            for _ in range(rows_to_add):
                # Add an empty row with the correct number of columns
                empty_row = [""] * len(table_content.columns)
                table_content.add_row(*empty_row)

        if self.header:
            table_content = Group(self.header, table_content)
            
        self._layout.top = Panel(table_content, title=panel_title, border_style="blue")

        # Zone 2: Preview
        if self.build_preview and self.global_cursor in self.expanded_states:
            preview_content = self.build_preview(self.all_rows[self.global_cursor])
            self._layout.middle = preview_content if preview_content is not None else ""
        else:
            self._layout.middle = ""

        # Zone 3: Footer
        self._layout.bottom = Panel(_footer(page, total_pages), border_style="dim blue")

    def handle_action(self, key: str) -> Any:
        page, total_pages, *_ = self._compute()
        dyn = self._dyn_page_size

        if key == "escape":
            self.result = None
            return SCREEN_EXIT
        if key == "enter":
            item = self.all_rows[self.global_cursor]
            if self.on_select:
                # Push the note/detail screen; stay in this Textual session
                screen = self.on_select(item)
                if screen is not None:
                    return screen  # process_signal will push_screen
            self.result = item
            return SCREEN_EXIT
        if key == "space" and self.build_preview:
            idx = self.global_cursor
            if idx in self.expanded_states:
                self.expanded_states.discard(idx)
            else:
                self.expanded_states.clear()
                self.expanded_states.add(idx)
            return True
        if key in ("down", "j"):     return self._move_cursor(+1) or None
        if key in ("up", "k"):        return self._move_cursor(-1) or None
        if key in ("right", "n"): return self._move_cursor(+dyn) or None
        if key in ("left", "p"): return self._move_cursor(-dyn) or None
        return None


def paginate_table(
    all_rows: List[T],
    build_table: Callable[[List[T], int, int, set], Any],
    page_size: int = 10,
    header: Optional[Any] = None,
    build_preview: Optional[Callable[[T], Any]] = None,
    on_select: Optional[Callable[[T], Any]] = None,
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

    Returns
    -------
    The selected item, or None if quit.
    """
    if not all_rows:
        console.print("[yellow]No results.[/yellow]")
        return None
    screen = _TablePagerScreen(all_rows, build_table, page_size, header, build_preview, on_select)
    run_screen(screen)
    return screen.result


# ── Panel pager ───────────────────────────────────────────────────────────────

class _PanelPagerScreen(AppScreen):
    """AppScreen backing paginate_panels(). Internal — use paginate_panels()."""

    alternate_screen = True

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
        yield Static(id="top_panel")
        yield Static(id="middle_panel")
        yield Static(id="bottom_panel")

    def watch_page(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()
            self._update_all()

    def watch_cursor(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()
            self._update_all()

    def watch_expanded_states(self, _) -> None:
        if self.is_mounted:
            self.refresh_zones()
            self._update_all()

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

        self._layout.top    = Panel(Group(*parts), border_style="blue")
        self._layout.middle = ""
        self._layout.bottom = Panel(_footer(self.page, total_pages), border_style="dim blue")

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
            if gidx in self.expanded_states:
                self.expanded_states.discard(gidx)
            else:
                self.expanded_states.add(gidx)
            return True
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
