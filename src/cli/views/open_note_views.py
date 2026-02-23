"""
Open Note views — pure rendering functions for the open_note command.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from shared.schemas.models.note import Note

def open_note_top_panel(note: "Note", arch_badge: str) -> Panel:
    """
    Full-detail panel for the open_note screen (used when the top zone is expanded).
    Shows ID, Date, Archipelago, Tags, and the full Markdown content.
    """
    date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
    tags_str = f"[magenta]{note.tags}[/magenta]" if note.tags else "[dim]No Tags[/dim]"

    meta_tbl = Table.grid(padding=(0, 4))
    meta_tbl.add_row(f"[bold cyan]ID:[/bold cyan] {note.id}", f"[bold cyan]Date:[/bold cyan] {date_str}")
    meta_tbl.add_row(f"[bold cyan]Archipelago:[/bold cyan] {arch_badge}", f"[bold cyan]Tags:[/bold cyan] {tags_str}")

    content_md = Markdown(note.content)

    return Panel(
        Group(meta_tbl, "", content_md),
        title=f"[bold green]Note #{note.id}[/bold green]",
        border_style="green",
        expand=True,
    )

def open_note_actions_panel() -> Panel:
    """
    Bottom panel for the open_note screen.
    Summarizes navigation controls.
    """
    from src.cli.components.footer import render_footer
    actions = [
        ("▲/▼", "Navigate", "yellow"),
        ("Space", "Expand/Select", "magenta"),
        ("Enter", "Open", "green"),
        ("Ctrl+C", "Back", "dim"),
    ]
    return render_footer(actions, border=True, border_style="dim cyan")
