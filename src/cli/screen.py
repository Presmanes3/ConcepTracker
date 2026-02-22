"""
Unified TUI screen runner.

Every interactive CLI screen is an AppScreen subclass.
The single run_screen() function owns the Live context, the input loop,
and all transitions — so each screen only needs to describe:

  1. build_layout()   — structure, called ONCE
  2. refresh_zones()  — fill content in-place, called on each change
  3. handle_key()     — react to input, return a ScreenSignal

ScreenSignal contract
---------------------
None                    No state change; skip refresh.
SCREEN_EXIT             Close the current screen and return to caller.
AppScreen instance      Transition to that screen inside the same Live session.
("suspend", callable)   Stop Live, run callable() (e.g. questionary), restart Live.
                        The callable's return value is re-dispatched as a new signal.

Usage
-----
    from src.cli.screen import AppScreen, SCREEN_EXIT, run_screen

    class MyScreen(AppScreen):
        def build_layout(self):
            layout = Layout()
            layout.split_column(Layout(name="body"), Layout(name="footer", size=1))
            return layout

        def refresh_zones(self):
            self._layout["body"].update(Panel("Hello"))
            self._layout["footer"].update(Text("q: quit"))

        def handle_key(self, kind, key):
            if kind == "char" and key in (b"q", b"\\x1b"):
                return SCREEN_EXIT
            return None

    run_screen(MyScreen())
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Tuple, Union

from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.live import Live

from src.cli._input import _getch_with_timeout

console = Console()

# Sentinel — return from handle_key() to exit the current screen
SCREEN_EXIT = "exit"

# Type alias for screen signals
ScreenSignal = Union[
    None,                                    # no change
    bool,                                    # True = refresh, False = no-op
    str,                                     # SCREEN_EXIT = "exit"
    "AppScreen",                             # transition to another screen
    Tuple[str, Callable],                    # ("suspend", fn)
]


class AppScreen(ABC):
    """
    Base class for all interactive TUI screens.

    Subclass this, implement three methods, then pass an instance to run_screen().
    The Layout instance is stored on self._layout after run_screen() calls build_layout().

    Set ``alternate_screen = True`` on a subclass to open it in an alternate terminal
    buffer (like vim/less) — the previous terminal content is preserved and restored
    when the screen exits.
    """

    _layout: Optional[RenderableType] = None
    alternate_screen: bool = False  # override to True for full-page screens

    @abstractmethod
    def build_layout(self) -> RenderableType:
        """
        Construct and return the initial renderable (e.g. Layout, Group, Table).
        Called ONCE by run_screen(). The result is stored on self._layout.
        """

    @abstractmethod
    def refresh_zones(self) -> None:
        """
        Update the renderable in-place.
        For Layout, call self._layout["name"].update(renderable).
        For other types, you might need to mutate them or just rely on Live.update()
        if you change run_screen to call Live.update(self.render()).
        """

    @abstractmethod
    def handle_key(self, kind: Optional[str], key: Optional[bytes]) -> ScreenSignal:
        """
        Process one keypress. Return a ScreenSignal:
          None                  — no visible change (skip refresh)
          SCREEN_EXIT           — exit this screen
          AppScreen instance    — transition to a new screen
          ("suspend", callable) — suspend Live, run callable(), re-dispatch result
        """


def _dbg(msg: str) -> None:
    """Append a debug line to /tmp/ct_screen_debug.log."""
    import datetime
    with open("ct_screen_debug.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {msg}\n")


def run_screen(screen: AppScreen) -> None:
    """
    Run an AppScreen as a Live block.

    If ``screen.alternate_screen`` is True, opens in an alternate terminal buffer
    (like vim/less): the terminal is cleared on entry and the previous content is
    fully restored on exit — so ls/find output comes back intact after Back.

    Owns the full event loop:
      - Builds the Layout once via screen.build_layout()
      - Populates content via screen.refresh_zones()
      - Passes keypresses to screen.handle_key()
      - Handles all ScreenSignals (exit, transition, suspend)
      - Detects terminal resize and refreshes automatically
    """
    _dbg(f"run_screen called: class={screen.__class__.__name__} alternate_screen={screen.alternate_screen}")
    _dbg(f"  console.is_terminal={console.is_terminal}  console.size={console.size}")

    screen._layout = screen.build_layout()
    screen.refresh_zones()

    _dbg(f"  opening Live(screen={screen.alternate_screen}) ...")
    with Live(
        screen._layout,
        console=console,
        auto_refresh=False,
        screen=screen.alternate_screen,
    ) as live:
        _dbg(f"  Live started  is_alt={getattr(live, '_alt_screen', '?')}")
        last_size = console.size
        while True:
            # ── Input wait (inner loop) ───────────────────────────────────
            while True:
                kind, key = _getch_with_timeout(0.1)
                if kind is not None:
                    break
                # Resize detection
                if console.size != last_size:
                    last_size = console.size
                    screen.refresh_zones()
                    live.refresh()

            # ── Dispatch keypress ─────────────────────────────────────────
            signal = screen.handle_key(kind, key)
            _process_signal(signal, screen, live)

            if not getattr(screen, "_running", True):
                break


def _process_signal(signal: ScreenSignal, screen: AppScreen, live: Live) -> None:
    """
    Recursively process a ScreenSignal, updating layout and live display.
    """
    if signal is None:
        return  # No change, no refresh

    if signal == SCREEN_EXIT:
        screen._running = False  # type: ignore[attr-defined]
        return

    if isinstance(signal, AppScreen):
        # Transition: stop current Live, run new screen, come back
        live.stop()
        run_screen(signal)
        live.start()
        screen.refresh_zones()
        live.refresh()
        return

    if isinstance(signal, tuple) and len(signal) == 2 and signal[0] == "suspend":
        _, fn = signal
        live.stop()
        result = fn()
        live.start()
        # Re-dispatch the callable's return value
        _process_signal(result, screen, live)
        return

    # Default: something changed — refresh zones in-place, then repaint.
    # Layout zones are mutated in-place by refresh_zones(), so live.update()
    # is never needed — calling it replaces the root renderable and forces
    # a full terminal repaint on every keypress (the blink/scroll bug).
    _dbg(f"  _process_signal: refresh — signal={signal!r} screen={screen.__class__.__name__}")
    screen.refresh_zones()
    live.refresh()
