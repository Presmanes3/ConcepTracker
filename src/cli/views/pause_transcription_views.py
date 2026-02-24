"""
src/cli/views/pause_transcription_views.py

Pure render functions for the pause transcription screen.
No lifecycle, no Live, no console — data in, Rich renderable out.

Per CLI_ARCHITECTURE.MD: Views are stateless and data-driven.

Exported:
  PAUSE_MENU_ITEMS        List[Tuple[str, str]]  constant shared with the screen
  render_pause_status()   → Panel                status bar
  render_pause_transcript()→ Panel               transcript pane
"""
from __future__ import annotations

from typing import List, Tuple

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from src.cli.components.footer import render_footer

# ── Menu items ─────────────────────────────────────────────────────────────────
# Shared with PauseTranscriptionScreen so menu labels and action identifiers
# are defined in exactly one place (single source of truth).

PAUSE_MENU_ITEMS: List[Tuple[str, str]] = [
    ("▶  Resume",          "resume"),
    ("✏  Modify Text",     "modify"),
    ("✨ Enhance with AI",  "enhance"),
    ("💾 Save",            "save"),
    ("✖  Cancel / Exit",   "discard"),
]


# ── Render functions ───────────────────────────────────────────────────────────

def render_pause_status(time_str: str, words: int, tokens: int) -> Panel:
    """Status bar: pause indicator, elapsed time, word and token counts.

    Returns a Rich Panel — same style as render_recording_status() but yellow.
    """
    info = Text()
    info.append("⏸  PAUSED", style="bold yellow")
    info.append("  │  ", style="dim")
    info.append("Time: ",         style="dim cyan")
    info.append(time_str,          style="cyan")
    info.append("  │  ", style="dim")
    info.append("Words: ",        style="dim cyan")
    info.append(str(words),        style="cyan")
    info.append("  │  ", style="dim")
    info.append("Tokens (est): ", style="dim cyan")
    info.append(f"~{tokens}",      style="cyan")
    return Panel(info, border_style="yellow", title="[bold]Paused[/bold]")


def render_pause_transcript(text: str, title: str = "Transcript") -> Panel:
    """Transcript / live-preview panel.

    Args:
        text:  Content to render as Rich Markdown.
        title: Panel title — "Transcript" (read mode) or "Preview" (edit mode).

    Returns a Rich Panel suitable for Static.update().
    """
    if text and text.strip():
        body: object = Markdown(text)
    else:
        body = Text("No transcript yet.", style="dim italic")
    return Panel(body, border_style="green", title=f"[bold]{title}[/bold]")


def render_pause_footer(mode: str) -> Panel:
    """Context-sensitive footer with mnemonic keys.

    READ:  Esc Resume · e Edit · s Save · Ctrl+X Discard
    EDIT:  Ctrl+S Save edit · Esc Cancel
    """
    if mode == "edit":
        actions = [
            ("Ctrl+S", "Save edit",  "green"),
            ("Esc",    "Cancel",     "yellow"),
        ]
    else:
        actions = [
            ("Esc",    "Resume",     "cyan"),
            ("e",      "Edit",       "yellow"),
            ("s",      "Save",       "green"),
            ("Ctrl+X", "Discard",    "red"),
        ]

    return render_footer(
        actions=actions,
        border=True,
        border_style="dim blue",
    )
