"""
src/cli/views/transcription_views.py

Pure render functions for the live recording screen.
No lifecycle, no Live, no console — data in, Rich Panel out.

Exported:
  render_recording_status()    → Panel
  render_transcription_panel() → Panel
  render_navigation_panel()    → Panel  (static, build once per session)
"""
from __future__ import annotations

from typing import List

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from src.cli.components.footer import render_footer


def render_recording_status(
    rec_icon: str,
    rec_style: str,
    time_str: str,
    words: int,
    tokens: int,
) -> Panel:
    """Status bar: blinking dot, elapsed time, word count, token estimate."""
    info = Text()
    info.append(f"{rec_icon} ",       style=rec_style)
    info.append("RECORDING",          style="bold red")
    info.append("  │  ",              style="dim")
    info.append("Time: ",             style="dim cyan")
    info.append(time_str,             style="cyan")
    info.append("  │  ",              style="dim")
    info.append("Words: ",            style="dim cyan")
    info.append(str(words),           style="cyan")
    info.append("  │  ",              style="dim")
    info.append("Tokens (est): ",     style="dim cyan")
    info.append(f"~{tokens}",         style="cyan")
    return Panel(info, border_style="dim", title="[bold]Recording[/bold]")


def render_transcription_panel(
    full_transcript: List[str],
    current_partial: str = "",
) -> Panel:
    """Scrolling transcript panel — renders confirmed text as Markdown + dim partial."""
    full_text = " ".join(full_transcript).strip()

    if full_text and current_partial:
        # Markdown body + trailing partial hint
        body: object = Group(
            Markdown(full_text),
            Text(current_partial, style="dim"),
        )
    elif full_text:
        body = Markdown(full_text)
    elif current_partial:
        body = Text(current_partial, style="dim")
    else:
        body = Text("Listening…", style="dim italic")

    return Panel(
        body,
        border_style="dim",
        title="[bold]Live Transcription[/bold]",
    )


def render_navigation_panel() -> "Panel | Text":
    """Footer for the recording screen — docked at the bottom."""
    return render_footer(
        actions=[
            ("Esc",    "Pause",   "cyan"),
            ("s",      "Save",    "green"),
            ("Ctrl+X", "Discard", "red"),
        ],
        border=True,
        border_style="dim",
    )

