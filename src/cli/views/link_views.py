"""
Link view helpers — pure rendering, no DB access.

Accepts pre-fetched link lists and note summaries and returns Rich renderables.
"""
from __future__ import annotations
from typing import List, Optional, Dict, TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from shared.schemas.models.link import Link


def link_table_view(
    out_links: "List[Link]",
    in_links: "List[Link]",
    note_summaries: Optional[Dict[int, str]] = None,
) -> Panel:
    """
    Render incoming and outgoing links as a Rich Panel.

    Args:
        out_links:       Links where note is the source.
        in_links:        Links where note is the target.
        note_summaries:  Optional dict mapping note_id -> summary for context rows.
    """
    note_summaries = note_summaries or {}

    if not out_links and not in_links:
        return Panel(
            "[dim]No links connected to this note.[/dim]",
            title="[bold blue]Connections[/bold blue]",
            border_style="blue",
            expand=True,
        )

    link_tbl = Table(show_header=False, box=None, padding=(0, 2))
    link_tbl.add_column("Direction", style="bold")
    link_tbl.add_column("Type", style="cyan")
    link_tbl.add_column("Other ID", style="magenta")
    link_tbl.add_column("Summary", style="dim")

    def _trunc(s: str, n: int = 60) -> str:
        return s[:n] + "…" if len(s) > n else s

    if out_links:
        link_tbl.add_row("[blue]🔗 Outgoing[/blue]", "", "", "")
        for lnk in out_links:
            summary = _trunc(note_summaries.get(lnk.target_id, ""))
            link_tbl.add_row("  [dim]↳[/dim]", lnk.relation_type, f"ID {lnk.target_id}", summary)

    if in_links:
        if out_links:
            link_tbl.add_row("", "", "", "")  # spacer
        link_tbl.add_row("[yellow]🔗 Incoming[/yellow]", "", "", "")
        for lnk in in_links:
            summary = _trunc(note_summaries.get(lnk.source_id, ""))
            link_tbl.add_row("  [dim]↳[/dim]", lnk.relation_type, f"ID {lnk.source_id}", summary)

    return Panel(
        link_tbl,
        title="[bold blue]Connections[/bold blue]",
        border_style="blue",
        expand=True,
    )


def links_inline_text(
    out_links: "List[Link]",
    in_links: "List[Link]",
) -> Text:
    """
    Compact one-line Rich Text showing link counts, used inside note cards.
    """
    t = Text()
    if not out_links and not in_links:
        t.append("No links.", style="dim")
        return t
    if out_links:
        t.append(f"🔗 {len(out_links)} out ", style="bold blue")
        t.append(", ".join(f"[{l.relation_type}→{l.target_id}]" for l in out_links))
    if in_links:
        if out_links:
            t.append("  ")
        t.append(f"🔗 {len(in_links)} in ", style="bold yellow")
        t.append(", ".join(f"[{l.relation_type}←{l.source_id}]" for l in in_links))
    return t
