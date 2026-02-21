"""
Note view components — pure rendering, no DB access.

All functions receive pre-fetched data as arguments.

Components
----------
note_card_view        Compact Rich Panel used in paginated list/find results.
note_header_view      5-line header Panel used at top of ColumnMenu (note action menu).
note_detail_view      Full Rich Group with Markdown content + link table (ColumnMenu right pane).
"""
from __future__ import annotations
from typing import Optional, List, Dict, TYPE_CHECKING

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.cli.views.link_views import link_table_view, links_inline_text

if TYPE_CHECKING:
    from shared.schemas.models.note import Note
    from shared.schemas.models.link import Link


# ── Helpers ────────────────────────────────────────────────────────────────

def _meta_table(note: "Note", arch_badge: str) -> Table:
    date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
    tags_str = f"[magenta]{note.tags}[/magenta]" if note.tags else "[dim]No Tags[/dim]"
    tbl = Table.grid(padding=(0, 4))
    tbl.add_row(f"[bold cyan]ID:[/bold cyan] {note.id}", f"[bold cyan]Date:[/bold cyan] {date_str}")
    tbl.add_row(f"[bold cyan]Archipelago:[/bold cyan] {arch_badge}", f"[bold cyan]Tags:[/bold cyan] {tags_str}")
    return tbl


def _trunc(s: str, n: int) -> str:
    return s[:n] + "…" if len(s) > n else s


# ── Public components ──────────────────────────────────────────────────────

def note_card_view(
    note: "Note",
    arch_badge: str = "[dim]~island~[/dim]",
    out_links: Optional["List[Link]"] = None,
    in_links: Optional["List[Link]"] = None,
    title: Optional[str] = None,
    border_style: str = "green",
    truncate_content: Optional[int] = None,
) -> Panel:
    """
    Compact card Panel used in ls/find previews.
    All data must be pre-fetched; this function does zero DB calls.
    """
    out_links = out_links or []
    in_links = in_links or []

    meta = _meta_table(note, arch_badge)
    content = note.content
    if truncate_content and len(content) > truncate_content:
        content = content[:truncate_content] + "…"

    body = f"{content}\n\n[dim italic]Summary: {note.summary}[/dim italic]"
    renderables = [meta, "", body]

    if out_links or in_links:
        renderables += ["", links_inline_text(out_links, in_links)]

    if title is None:
        title = f"[bold green]Preview: Note #{note.id}[/bold green]"

    return Panel(Group(*renderables), title=title, border_style=border_style)


def note_header_view(
    note: "Note",
    arch_badge: str = "[dim]~island~[/dim]",
) -> Panel:
    """
    Compact 5-line header Panel for ColumnMenu.
    Shows metadata + one-line summary preview — keeps the action menu fully visible on screen.
    """
    meta = _meta_table(note, arch_badge)
    preview = _trunc(note.summary, 120)

    return Panel(
        Group(meta, "", Text(preview, style="italic dim")),
        title=f"[bold green]Note #{note.id}[/bold green]",
        border_style="green",
        expand=True,
    )


from rich.layout import Layout

def note_detail_view(
    note: "Note",
    arch_badge: str = "[dim]~island~[/dim]",
    out_links: Optional["List[Link]"] = None,
    in_links: Optional["List[Link]"] = None,
    note_summaries: Optional[Dict[int, str]] = None,
) -> Layout:
    """
    Full Rich Layout suitable for a ColumnMenu header or standalone display.
    Renders metadata, Markdown content, summary panel, and a links table.
    All data must be pre-fetched.
    """
    out_links = out_links or []
    in_links = in_links or []

    meta = _meta_table(note, arch_badge)
    content_md = Markdown(note.content)
    summary_panel = Panel(
        f"[italic]{note.summary}[/italic]",
        title="[dim]TL;DR / Summary[/dim]",
        border_style="dim",
        title_align="left",
    )

    main_panel = Panel(
        Group(meta, Rule(style="dim"), content_md, "", summary_panel),
        title=f"[bold green]Note #{note.id}[/bold green]",
        border_style="green",
        expand=True,
    )

    connections = link_table_view(out_links, in_links, note_summaries)

    # Calculate connections height
    num_links = len(out_links) + len(in_links)
    if num_links == 0:
        conn_height = 3 # Panel borders + 1 line of text
    else:
        conn_height = 2 + num_links + (1 if out_links else 0) + (1 if in_links else 0) + (1 if out_links and in_links else 0)
        # Cap the height to avoid taking up the whole screen if there are too many links
        conn_height = min(conn_height, 12)

    layout = Layout()
    layout.split_column(
        Layout(main_panel, name="note"),
        Layout(connections, name="connections", size=conn_height)
    )

    return layout
