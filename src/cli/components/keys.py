"""
src/cli/components/keys.py

Cross-platform keyboard predicate helpers extracted from pager.py.
"""
from typing import Optional


def is_up(kind: Optional[str], key: Optional[bytes]) -> bool:
    """↑ arrow or k."""
    return (
        (kind == "char" and key in (b"k", b"K"))
        or (kind == "arrow" and key == b"H")    # Windows ↑
        or (kind == "escape" and key == b"[A")  # Unix ↑
    )


def is_down(kind: Optional[str], key: Optional[bytes]) -> bool:
    """↓ arrow or j."""
    return (
        (kind == "char" and key in (b"j", b"J"))
        or (kind == "arrow" and key == b"P")    # Windows ↓
        or (kind == "escape" and key == b"[B")  # Unix ↓
    )


def is_select(kind: Optional[str], key: Optional[bytes]) -> bool:
    """Enter key."""
    return kind == "char" and key in (b"\r", b"\n")


def is_quit(kind: Optional[str], key: Optional[bytes]) -> bool:
    return kind == "char" and key in (b"q", b"Q", b"\x03", b"\x1b")


def is_expand(kind: Optional[str], key: Optional[bytes]) -> bool:
    """Space key to expand/collapse."""
    return kind == "char" and key == b" "


def is_next_page(kind: Optional[str], key: Optional[bytes]) -> bool:
    """→ arrow or n."""
    return (
        (kind == "char" and key in (b"n", b"N"))
        or (kind == "arrow" and key == b"M")    # Windows →
        or (kind == "escape" and key == b"[C")  # Unix →
    )


def is_prev_page(kind: Optional[str], key: Optional[bytes]) -> bool:
    """← arrow or p."""
    return (
        (kind == "char" and key in (b"p", b"P"))
        or (kind == "arrow" and key == b"K")    # Windows ←
        or (kind == "escape" and key == b"[D")  # Unix ←
    )
