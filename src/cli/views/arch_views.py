"""
Archipelago view helpers — pure rendering, no DB access.

All functions accept pre-resolved data and return Rich markup strings or renderables.
"""
from __future__ import annotations
from typing import Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from shared.schemas.models.note import Note


def archipelago_badge(arch_name: Optional[str], arch_type: Optional[str] = None) -> str:
    """
    Return a Rich-markup badge string for an archipelago.

    Args:
        arch_name:  Display name, or None/empty for island notes.
        arch_type:  "continent" | "archipelago" | None.
    """
    if not arch_name:
        return "[dim]~island~[/dim]"
    icon = "\U0001f30d" if arch_type == "continent" else "\U0001f5fa\ufe0f"
    return f"{icon} [yellow]{arch_name}[/yellow]"


def prefetch_arch_cache(notes: "List[Note]", arch_repo) -> Dict[int, str]:
    """
    Pre-resolve archipelago badges for a list of notes in the minimum number of DB calls.
    Returns a dict mapping archipelago_id -> badge markup string.

    Args:
        notes:      Iterable of Note objects (or (Note, score) tuples).
        arch_repo:  An ArchipelagoRepository instance (from repos.archipelagos).
    """
    cache: Dict[int, str] = {}
    for item in notes:
        # Support both plain Note and (note, distance) tuples from semantic_search
        note = item[0] if isinstance(item, (tuple, list)) else item
        arch_id = getattr(note, "archipelago_id", None)
        if arch_id and arch_id not in cache:
            arch = arch_repo.get_archipelago_by_id(arch_id)
            cache[arch_id] = archipelago_badge(
                arch.name if arch else None,
                arch.type if arch else None,
            )
    return cache
