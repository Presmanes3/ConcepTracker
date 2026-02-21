from typing import Callable, Dict, List, Optional, Any
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.live import Live
from src.cli.pager import _getch_with_timeout, _is_up, _is_down, _is_select, _is_quit

console = Console()

class MenuAction:
    def __init__(self, label: str, callback: Callable[[], Any], needs_suspend: bool = False):
        self.label = label
        self.callback = callback
        self.needs_suspend = needs_suspend

class ColumnMenu:
    def __init__(self, title: str, header_renderable: Optional[RenderableType] = None):
        self.title = title
        self.header_renderable = header_renderable
        self.actions: List[MenuAction] = []
        self.selected_index = 0
        self.right_pane: Any = None
        self.focus = "menu" # "menu" or "right_pane"
        self.is_running = False

    def add_action(self, label: str, callback: Callable[[], Any], needs_suspend: bool = False):
        self.actions.append(MenuAction(label, callback, needs_suspend))

    def render(self) -> RenderableType:
        # Render the left menu
        menu_items = []
        for i, action in enumerate(self.actions):
            if self.focus == "menu":
                style = "bold white on blue" if i == self.selected_index else "white"
                prefix = "▶ " if i == self.selected_index else "  "
            else:
                style = "bold white on bright_black" if i == self.selected_index else "dim"
                prefix = "▶ " if i == self.selected_index else "  "
            menu_items.append(Text(f"{prefix}{action.label}", style=style))
        
        menu_panel = Panel(
            Group(*menu_items),
            title=f"[bold cyan]{self.title}[/bold cyan]",
            border_style="blue" if self.focus == "menu" else "dim",
            width=40
        )

        # Render the right content (if any)
        if self.right_pane:
            if hasattr(self.right_pane, "render"):
                right_content = self.right_pane.render()
            else:
                right_content = self.right_pane
        else:
            right_content = Panel(Text("Select an action from the menu.", style="dim"), border_style="dim")

        # Combine into columns
        columns = Columns([menu_panel, right_content], expand=True)

        # Add header if present
        if self.header_renderable:
            from rich.layout import Layout
            layout = Layout()
            layout.split_column(
                Layout(self.header_renderable, name="header"),
                Layout(columns, name="menu", size=max(10, len(self.actions) + 4))
            )
            return layout
        return columns

    def run(self):
        self.is_running = True
        with Live(self.render(), auto_refresh=False, screen=True) as live:
            while self.is_running:
                kind, key = _getch_with_timeout(0.1)
                if not kind:
                    continue

                if self.focus == "right_pane" and self.right_pane and hasattr(self.right_pane, "handle_key"):
                    res = self.right_pane.handle_key(kind, key)
                    if res == "done":
                        self.focus = "menu"
                else:
                    if _is_up(kind, key):
                        if self.selected_index > 0:
                            self.selected_index -= 1
                    elif _is_down(kind, key):
                        if self.selected_index < len(self.actions) - 1:
                            self.selected_index += 1
                    elif _is_select(kind, key):
                        action = self.actions[self.selected_index]

                        if action.needs_suspend:
                            # Stop Live, run the callback (which may use questionary),
                            # then restart Live in-place on the same screen buffer.
                            live.stop()
                            console.clear()
                            result = action.callback()
                            console.clear()
                            live.start()
                        else:
                            result = action.callback()

                        if hasattr(result, "render") and hasattr(result, "handle_key"):
                            self.right_pane = result
                            self.focus = "right_pane"
                        elif result == "exit":
                            self.is_running = False
                        elif result is not None:
                            self.right_pane = result
                            self.focus = "menu"
                    elif _is_quit(kind, key):
                        self.is_running = False

                if self.is_running:
                    live.update(self.render(), refresh=True)
