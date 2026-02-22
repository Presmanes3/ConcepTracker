"""
Cross-platform single-key input utilities.

Used by screen.py (AppScreen runner) and pager.py.
Kept in a separate module to avoid circular imports.
"""
from __future__ import annotations

import sys
import time
from typing import Optional, Tuple


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
                        if seq == b"[A": return "escape", b"[A"  # Up
                        if seq == b"[B": return "escape", b"[B"  # Down
                        if seq == b"[C": return "escape", b"[C"  # Right
                        if seq == b"[D": return "escape", b"[D"  # Left
                        return "escape", seq
                return "char", ch
            return None, None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Key classifiers ───────────────────────────────────────────────────────────

def _is_expand(kind: Optional[str], key: Optional[bytes]) -> bool:
    """Space key to expand/collapse."""
    return kind == "char" and key == b" "


def _is_next_page(kind: Optional[str], key: Optional[bytes]) -> bool:
    """→ arrow or n."""
    return (
        (kind == "char"   and key in (b"n", b"N"))
        or (kind == "arrow"  and key == b"M")      # Windows →
        or (kind == "escape" and key == b"[C")     # Unix →
    )


def _is_prev_page(kind: Optional[str], key: Optional[bytes]) -> bool:
    """← arrow or p."""
    return (
        (kind == "char"   and key in (b"p", b"P"))
        or (kind == "arrow"  and key == b"K")      # Windows ←
        or (kind == "escape" and key == b"[D")     # Unix ←
    )


def _is_up(kind: Optional[str], key: Optional[bytes]) -> bool:
    """↑ arrow or k."""
    return (
        (kind == "char"   and key in (b"k", b"K"))
        or (kind == "arrow"  and key == b"H")      # Windows ↑
        or (kind == "escape" and key == b"[A")     # Unix ↑
    )


def _is_down(kind: Optional[str], key: Optional[bytes]) -> bool:
    """↓ arrow or j."""
    return (
        (kind == "char"   and key in (b"j", b"J"))
        or (kind == "arrow"  and key == b"P")      # Windows ↓
        or (kind == "escape" and key == b"[B")     # Unix ↓
    )


def _is_select(kind: Optional[str], key: Optional[bytes]) -> bool:
    """Enter key."""
    return kind == "char" and key in (b"\r", b"\n")


def _is_quit(kind: Optional[str], key: Optional[bytes]) -> bool:
    return kind == "char" and key in (b"q", b"Q", b"\x03", b"\x1b")
