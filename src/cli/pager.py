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

import sys
import time
from typing import Any, Callable, List, TypeVar, Optional, Tuple

from rich.console import Console, Group
from rich.rule import Rule
from rich.text import Text
from rich.live import Live

console = Console()

T = TypeVar("T")

# ── Cross-platform single-key read ────────────────────────────────────────────

def _getch_with_timeout(timeout: float = 0.2) -> Tuple[Optional[str], Optional[bytes]]:
    """
    Read one logical keypress with a timeout.
    Returns ('char', b'x'), ('arrow', b'M'), ('escape', b'[C'), or (None, None) on timeout.
    """
    if sys.platform == "win32":
        import msvcrt  # type: ignore
        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):          # extended key prefix
                    return "arrow", msvcrt.getch()
                return "char", ch
            time.sleep(0.02)
        return None, None
    else:
        import termios, tty, select  # type: ignore  # noqa: E401
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            r, _, _ = select.select([sys.stdin], [], [], timeout)
            if r:
                ch = sys.stdin.buffer.read(1)
                if ch == b"\x1b":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.01)
                    if r2:
                        seq = sys.stdin.buffer.read(2)
                        if seq == b"[A": return "escape", b"[A" # Up
                        if seq == b"[B": return "escape", b"[B" # Down
                        if seq == b"[C": return "escape", b"[C" # Right
                        if seq == b"[D": return "escape", b"[D" # Left
                        return "escape", seq
                return "char", ch
            return None, None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _is_expand(kind: Optional[str], key: Optional[bytes]) -> bool:
    """Space key to expand/collapse."""
    return kind == "char" and key == b" "

def _is_next_page(kind: Optional[str], key: Optional[bytes]) -> bool:
    """→ arrow or n."""
    return (
        (kind == "char"   and key in (b"n", b"N"))
        or (kind == "arrow"  and key == b"M")     # Windows →
        or (kind == "escape" and key == b"[C")    # Unix →
    )


def _is_prev_page(kind: Optional[str], key: Optional[bytes]) -> bool:
    """← arrow or p."""
    return (
        (kind == "char"   and key in (b"p", b"P"))
        or (kind == "arrow"  and key == b"K")     # Windows ←
        or (kind == "escape" and key == b"[D")    # Unix ←
    )

def _is_up(kind: Optional[str], key: Optional[bytes]) -> bool:
    """↑ arrow or k."""
    return (
        (kind == "char"   and key in (b"k", b"K"))
        or (kind == "arrow"  and key == b"H")     # Windows ↑
        or (kind == "escape" and key == b"[A")    # Unix ↑
    )

def _is_down(kind: Optional[str], key: Optional[bytes]) -> bool:
    """↓ arrow or j."""
    return (
        (kind == "char"   and key in (b"j", b"J"))
        or (kind == "arrow"  and key == b"P")     # Windows ↓
        or (kind == "escape" and key == b"[B")    # Unix ↓
    )

def _is_select(kind: Optional[str], key: Optional[bytes]) -> bool:
    """Enter key."""
    return kind == "char" and key in (b"\r", b"\n")

def _is_quit(kind: Optional[str], key: Optional[bytes]) -> bool:
    return kind == "char" and key in (b"q", b"Q", b"\x03", b"\x1b")


# ── Navigation footer ─────────────────────────────────────────────────────────

def _footer(page: int, total: int) -> Text:
    t = Text(justify="center")
    t.append(f"  Page {page + 1} / {total}  ", style="bold white")
    t.append("▲/▼ select  ", style="yellow")
    t.append("◀/▶ page  ", style="cyan")
    t.append("[Space] expand  ", style="magenta")
    t.append("[Enter] open  ", style="green")
    t.append("[q] quit", style="dim")
    return t


# ── Table pager ───────────────────────────────────────────────────────────────

def paginate_table(
    all_rows: List[T],
    build_table: Callable[[List[T], int, int, set], Any],
    page_size: int = 10,
    header: Optional[Any] = None,
    build_preview: Optional[Callable[[T], Any]] = None,
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

    global_cursor = 0
    expanded_states = set()

    with Live(auto_refresh=False, screen=True) as live:
        last_size = console.size
        while True:
            term_height = console.size.height
            
            # Calculate dynamic page size based on terminal height
            overhead = 10  # Table headers, borders, footer, rule
            if header:
                overhead += 2
                
            preview_height = 0
            preview_renderable = None
            if build_preview and global_cursor in expanded_states:
                preview_renderable = build_preview(all_rows[global_cursor])
                # Estimate preview height (borders + meta + content + padding)
                preview_height = 14

            dynamic_page_size = max(2, term_height - overhead - preview_height)
            
            # Calculate current page and chunk based on global_cursor
            page = global_cursor // dynamic_page_size
            cursor = global_cursor % dynamic_page_size
            total_pages = max(1, (len(all_rows) + dynamic_page_size - 1) // dynamic_page_size)

            start = page * dynamic_page_size
            chunk = all_rows[start : start + dynamic_page_size]
            
            # Ensure cursor is within bounds of current chunk (should be guaranteed by math, but safe)
            if cursor >= len(chunk):
                cursor = len(chunk) - 1

            renderables = []
            if header:
                renderables.append(header)
            renderables.append(build_table(chunk, cursor, start, expanded_states))
            
            if preview_renderable:
                renderables.append(preview_renderable)
                        
            renderables.append(Rule(style="dim blue"))
            renderables.append(_footer(page, total_pages))

            live.update(Group(*renderables), refresh=True)

            # Wait for input or resize
            while True:
                kind, key = _getch_with_timeout(0.1)
                if kind is None:
                    if console.size != last_size:
                        last_size = console.size
                        break  # Break inner loop to re-render
                    continue
                break  # Key pressed, break inner loop to handle it

            if kind is None:
                continue  # It was a resize, just re-render

            if _is_quit(kind, key):
                return None
            elif _is_select(kind, key):
                return all_rows[global_cursor]
            elif _is_expand(kind, key) and build_preview:
                if global_cursor in expanded_states:
                    expanded_states.remove(global_cursor)
                else:
                    # Clear other expanded states to keep only one preview at a time
                    expanded_states.clear()
                    expanded_states.add(global_cursor)
            elif _is_down(kind, key):
                if global_cursor < len(all_rows) - 1:
                    global_cursor += 1
                    # Auto-expand if we want master-detail to follow cursor
                    if expanded_states:
                        expanded_states.clear()
                        expanded_states.add(global_cursor)
            elif _is_up(kind, key):
                if global_cursor > 0:
                    global_cursor -= 1
                    if expanded_states:
                        expanded_states.clear()
                        expanded_states.add(global_cursor)
            elif _is_next_page(kind, key):
                if page < total_pages - 1:
                    global_cursor = min(len(all_rows) - 1, global_cursor + dynamic_page_size)
                    if expanded_states:
                        expanded_states.clear()
                        expanded_states.add(global_cursor)
            elif _is_prev_page(kind, key):
                if page > 0:
                    global_cursor = max(0, global_cursor - dynamic_page_size)
                    if expanded_states:
                        expanded_states.clear()
                        expanded_states.add(global_cursor)


# ── Panel pager ───────────────────────────────────────────────────────────────

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

    total_pages = max(1, (len(all_items) + page_size - 1) // page_size)
    page = 0
    cursor = 0
    
    # Keep track of expanded state for each item by its global index
    expanded_states = set()

    with Live(auto_refresh=False, screen=True) as live:
        last_size = console.size
        while True:
            start = page * page_size
            chunk = all_items[start : start + page_size]
            
            if cursor >= len(chunk):
                cursor = len(chunk) - 1

            renderables = []
            if header:
                renderables.append(header)
            for i, item in enumerate(chunk):
                global_idx = start + i
                is_expanded = global_idx in expanded_states
                renderables.append(build_panel(item, global_idx, i == cursor, is_expanded))
            renderables.append(Rule(style="dim blue"))
            renderables.append(_footer(page, total_pages))

            live.update(Group(*renderables), refresh=True)

            # Wait for input or resize
            while True:
                kind, key = _getch_with_timeout(0.1)
                if kind is None:
                    if console.size != last_size:
                        last_size = console.size
                        break  # Break inner loop to re-render
                    continue
                break  # Key pressed, break inner loop to handle it

            if kind is None:
                continue  # It was a resize, just re-render

            if _is_quit(kind, key):
                return None
            elif _is_select(kind, key):
                return chunk[cursor]
            elif _is_expand(kind, key):
                global_idx = start + cursor
                if global_idx in expanded_states:
                    expanded_states.remove(global_idx)
                else:
                    expanded_states.add(global_idx)
            elif _is_down(kind, key):
                if cursor < len(chunk) - 1:
                    cursor += 1
                elif page < total_pages - 1:
                    page += 1
                    cursor = 0
            elif _is_up(kind, key):
                if cursor > 0:
                    cursor -= 1
                elif page > 0:
                    page -= 1
                    cursor = page_size - 1
            elif _is_next_page(kind, key) and page < total_pages - 1:
                page += 1
                cursor = 0
            elif _is_prev_page(kind, key) and page > 0:
                page -= 1
                cursor = 0
