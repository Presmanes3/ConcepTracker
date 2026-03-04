"""
Unified TUI screen runner powered by Textual.

Every interactive CLI screen is an AppScreen subclass.
The single run_screen() function starts a Textual App and mounts the screen.

ScreenSignal contract 
---------------------
None                    No state change.
SCREEN_EXIT             Close the current screen and return to caller.
AppScreen instance      Transition to that screen inside the same session.
("suspend", callable)   Suspend TUI, run callable() (e.g. questionary), restart.
                        The callable's return value is re-dispatched as a new signal.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, Optional, Tuple, Union

from rich.console import Console, RenderableType
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Header, Footer

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


from textual.reactive import reactive

from textual.binding import Binding

class AppScreen(Screen):
    """
    Base class for all interactive TUI screens, built on Textual.
    """

    alternate_screen: bool = False  # Textual handles this at the App level
    _layout: Optional[RenderableType] = None
    result: Any = None
    
    # We can use a reactive content attribute for simple screens
    # and override compose() for more complex ones.
    content: reactive[Optional[RenderableType]] = reactive(None)

    BINDINGS = [
        Binding("escape", "back_screen", "Back", priority=True, show=False),
    ]

    async def action_quit_screen(self) -> None:
        """Ctrl+C handler — called by the App-level binding to exit cleanly."""
        if len(self.app.screen_stack) > 2:
            self.dismiss(self.result)
        else:
            self.app.exit(result=self.result)

    async def action_back_screen(self) -> None:
        """Escape usually acts as back/exit."""
        await self.process_signal(SCREEN_EXIT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        """
        By default, yield a single container that updates when 'content' changes.
        """
        yield Static(id="main_content")

    def watch_content(self, content: Optional[RenderableType]) -> None:
        """Update the UI whenever the layout content changes."""
        if content is not None:
            # Only try to update #main_content if it exists
            try:
                target = self.query_one("#main_content", Static)
                target.update(content)
            except Exception:
                pass

    def build_layout(self) -> Optional[RenderableType]:
        """Original AppScreen method: override this to return a Rich renderable."""
        return None

    def refresh_zones(self) -> None:
        """Original AppScreen method: override this to update the layout."""
        pass

    def on_mount(self) -> None:
        """Called when the screen is active."""
        # Execute custom logic to populate data
        self.refresh_zones()
        
        # Determine initial content
        initial_content = self._layout if self._layout else self.build_layout()
        
        # Assign to content which triggers watch_content
        self.content = initial_content
        
        # Only try to force update if #main_content exists (simple screens)
        if self.content is not None:
            try:
                # Check if we are using the default compose (with #main_content)
                self.query_one("#main_content", Static)
                # Textual's call_after_refresh ensures the query happens after compose is finish
                self.app.call_after_refresh(lambda: self.query_one("#main_content", Static).update(self.content or ""))
            except Exception:
                # Complex screens (like Pager) don't have #main_content, they have their own widgets
                pass

    def on_show(self) -> None:
        """Called when the screen is shown (initial mount or after push_screen/pop)."""
        # Ensure zones are refreshed when returning to screen
        self.refresh_zones()
        latest_layout = self._layout if self._layout else self.build_layout()
        if latest_layout:
            self.content = latest_layout

    async def on_key(self, event: Any) -> None:
        """
        Bridge Textual keys to handle_action (legacy support).
        Native BINDINGS are handled by Textual before reaching this.
        """
        # If the key is associated with a Textual binding on this screen or app,
        # do not forward it to handle_action to avoid double-handling.
        screen_bindings = getattr(self, "BINDINGS", []) or []
        app_bindings = getattr(self.app, "BINDINGS", []) or []
        if any(binding.key == event.key for binding in screen_bindings) or any(
            binding.key == event.key for binding in app_bindings
        ):
            return

        signal = self.handle_action(event.key)
        if signal:
            await self.process_signal(signal)

    def handle_action(self, key: str) -> ScreenSignal:
        """DEPRECATED: Use BINDINGS and action_* methods instead."""
        return None

    async def process_signal(self, signal: ScreenSignal) -> None:
        """Recursively process the signal."""
        if signal is None:
            return

        if signal == SCREEN_EXIT:
            # Use Textual's dismiss(result) so the callback registered in
            # push_screen(..., callback=fn) receives the result correctly.
            # app.pop_screen() does NOT pass the result to the callback.
            if len(self.app.screen_stack) > 2:
                self.dismiss(self.result)
            else:
                self.app.exit(result=self.result)
            return

        if isinstance(signal, AppScreen):
            # Push the child screen; when it calls dismiss() (Back), return to this screen.
            # We call self.on_show manually in the callback because Textual's 
            # pop_screen don't always trigger Screen.on_show in all versions/setups.
            def _handle_back(result):
                self.on_show()
            
            self.app.push_screen(signal, callback=_handle_back)
            return

        if isinstance(signal, tuple) and signal[0] == "suspend":
            fn = signal[1]
            # Suspend Textual, run fn, resume
            with self.app.suspend():
                result = fn()
            await self.process_signal(result)
            return

        # Default: refresh by updating the reactive 'content'
        self.refresh_zones()
        self.content = self._layout if self._layout else self.build_layout()


class TextualBridgeApp(App):
    """A minimal App to run a single AppScreen."""

    BINDINGS = [
        # App-level ctrl+c: highest priority in Textual's event hierarchy.
        # This fires before any focused widget (including TextArea) can capture it.
        Binding("ctrl+c", "app_quit", "Quit", priority=True, show=False),
    ]

    def __init__(self, screen: AppScreen):
        super().__init__()
        self.root_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.root_screen)

    async def action_app_quit(self) -> None:
        """Ctrl+C at the App level always exits cleanly."""
        screen = self.screen
        if isinstance(screen, AppScreen):
            result = screen.action_quit_screen()
            if inspect.isawaitable(result):
                await result
        else:
            self.exit()


def run_screen(screen: AppScreen) -> Any:
    """Run an AppScreen using Textual."""
    app = TextualBridgeApp(screen)
    return app.run()
