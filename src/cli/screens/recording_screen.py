"""
src/cli/screens/recording_screen.py

RecordingScreen — Textual AppScreen for an active transcription session.
Driven by async audio events (append_final / set_partial).

Layout (2 columns + footer):
  ┌────────────────────────────────────┬──────────────┐
  │  ● RECORDING  00:42  Words: 34     │  ● RECORDING │
  ├────────────────────────────────────│              │
  │  Transcript text…                  │  Space:Pause │
  │  partial▌                          │              │
  └────────────────────────────────────┴──────────────┘
  │  [Space] Pause                                     │

Space / p / Ctrl+C → push PauseTranscriptionScreen in the SAME Textual session.
Audio pipeline keeps running while the pause menu is visible.
"""
from __future__ import annotations

import time
from typing import List

from rich.console import Console
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static

from src.cli.screen import AppScreen, ScreenSignal
from src.cli.views.transcription_views import (
    render_navigation_panel,
    render_recording_status,
    render_transcription_panel,
)


class RecordingScreen(AppScreen):
    """
    Live transcription screen with a lateral actions panel.

    The async audio pipeline drives the display via ``append_final`` /
    ``set_partial``.  The user can act without Ctrl+C:
      p / Space  → Pause (exit → interactor shows pause menu)
      s          → Stop & Save (exit → interactor saves directly)
      d          → Discard (exit → interactor discards without prompting)
      Ctrl+C     → same as Pause (default exit)
    """

    DEFAULT_CSS = """
    RecordingScreen {
        layout: vertical;
    }
    #recording_zone {
        height: auto;
    }
    #transcription_zone {
        height: 1fr;
    }
    #navigation_zone {
        height: auto;
        dock: bottom;
    }
    """

    # ── Reactive state ───────────────────────────────────────────────────────
    elapsed_seconds: reactive[float]     = reactive(0.0)
    full_transcript: reactive[List[str]] = reactive([])
    current_partial: reactive[str]       = reactive("")
    is_blink_on:     reactive[bool]      = reactive(True)

    def __init__(self, console: Console, initial_duration: float = 0.0) -> None:
        super().__init__()
        self._initial_duration = initial_duration
        self._start_time       = time.time()
        self.result            = "pause"     # default: exit → show pause menu
        self._elapsed_timer    = None
        self._blink_timer      = None
        self._is_paused        = False       # True while pause overlay is on top
        self._stream_dead      = False       # True when AWS stream timed out during pause

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(id="recording_zone")
        yield Static(id="transcription_zone")
        yield Static(id="navigation_zone")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        super().on_mount()
        self._elapsed_timer = self.set_interval(1.0, self._tick_elapsed)
        self._blink_timer   = self.set_interval(0.5, self._tick_blink)
        self._render_status()
        self._render_transcript()
        self._render_nav()

    # ── Timers ────────────────────────────────────────────────────────────────

    def _tick_elapsed(self) -> None:
        self.elapsed_seconds = self._initial_duration + (time.time() - self._start_time)

    def _tick_blink(self) -> None:
        self.is_blink_on = not self.is_blink_on

    # ── Reactive watchers ─────────────────────────────────────────────────────

    def watch_elapsed_seconds(self, _: float) -> None:
        if self.is_mounted and not self._is_paused:
            self._render_status()

    def watch_is_blink_on(self, _: bool) -> None:
        if self.is_mounted and not self._is_paused:
            self._render_status()

    def watch_full_transcript(self, _: List[str]) -> None:
        if self.is_mounted and not self._is_paused:
            self._render_transcript()

    def watch_current_partial(self, _: str) -> None:
        if self.is_mounted and not self._is_paused:
            self._render_transcript()

    # ── Rendering helpers ─────────────────────────────────────────────────────

    def _render_status(self) -> None:
        try:
            mins, secs = divmod(int(self.elapsed_seconds), 60)
            time_str   = f"{mins:02d}:{secs:02d}"
            full_text  = " ".join(self.full_transcript)
            words      = len(full_text.split()) if full_text.strip() else 0
            tokens     = int(words * 1.3)
            icon       = "●" if self.is_blink_on else "○"
            style      = "bold red" if self.is_blink_on else "dim red"
            self.query_one("#recording_zone", Static).update(
                render_recording_status(icon, style, time_str, words, tokens)
            )
        except Exception:
            pass

    def _render_transcript(self) -> None:
        try:
            self.query_one("#transcription_zone", Static).update(
                render_transcription_panel(self.full_transcript, self.current_partial)
            )
        except Exception:
            pass

    def _render_nav(self) -> None:
        try:
            self.query_one("#navigation_zone", Static).update(render_navigation_panel())
        except Exception:
            pass

    # ── AppScreen interface ───────────────────────────────────────────────────

    BINDINGS = [
        Binding("ctrl+c", "discard_session", "Discard", priority=True, show=False),
        Binding("ctrl+x", "discard_session", "Discard", priority=True, show=False),
    ]

    async def action_discard_session(self) -> None:
        """Ctrl+C / Ctrl+X → discard immediately."""
        self.result = "discard"
        self.app.exit(result="discard")

    def build_layout(self) -> None:
        return None

    def refresh_zones(self) -> None:
        pass

    def handle_action(self, key: str) -> ScreenSignal:
        if key in ("p", "space", "escape"):
            self._pause()
            return None
        if key == "s":
            self.result = "save"
            self.app.exit(result="save")
            return None
        return None

    # ── Pause flow ────────────────────────────────────────────────────────────

    def _pause(self) -> None:
        """Push PauseTranscriptionScreen in the same Textual session.

        The audio pipeline keeps running while the pause screen is visible.
        Timers are paused so the recording screen stops repainting underneath
        the pause overlay — this eliminates the compositor flash.
        When the pause screen is dismissed, ``_on_pause_done`` fires and
        the timers are resumed.
        """
        from src.cli.screens.pause_transcription_screen import PauseTranscriptionScreen

        # Stop the recording screen's timers while the pause overlay is shown.
        # Without this, _tick_blink (0.5s) and _tick_elapsed (1s) keep firing,
        # calling Static.update() underneath the overlay which forces a full
        # compositor repaint — visible as a terminal-wide flash.
        if self._blink_timer:
            self._blink_timer.pause()
        if self._elapsed_timer:
            self._elapsed_timer.pause()
        self._is_paused = True

        full_text = " ".join(self.full_transcript)
        mins, secs = divmod(int(self.elapsed_seconds), 60)
        pause_screen = PauseTranscriptionScreen(
            full_text=full_text,
            time_str=f"{mins:02d}:{secs:02d}",
        )
        self.app.push_screen(pause_screen, callback=self._on_pause_done)

    def _on_pause_done(self, result: object) -> None:
        """Called when PauseTranscriptionScreen is dismissed."""
        # Resume the timers now that the pause overlay is gone.
        self._is_paused = False
        if self._blink_timer:
            self._blink_timer.resume()
        if self._elapsed_timer:
            self._elapsed_timer.resume()
        # Re-render once now to catch anything that arrived while paused.
        self._render_status()
        self._render_transcript()

        if result is None:
            result = ("resume", None)
        action, edited_text = result if isinstance(result, tuple) else (result, None)

        # Apply any inline edits
        if edited_text is not None:
            self.full_transcript = [edited_text]
            self.current_partial = ""

        if action == "resume":
            if self._stream_dead:
                # AWS stream timed out during pause — exit so the interactor
                # can open a fresh stream.  Transcript is preserved in state.
                self.result = "resume"
                self.app.exit(result="resume")
            else:
                return  # stream still alive — just continue recording

        # save / discard / enhance → exit the Textual app
        self.result = action
        self.app.exit(result=action)

    # ── Audio event interface (called by async pipeline) ─────────────────────

    def append_final(self, text: str) -> None:
        self.full_transcript = [*self.full_transcript, text]
        self.current_partial = ""

    def set_partial(self, text: str) -> None:
        self.current_partial = text

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def elapsed_total(self) -> float:
        return self.elapsed_seconds
