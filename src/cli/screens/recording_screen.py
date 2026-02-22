"""
src/cli/screens/recording_screen.py

RecordingScreen — owns the Rich Live display for an active transcription session.

NOT an AppScreen subclass: this screen is driven by async audio events
(append_final / set_partial), not by keyboard input.  The async pipeline
calls start() / stop() and pushes text updates; this class owns the
Layout + Live context and delegates all rendering to pure functions in
views/transcription_views.py.
"""
from __future__ import annotations

import time
from typing import List

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from src.cli.views.transcription_views import (
    render_navigation_panel,
    render_recording_status,
    render_transcription_panel,
)

# Navigation panel is static for every session — build once at class level
_NAV_PANEL = render_navigation_panel()


class RecordingScreen:
    """
    Manages the 3-zone Live layout during an active recording session.

    Zones:
      recording      (size=5)  — blinking indicator, time, word count
      transcription  (size=12) — live text + partial utterance
      navigation     (size=5)  — static hint (Ctrl+C to pause)
    """

    def __init__(self, console: Console, initial_duration: float = 0.0) -> None:
        self._console          = console
        self._initial_duration = initial_duration
        self._start_time       = time.time()
        self._full_transcript  : List[str] = []
        self._current_partial  : str       = ""
        self._layout           = self._make_layout()
        self._live             = Live(
            self._layout,
            console=self._console,
            refresh_per_second=10,
            transient=True,
        )

    # ── Layout factory ─────────────────────────────────────────────────────

    @staticmethod
    def _make_layout() -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="recording",     size=5),
            Layout(name="transcription", size=12),
            Layout(name="navigation",    size=5),
        )
        return layout

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        self._live.start()
        self._layout["navigation"].update(_NAV_PANEL)   # static — set once
        self._render()

    def stop(self) -> None:
        self._live.stop()

    # ── Audio event interface ──────────────────────────────────────────────

    def append_final(self, text: str) -> None:
        """Called by the async pipeline when AWS emits a final transcript segment."""
        self._full_transcript.append(text)
        self._current_partial = ""
        self._render()

    def set_partial(self, text: str) -> None:
        """Called by the async pipeline on every partial utterance update."""
        self._current_partial = text
        self._render()

    # ── Properties read by the async pipeline after stop() ────────────────

    @property
    def full_transcript(self) -> List[str]:
        return list(self._full_transcript)

    @property
    def elapsed_seconds(self) -> float:
        return self._initial_duration + (time.time() - self._start_time)

    # ── Internal render ────────────────────────────────────────────────────

    def _render(self) -> None:
        elapsed = self.elapsed_seconds
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        full_text = " ".join(self._full_transcript)
        words  = len(full_text.split()) if full_text.strip() else 0
        tokens = int(words * 1.3)

        is_blink_on = int(time.time() * 2) % 2 == 0
        rec_icon  = "●" if is_blink_on else "○"
        rec_style = "bold red" if is_blink_on else "dim red"

        self._layout["recording"].update(
            render_recording_status(rec_icon, rec_style, time_str, words, tokens)
        )
        self._layout["transcription"].update(
            render_transcription_panel(self._full_transcript, self._current_partial)
        )
