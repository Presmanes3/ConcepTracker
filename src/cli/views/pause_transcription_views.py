"""
src/cli/views/pause_transcription_views.py

Pure render functions for the pause transcription screen.
No lifecycle, no Live, no console — data in, Rich Panel out.

Exported:
  PAUSE_MENU_ITEMS              List[Tuple[str, str]]  — shared with the screen
  render_pause_status()         → Panel
  render_pause_menu()           → Panel
  render_pause_content_text()   → Panel  (menu mode)
  render_pause_content_editor() → Panel  (edit mode)
"""
from __future__ import annotations

from typing import List, Tuple

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

# ── Shared menu definition ─────────────────────────────────────────────────────
# Exported so PauseTranscriptionScreen can iterate over it for key handling
# without duplicating the list.

PAUSE_MENU_ITEMS: List[Tuple[str, str]] = [
    ("✨ Enhance with AI", "enhance"),
    ("💾 Save",            "save"),
    ("✏  Edit Text",       "modify"),
    ("▶  Resume",          "continue"),
    ("🔄 New Session",     "restart"),
    ("❌ Discard",         "discard"),
]

# Fixed column width for the menu panel — longest label + panel borders + padding
PAUSE_MENU_COL_WIDTH: int = 26


# ── Render functions ───────────────────────────────────────────────────────────

def render_pause_status(time_str: str, words: int, tokens: int) -> Panel:
    """Top status bar: paused state, elapsed time, word and token counts."""
    return Panel(
        Text.from_markup(
            f"[bold yellow]⏸  PAUSED[/bold yellow]  |  "
            f"[cyan]Time:[/cyan] {time_str}  |  "
            f"[cyan]Words:[/cyan] {words}  |  "
            f"[cyan]Tokens (est):[/cyan] ~{tokens}"
        ),
        border_style="yellow",
        title="[bold]Status[/bold]",
    )


def render_pause_menu(menu_index: int, is_edit_mode: bool = False) -> Panel:
    """Left-column action menu.  Highlights the selected row when in menu mode."""
    rows: List[Text] = []
    for i, (label, _) in enumerate(PAUSE_MENU_ITEMS):
        if not is_edit_mode and i == menu_index:
            rows.append(Text(f"▶ {label}", style="bold black on bright_yellow"))
        else:
            rows.append(Text(f"  {label}", style="white"))

    is_active = not is_edit_mode
    return Panel(
        Group(*rows),
        title=(
            "[bold bright_yellow]Actions[/bold bright_yellow]"
            if is_active else
            "[dim]Actions[/dim]"
        ),
        border_style="bright_yellow" if is_active else "dim",
    )


def render_pause_content_text(full_text: str) -> Panel:
    """Right pane (menu mode): transcript text, capped at last 150 words."""
    words_all = full_text.split()
    truncated = len(words_all) > 150
    display   = " ".join(words_all[-150:])

    body = Text(overflow="fold")
    if truncated:
        body.append("… ", style="dim")
    body.append(
        display if display else "(empty transcription)",
        style="green" if display else "dim italic",
    )
    return Panel(body, border_style="dim", title="[bold]Transcription[/bold]")


def render_pause_content_editor(edit_buffer: str, edit_cursor: int) -> Panel:
    """Right pane (edit mode): inline editor with a block cursor (▌)."""
    before = edit_buffer[:edit_cursor]
    after  = edit_buffer[edit_cursor:]
    t = Text(overflow="fold")
    t.append(before, style="green")
    t.append("▌", style="bold bright_white")
    t.append(after, style="dim green")
    return Panel(
        t,
        border_style="yellow",
        title=(
            "[bold yellow]✏  Edit Transcription[/bold yellow]  "
            "[dim](Enter: confirm · Esc: cancel · ← →: move cursor)[/dim]"
        ),
    )
