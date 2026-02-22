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
    title: str = "[bold blue]Connections[/bold blue]",
    border_style: str = "blue",
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
            title=title,
            border_style=border_style,
            expand=True,
        )

    link_tbl = Table(show_header=False, box=None, padding=(0, 2))
    link_tbl.add_column("Direction", style="bold")
    link_tbl.add_column("Type", style="cyan")
    link_tbl.add_column("Other ID", style="magenta")
    link_tbl.add_column("Summary", style="dim")

    def _trunc(s: str, n: int = 60) -> str:
        return s[:n] + "…" if len(s) > n else s

    max_rows = 4
    current_rows = 0

    if out_links:
        link_tbl.add_row("[blue]🔗 Outgoing[/blue]", "", "", "")
        current_rows += 1
        for i, lnk in enumerate(out_links):
            if current_rows >= max_rows:
                break
            # If we are at the last available row, and there are more links to show
            if current_rows == max_rows - 1 and (i < len(out_links) - 1 or in_links):
                link_tbl.add_row("  [dim]...[/dim]", f"[dim]+{len(out_links) - i} more[/dim]", "", "")
                current_rows += 1
                break
            summary = _trunc(note_summaries.get(lnk.target_id, ""))
            link_tbl.add_row("  [dim]↳[/dim]", lnk.relation_type, f"ID {lnk.target_id}", summary)
            current_rows += 1

    if in_links and current_rows < max_rows:
        # If we only have 1 row left, we can't even show the header + 1 link.
        # So we just show a summary row.
        if current_rows == max_rows - 1:
            link_tbl.add_row("[yellow]🔗 Incoming[/yellow]", f"[dim]+{len(in_links)} more[/dim]", "", "")
            current_rows += 1
        else:
            link_tbl.add_row("[yellow]🔗 Incoming[/yellow]", "", "", "")
            current_rows += 1
            for i, lnk in enumerate(in_links):
                if current_rows >= max_rows:
                    break
                if current_rows == max_rows - 1 and i < len(in_links) - 1:
                    link_tbl.add_row("  [dim]...[/dim]", f"[dim]+{len(in_links) - i} more[/dim]", "", "")
                    current_rows += 1
                    break
                summary = _trunc(note_summaries.get(lnk.source_id, ""))
                link_tbl.add_row("  [dim]↳[/dim]", lnk.relation_type, f"ID {lnk.source_id}", summary)
                current_rows += 1

    return Panel(
        link_tbl,
        title=title,
        border_style=border_style,
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
