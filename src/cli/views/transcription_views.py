"""
LiveTranscriptionView — Rich TUI component for real-time transcription display.

Extracted from src/cli/commands/live_transcription.py.
Pure presentation: receives data, renders panels. No async I/O, no DB calls.
"""
from __future__ import annotations

import time
from typing import List

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


class LiveTranscriptionView:
    """
    Manages the Live TUI display during an active transcription session.

    Usage::

        view = LiveTranscriptionView(console)
        view.start()
        view.update(transcript_words=["hello", "world"], partial="how are")
        view.stop()
    """

    def __init__(self, console: Console, initial_duration: float = 0.0):
        self._console = console
        self._initial_duration = initial_duration
        self._start_time = time.time()
        self._full_transcript: List[str] = []
        self._current_partial: str = ""
        self._live = Live(
            console=self._console,
            refresh_per_second=10,
            transient=False,
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        self._live.start()
        self._render()

    def stop(self) -> None:
        self._live.stop()

    # ── Data interface ─────────────────────────────────────────────────────

    def append_final(self, text: str) -> None:
        self._full_transcript.append(text)
        self._current_partial = ""
        self._render()

    def set_partial(self, text: str) -> None:
        self._current_partial = text
        self._render()

    @property
    def full_transcript(self) -> List[str]:
        return list(self._full_transcript)

    @property
    def elapsed_seconds(self) -> float:
        return self._initial_duration + (time.time() - self._start_time)

    # ── Rendering ──────────────────────────────────────────────────────────

    def _render(self) -> None:
        elapsed = self.elapsed_seconds
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        full_text = " ".join(self._full_transcript)
        words = len(full_text.split()) if full_text.strip() else 0
        tokens = int(words * 1.3)

        # Blinking recording indicator
        is_blink_on = int(time.time() * 2) % 2 == 0
        rec_icon = "●" if is_blink_on else "○"
        rec_style = "bold red" if is_blink_on else "dim red"

        info_text = Text.from_markup(
            f"[{rec_style}]{rec_icon}[/{rec_style}] [bold red]RECORDING[/bold red] | "
            f"[cyan]Time:[/cyan] {time_str} | "
            f"[cyan]Words:[/cyan] {words} | "
            f"[cyan]Tokens (est):[/cyan] ~{tokens}"
        )
        info_panel = Panel(info_text, border_style="blue", title="[bold]Status[/bold]")

        # Show last ~100 words to prevent vertical growth
        display_words = full_text.split()[-100:]
        display_text = " ".join(display_words)

        trans_text = Text()
        if display_words and len(full_text.split()) > 100:
            trans_text.append("… ", style="dim")
        if display_text:
            trans_text.append(display_text + " ", style="green")
        if self._current_partial:
            trans_text.append(self._current_partial, style="dim")

        trans_panel = Panel(
            Align.left(trans_text, vertical="top"),
            border_style="green",
            title="[bold]Live Transcription (Latest)[/bold]",
            height=10,
        )

        footer_text = Text.from_markup(
            "[dim]Press[/dim] [bold cyan]Ctrl+C[/bold cyan] [dim]to pause or stop recording[/dim]"
        )
        footer_panel = Panel(Align.center(footer_text), border_style="dim")

        self._live.update(Group(info_panel, trans_panel, footer_panel))
