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

from rich.markdown import Markdown
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
    """Scrolling transcript panel — renders confirmed text as Markdown + dim partial."""
    full_text = " ".join(full_transcript).strip()

    if full_text and current_partial:
        # Markdown body + trailing partial hint
        from rich.console import Group
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
        border_style="green",
        title="[bold]Live Transcription[/bold]",
    )


def render_recording_side_panel(blink: bool = True) -> Panel:
    """Right column: recording indicator + single shortcut hint."""
    from rich.console import Group
    dot = "[bold red]●[/bold red]" if blink else "[dim red]○[/dim red]"
    lines = [
        Text.from_markup(f"{dot} [bold red]RECORDING[/bold red]"),
        Text(""),
        Text.from_markup("[dim]Space to pause[/dim]"),
    ]
    return Panel(Group(*lines), title="[bold]Status[/bold]", border_style="blue")


def render_navigation_panel() -> Panel:
    """Footer hint for the recording screen."""
    from src.cli.components.footer import render_footer
    return render_footer(
        [("Space", "Pause", "cyan")],
        border=True,
    )

