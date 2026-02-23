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


def render_pause_transcript(text: str) -> Panel:
    """Transcript panel — mirrors render_transcription_panel() from recording screen.

    Returns a Rich Panel suitable for Static.update().
    """
    if text and text.strip():
        body: object = Markdown(text)
    else:
        body = Text("No transcript yet.", style="dim italic")
    return Panel(body, border_style="green", title="[bold]Transcript[/bold]")


def render_pause_footer(mode: str) -> Panel | Text:
    """
    Renders the footer based on the current mode ("read" or "edit").
    
    Uses the shared footer component for consistent styling.
    """
    if mode == "edit":
        actions = [
            ("Ctrl+S", "Save & Resume", "green"),
            ("Esc",    "Cancel Edit",   "red"),
        ]
        status = "✏ EDIT MODE"
    else:
        # standard read mode
        actions = [
            ("e",      "Edit Text", "yellow"),
            ("Esc",    "Resume Recording", "cyan"),
            ("Ctrl+C", "Stop Session", "red"),
        ]
        status = "⏸ PAUSED"

    return render_footer(
        actions=actions,
        status_msg=status,
        border=True,
        border_style="dim blue",
    )
