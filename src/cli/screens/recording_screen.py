"""
src/cli/screens/recording_screen.py

RecordingScreen — Textual AppScreen for an active transcription session.
Driven by async audio events (append_final / set_partial).

Layout (Strategy & Zone pattern):
  ┌────────────────────────────────────┐
  │  ● RECORDING  00:42  Words: 34     │  (ZONE_STATUS)
  ├─────────────┬──────────────────────┤
  │  Actions    │  Transcript text…    │  (ZONE_MENU | ZONE_CONTENT)
  │  ● Pause    │  partial▌            │
  │  ○ Save     │                      │
  └─────────────┴──────────────────────┘
  │  [Space] Pause                     │  (FOOTER)

Audio pipeline keeps running while the screen is managed.
"""
from __future__ import annotations

import time
from typing import List, Optional

from rich.console import Console, RenderableType, Group
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Static
from textual.containers import Horizontal

from src.cli.screen import AppScreen
from src.cli.screens.transcription_actions import TranscriptionAction
from src.cli.views.transcription_views import (
    render_navigation_panel,
    render_recording_status,
    render_transcription_panel,
)

# Which zone the cursor is on
_ZONE_STATUS = "status"
_ZONE_CONTENT = "content"
_ZONE_MENU = "menu"

class RecordingScreen(AppScreen):
    """
    Live transcription screen with a lateral actions panel and strategy pattern.
    """

    DEFAULT_CSS = """
    RecordingScreen {
        layout: vertical;
    }
    #top_row {
        height: auto;
        margin-bottom: 1;
    }
    #main_row {
        height: 1fr;
    }
    #menu_panel {
        width: 26;
        height: 100%;
    }
    #content_panel {
        width: 1fr;
        height: 100%;
        border: round #666666;
        padding: 0 1;
    }
    #footer_zone {
        height: auto;
        dock: bottom;
    }
    """

    # ── Reactive state ───────────────────────────────────────────────────────
    elapsed_seconds: reactive[float]     = reactive(0.0)
    full_transcript: reactive[List[str]] = reactive([])
    current_partial: reactive[str]       = reactive("")
    is_blink_on:     reactive[bool]      = reactive(True)
    focus_zone:      reactive[str]       = reactive(_ZONE_MENU)
    menu_index:      reactive[int]       = reactive(0)

    def __init__(self, console: Console, initial_duration: float = 0.0) -> None:
        super().__init__()
        self._initial_duration = initial_duration
        self._start_time       = time.time()
        self.result            = "pause"     # default: exit → show pause menu
        self._elapsed_timer       = None
        self._blink_timer         = None
        self._auto_pause_timer    = None        # one-shot timer for auto-pause
        self._auto_pause_seconds  = 0           # loaded from config in on_mount
        self._is_paused           = False       # True while pause overlay is on top
        self._stream_dead         = False       # True when AWS stream timed out during pause
        self._pause_interactor    = None        # PauseTranscriptionInteractor while paused
        self.actions: List[TranscriptionAction] = []
        self._active_action: Optional[TranscriptionAction] = None

    def set_actions(self, actions: List[TranscriptionAction]) -> None:
        """Register the ordered list of menu actions. Call after construction."""
        self.actions = actions

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(id="top_row")
        with Horizontal(id="main_row"):
            yield Static(id="menu_panel")
            yield Static(id="content_panel")
        yield Static(id="footer_zone")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        super().on_mount()
        self._elapsed_timer = self.set_interval(1.0, self._tick_elapsed)
        self._blink_timer   = self.set_interval(0.5, self._tick_blink)
        self._load_auto_pause()
        self.refresh_zones()

    def _load_auto_pause(self) -> None:
        """Read auto_pause_seconds from config and start the one-shot timer."""
        try:
            from src.cli.client.http_client import ConcepTrackerClient
            with ConcepTrackerClient() as client:
                config = client.get_config()
            ap = config.auto_pause_seconds
        except Exception:
            ap = 0
        self._auto_pause_seconds = ap or 0
        if self._auto_pause_seconds > 0:
            self._auto_pause_timer = self.set_timer(
                self._auto_pause_seconds, self._on_auto_pause
            )

    def _on_auto_pause(self) -> None:
        """Fired by the one-shot auto-pause timer — pause if still recording."""
        self._auto_pause_timer = None
        if not self._is_paused:
            self._pause()

    # ── Timers ────────────────────────────────────────────────────────────────

    def _tick_elapsed(self) -> None:
        self.elapsed_seconds = self._initial_duration + (time.time() - self._start_time)

    def _tick_blink(self) -> None:
        self.is_blink_on = not self.is_blink_on

    # ── Reactive watchers ─────────────────────────────────────────────────────

    def watch_elapsed_seconds(self, _: float) -> None:
        if self.is_mounted and not self._is_paused:
            self.refresh_zones()

    def watch_is_blink_on(self, _: bool) -> None:
        if self.is_mounted and not self._is_paused:
            self.refresh_zones()

    def watch_full_transcript(self, _: List[str]) -> None:
        if self.is_mounted and not self._is_paused:
            self.refresh_zones()

    def watch_current_partial(self, _: str) -> None:
        if self.is_mounted and not self._is_paused:
            self.refresh_zones()

    def watch_focus_zone(self, _: str) -> None:
        self.refresh_zones()

    def watch_menu_index(self, _: int) -> None:
        self.refresh_zones()

    # ── Rendering helpers ─────────────────────────────────────────────────────

    def refresh_zones(self) -> None:
        """Push Rich renderables into the individual Textual widgets."""
        try:
            self.query_one("#top_row", Static).update(self._render_status())
        except Exception: pass

        try:
            self.query_one("#menu_panel", Static).update(self._render_menu())
        except Exception: pass

        try:
            self.query_one("#content_panel", Static).update(self._render_transcript())
        except Exception: pass

        try:
            self.query_one("#footer_zone", Static).update(self._render_footer())
        except Exception: pass

    def _render_status(self) -> RenderableType:
        mins, secs = divmod(int(self.elapsed_seconds), 60)
        time_str   = f"{mins:02d}:{secs:02d}"
        full_text  = " ".join(self.full_transcript)
        words      = len(full_text.split()) if full_text.strip() else 0
        tokens     = int(words * 1.3)
        icon       = "●" if self.is_blink_on else "○"
        
        dot_style  = "bold red" if self.is_blink_on else "dim red"
        border     = "dim"

        # Using the existing view logic but wrapped in a Panel for the border
        content = render_recording_status(icon, dot_style, time_str, words, tokens)
        content.border_style = border
        return content

    def _render_menu(self) -> RenderableType:
        is_zone_focused = self.focus_zone == _ZONE_MENU
        items: list[Text] = []
        for i, action in enumerate(self.actions):
            is_selected = i == self.menu_index
            
            bullet = "●" if is_selected else "○"
            style = "bold green" if is_selected and is_zone_focused else "white"
            if not is_zone_focused and is_selected:
                style = "cyan"
            
            line = Text(f" {bullet} {action.label}", style=style)
            items.append(line)

        border = "green" if is_zone_focused else "dim"
        title = "[bold green]Actions[/bold green]" if is_zone_focused else "[bold dim]Actions[/bold dim]"
        return Panel(Group(*items), title=title, border_style=border)

    def _render_transcript(self) -> RenderableType:
        is_focused = self.focus_zone == _ZONE_CONTENT
        border = "green" if is_focused else "dim"
        
        # We wrap the existing view to add the border based on focus zone
        inner = render_transcription_panel(self.full_transcript, self.current_partial)
        inner.border_style = border
        return inner

    def _render_footer(self) -> RenderableType:
        return render_navigation_panel()

    # ── Key handling ──────────────────────────────────────────────────────────

    BINDINGS = [
        Binding("ctrl+c", "discard_session", "Discard", priority=True, show=False),
        Binding("ctrl+x", "discard_session", "Discard", priority=True, show=False),
        Binding("ctrl+left",  "nav_left",  "To Menu",    priority=True, show=False),
        Binding("ctrl+right", "nav_right", "To Content", priority=True, show=False),
        Binding("up",    "nav_up",   "Up",   show=False),
        Binding("down",  "nav_down", "Down", show=False),
        Binding("k",     "nav_up",   "Up",   show=False),
        Binding("j",     "nav_down", "Down", show=False),
        Binding("p",     "pause_action", "Pause", show=False),
        Binding("s",     "save_action",  "Save", show=False),
        Binding("space", "interact", "Interact", show=False),
        Binding("enter", "select",   "Select",   show=False),
    ]

    async def action_nav_up(self) -> None:
        if self.focus_zone == _ZONE_MENU:
            if self.menu_index > 0:
                self.menu_index -= 1
        else:
            self._focus_prev()

    async def action_nav_down(self) -> None:
        if self.focus_zone == _ZONE_MENU:
            if self.menu_index < len(self.actions) - 1:
                self.menu_index += 1
        else:
            self._focus_next()

    async def action_nav_left(self) -> None:
        if self.focus_zone == _ZONE_CONTENT:
            self.focus_zone = _ZONE_MENU

    async def action_nav_right(self) -> None:
        if self.focus_zone == _ZONE_MENU:
            self.focus_zone = _ZONE_CONTENT

    async def action_interact(self) -> None:
        if self.focus_zone == _ZONE_MENU:
            await self.action_select()
        else:
            self._pause()

    async def action_select(self) -> None:
        if self.focus_zone != _ZONE_MENU or not self.actions:
            return
        action = self.actions[self.menu_index]
        if action.disabled:
            return
        action.enter()

    async def action_discard_session(self) -> None:
        self.result = "discard"
        self.app.exit(result="discard")

    async def action_pause_action(self) -> None:
        self._pause()

    async def action_save_action(self) -> None:
        self.result = "save"
        self.app.exit(result="save")

    _FOCUS_ORDER = [_ZONE_MENU, _ZONE_CONTENT]

    def _focus_next(self) -> None:
        idx = self._FOCUS_ORDER.index(self.focus_zone)
        self.focus_zone = self._FOCUS_ORDER[(idx + 1) % len(self._FOCUS_ORDER)]

    def _focus_prev(self) -> None:
        idx = self._FOCUS_ORDER.index(self.focus_zone)
        self.focus_zone = self._FOCUS_ORDER[(idx - 1) % len(self._FOCUS_ORDER)]

    # ── Original logic (moved but preserved) ──────────────────────────────────

    def _pause(self) -> None:
        """Push PauseTranscriptionScreen via its Interactor."""
        from src.cli.interactors.pause_transcription_interactor import (
            PauseTranscriptionInteractor,
        )

        if self._auto_pause_timer:
            self._auto_pause_timer.stop()
            self._auto_pause_timer = None

        if self._blink_timer:
            self._blink_timer.pause()
        if self._elapsed_timer:
            self._elapsed_timer.pause()
        self._is_paused = True

        self._pause_interactor = PauseTranscriptionInteractor(
            full_transcript=list(self.full_transcript),
            elapsed_seconds=self.elapsed_seconds,
        )
        pause_screen = self._pause_interactor.build_screen()
        self.app.push_screen(pause_screen, callback=self._on_pause_done)

    def _on_pause_done(self, raw_result: object) -> None:
        self._is_paused = False
        if self._blink_timer:
            self._blink_timer.resume()
        if self._elapsed_timer:
            self._elapsed_timer.resume()
        
        self.refresh_zones()

        action, edited_text = self._pause_interactor.process_result(
            self.app, raw_result
        )
        self._pause_interactor = None

        if edited_text is not None:
            self.full_transcript = [edited_text]
            self.current_partial = ""

        if action == "resume":
            if self._stream_dead:
                self.result = "resume"
                self.app.exit(result="resume")
            else:
                if self.full_transcript:
                    self.full_transcript = [*self.full_transcript, "\n\n"]
                if self._auto_pause_seconds > 0:
                    self._auto_pause_timer = self.set_timer(
                        self._auto_pause_seconds, self._on_auto_pause
                    )
                return

        self.result = action
        self.app.exit(result=action)

    # ── Audio event interface ─────────────────────────────────────────────────

    def append_final(self, text: str) -> None:
        self.full_transcript = [*self.full_transcript, text]
        self.current_partial = ""

    def set_partial(self, text: str) -> None:
        self.current_partial = text
