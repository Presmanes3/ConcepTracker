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

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.cli.views.link_views import link_table_view, links_inline_text

if TYPE_CHECKING:
    from shared.schemas.models.note import Note
    from shared.schemas.models.link import Link

# ── Type aliases ───────────────────────────────────────────────────────────
ArchCache = Dict[int, str]


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
    border_style: str = "dim",
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

    content_md = Markdown(content)
    summary_text = f"[dim italic]Summary: {note.summary}[/dim italic]"
    
    renderables = [meta, "", content_md, "", summary_text]

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
        border_style="dim",
        expand=True,
    )


def note_detail_view(
    note: "Note",
    arch_badge: str = "[dim]~island~[/dim]",
    out_links: Optional["List[Link]"] = None,
    in_links: Optional["List[Link]"] = None,
    note_summaries: Optional[Dict[int, str]] = None,
) -> Group:
    """
    Rich Group renderable for the ColumnMenu header.
    Returns a plain Group (note panel stacked above connections panel) so it
    can be embedded directly inside a Layout zone without nesting Layout objects.
    All data must be pre-fetched.
    """
    out_links = out_links or []
    in_links = in_links or []

    meta = _meta_table(note, arch_badge)
    content_md = Markdown(note.content)
    summary_panel = Panel(
        f"[italic]{note.summary}[/italic]",
        title="[bold]TL;DR / Summary[/bold]",
        border_style="dim",
        title_align="left",
    )

    main_panel = Panel(
        Group(meta, Rule(style="dim"), content_md, "", summary_panel),
        title=f"[bold green]Note #{note.id}[/bold green]",
        border_style="dim",
        expand=True,
    )

    connections = link_table_view(out_links, in_links, note_summaries)

    return Group(main_panel, connections)


# ── Pager table builders ───────────────────────────────────────────────────

def note_list_table_view(
    chunk: list,
    cursor_index: int,
    start_idx: int,
    expanded_states: set,
    arch_cache: ArchCache,
    total_notes: int,
) -> Table:
    """
    Build the Rich Table for the `ls` pager page.
    Pure function: data in, Table out — no DB calls, no console.print().
    """
    table = Table(
        title=f"Knowledge Captures  [dim]({total_notes} total)[/dim]",
        border_style="dim",
        box=None,
    )
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Tag", style="magenta")
    table.add_column("Archipelago", style="yellow")
    table.add_column("Summary", style="white")

    for i, n in enumerate(chunk):
        global_idx = start_idx + i
        arch_label = arch_cache.get(n.archipelago_id, "[dim]~island~[/dim]")
        style = "reverse" if i == cursor_index else None
        is_expanded = global_idx in expanded_states
        expand_indicator = "[-]" if is_expanded else "[+]"
        id_str = f"{expand_indicator} {n.id}"
        summary = n.summary if len(n.summary) <= 60 else n.summary[:57] + "..."
        table.add_row(
            id_str,
            n.created_at.strftime("%b %d %H:%M"),
            n.tags or "-",
            arch_label,
            summary,
            style=style,
        )
    return table


def note_find_table_view(
    chunk: list,
    cursor_index: int,
    start_idx: int,
    expanded_states: set,
    arch_cache: ArchCache,
    query: str,
    total_results: int,
) -> Table:
    """
    Build the Rich Table for the `find` pager page.
    Pure function: data in, Table out — no DB calls, no console.print().
    """
    table = Table(
        title=f"Top {total_results} matches for: [italic]'{query}'[/italic]",
        border_style="dim",
        box=None,
    )
    table.add_column("Match", style="green", justify="right")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("Tag", style="magenta")
    table.add_column("Archipelago", style="yellow")
    table.add_column("Summary", style="white")

    for i, item in enumerate(chunk):
        note, distance = item
        global_idx = start_idx + i
        percentage = max(0, min(100, int((1 - distance) * 100)))
        match_color = "green" if percentage > 70 else "yellow"
        match_str = f"[{match_color}]{percentage}%[/{match_color}]"
        arch_label = arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]")
        style = "reverse" if i == cursor_index else None
        is_expanded = global_idx in expanded_states
        expand_indicator = "[-]" if is_expanded else "[+]"
        id_str = f"{expand_indicator} {note.id}"
        summary = note.summary if len(note.summary) <= 50 else note.summary[:47] + "..."
        table.add_row(
            match_str,
            id_str,
            note.created_at.strftime("%b %d %H:%M"),
            note.tags or "-",
            arch_label,
            summary,
            style=style,
        )
    return table

