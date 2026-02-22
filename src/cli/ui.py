"""
src/cli/ui.py — REMOVED.

All rendering logic lives in src/cli/views/ and src/cli/screens/.
This file is intentionally empty. Import directly from those packages.
"""



def get_archipelago_badge(
    archipelago_id: Optional[int],
    arch_cache: Optional[dict] = None,
) -> str:
    """
    DEPRECATED — use src.cli.views.arch_views.archipelago_badge() instead,
    with pre-fetched data via prefetch_arch_cache().

    Kept for backward compat: still does a live DB lookup when cache misses.
    """
    if arch_cache is not None and archipelago_id in arch_cache:
        return arch_cache[archipelago_id]
    if not archipelago_id:
        return "[dim]~island~[/dim]"
    from src.repository.archipelago_repository import archipelago_repository
    arch = archipelago_repository.get_archipelago_by_id(archipelago_id)
    return archipelago_badge(arch.name if arch else None, arch.type if arch else None)


def build_note_preview(
    note,
    arch_cache: Optional[dict] = None,
    title: Optional[str] = None,
    border_style: str = "green",
    show_links: bool = True,
    truncate_content: Optional[int] = None,
) -> "Panel":
    """DEPRECATED — use src.cli.views.note_views.note_card_view() instead."""
    badge = get_archipelago_badge(note.archipelago_id, arch_cache)
    out_links, in_links = [], []
    if show_links:
        from src.repository.link_repository import link_repository
        out_links = link_repository.get_links_by_source(note.id)
        in_links = link_repository.get_links_by_target(note.id)
    return note_card_view(
        note,
        arch_badge=badge,
        out_links=out_links,
        in_links=in_links,
        title=title,
        border_style=border_style,
        truncate_content=truncate_content,
    )


def build_note_header(note) -> "Panel":
    """DEPRECATED — use src.cli.views.note_views.note_header_view() instead."""
    badge = get_archipelago_badge(note.archipelago_id)
    return note_header_view(note, arch_badge=badge)


def build_note_dashboard(note) -> "Group":
    """DEPRECATED — use src.cli.views.note_views.note_detail_view() instead."""
    from src.repository.link_repository import link_repository
    from src.repository.note_repository import repository

    badge = get_archipelago_badge(note.archipelago_id)
    out_links = link_repository.get_links_by_source(note.id)
    in_links = link_repository.get_links_by_target(note.id)

    summaries: dict = {}
    for lnk in out_links:
        n = repository.get_note_by_id(lnk.target_id)
        summaries[lnk.target_id] = n.summary if n else ""
    for lnk in in_links:
        n = repository.get_note_by_id(lnk.source_id)
        summaries[lnk.source_id] = n.summary if n else ""

    return note_detail_view(note, arch_badge=badge, out_links=out_links, in_links=in_links, note_summaries=summaries)

