from typing import List, Dict, Any, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from src.cli.pager import _getch_with_timeout, _is_up, _is_down, _is_select, _is_quit

console = Console()

def select_audio_device_ui(devices: List[Dict[str, Any]], current_device_id: Optional[int] = None) -> Optional[int]:
    """
    Interactive UI for selecting an audio input device.
    """
    if not devices:
        console.print("[red]No input devices found.[/red]")
        return None

    # Find the index of the currently configured device, or default to 0
    cursor_index = 0
    if current_device_id is not None:
        for i, d in enumerate(devices):
            if d["id"] == current_device_id:
                cursor_index = i
                break

    def render_ui() -> Group:
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Sel", justify="center", width=4)
        table.add_column("ID", justify="right", width=4)
        table.add_column("Device Name", style="cyan")
        table.add_column("Channels", justify="right", width=10)

        for i, device in enumerate(devices):
            is_cursor = (i == cursor_index)
            
            # Cursor indicator
            sel_text = "[bold green]>[/bold green]" if is_cursor else " "
            
            # Row styling
            style = "reverse" if is_cursor else ""
            
            # Device name with default indicator
            name = device["name"]
            if device.get("default"):
                name += " [dim](System Default)[/dim]"
                
            if device["id"] == current_device_id:
                name += " [bold yellow](Current)[/bold yellow]"

            table.add_row(
                sel_text,
                str(device["id"]),
                name,
                str(device["channels"]),
                style=style
            )

        instructions = Text(
            "↑/↓: Move | Enter: Select | Esc/q: Cancel",
            style="dim italic",
            justify="center"
        )

        return Group(
            Panel(table, title="[bold]Select Audio Input Device[/bold]", border_style="blue"),
            instructions
        )

    with Live(render_ui(), console=console, refresh_per_second=10, transient=True) as live:
        while True:
            ktype, kbytes = _getch_with_timeout(0.1)
            if ktype is None:
                continue

            if _is_quit(ktype, kbytes):
                return None

            if _is_up(ktype, kbytes):
                cursor_index = max(0, cursor_index - 1)
                live.update(render_ui())
            elif _is_down(ktype, kbytes):
                cursor_index = min(len(devices) - 1, cursor_index + 1)
                live.update(render_ui())
            elif _is_select(ktype, kbytes):
                return devices[cursor_index]["id"]
