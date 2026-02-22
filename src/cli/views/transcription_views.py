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

from rich.align import Align
from rich.panel import Panel
from rich.text import Text


def render_recording_status(
    rec_icon: str,
    rec_style: str,
    time_str: str,
    words: int,
    tokens: int,
) -> Panel:
    """Status bar: blinking dot, elapsed time, word count, token estimate."""
    info_text = Text.from_markup(
        f"[{rec_style}]{rec_icon}[/{rec_style}] [bold red]RECORDING[/bold red] | "
        f"[cyan]Time:[/cyan] {time_str} | "
        f"[cyan]Words:[/cyan] {words} | "
        f"[cyan]Tokens (est):[/cyan] ~{tokens}"
    )
    return Panel(info_text, border_style="blue", title="[bold]Recording[/bold]")


def render_transcription_panel(
    full_transcript: List[str],
    current_partial: str = "",
) -> Panel:
    """Scrolling transcript panel — shows last 100 words + live partial."""
    full_text = " ".join(full_transcript)
    display_words = full_text.split()[-100:]
    display_text  = " ".join(display_words)

    trans_text = Text()
    if display_words and len(full_text.split()) > 100:
        trans_text.append("… ", style="dim")
    if display_text:
        trans_text.append(display_text + " ", style="green")
    if current_partial:
        trans_text.append(current_partial, style="dim")

    return Panel(
        Align.left(trans_text, vertical="top"),
        border_style="green",
        title="[bold]Live Transcription[/bold]",
    )


def render_navigation_panel() -> Panel:
    """Static navigation hint for the recording screen (build once per session)."""
    footer_text = Text.from_markup(
        "[dim]Press[/dim] [bold cyan]Ctrl+C[/bold cyan] "
        "[dim]to pause or stop recording[/dim]"
    )
    return Panel(
        Align.center(footer_text, vertical="middle"),
        border_style="dim",
        title="[bold]Navigation[/bold]",
    )

