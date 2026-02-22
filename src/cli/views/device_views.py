"""
src/cli/views/device_views.py

Pure rendering functions for audio device listings.
No console.print(), no DB calls, no service calls — data in, Rich renderable out.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def render_device_table(
    devices: List[Dict[str, Any]],
    current_device_id: Optional[int],
    cursor: int = 0,
    pending_id: Optional[int] = None,
) -> Panel:
    """
    Render a navigable table of audio input devices inside a Panel.

    Args:
        devices:           List of device dicts from AudioDeviceService.
        current_device_id: ID of the saved (settings.yaml) device — shown with ★.
        cursor:            Row index highlighted by the keyboard cursor.
        pending_id:        ID the user has Space-selected but not yet saved — shown with ●.
                           Defaults to current_device_id when not provided.

    Returns:
        A Rich Panel containing the device table.
    """
    if pending_id is None:
        pending_id = current_device_id

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("",       justify="center", width=3)   # cursor arrow
    table.add_column("Sel",    justify="center", width=5)   # pending selection
    table.add_column("Saved",  justify="center", width=7)   # persisted in settings
    table.add_column("ID",     justify="right",  width=4)
    table.add_column("Device Name", style="cyan", ratio=3)
    table.add_column("Max Channels", justify="right", width=14)

    for i, device in enumerate(devices):
        is_cursor  = (i == cursor)
        is_pending = (device["id"] == pending_id)
        is_saved   = (device["id"] == current_device_id)

        cursor_cell  = "[bold cyan]▶[/bold cyan]" if is_cursor else " "
        pending_cell = "[bold green]●[/bold green]" if is_pending else "[dim]○[/dim]"
        saved_cell   = "[bold yellow]★[/bold yellow]" if is_saved else "[dim] [/dim]"
        row_style    = "reverse" if is_cursor else ""

        name = device["name"]
        if device.get("default"):
            name += "  [dim](System Default)[/dim]"

        table.add_row(
            cursor_cell,
            pending_cell,
            saved_cell,
            str(device["id"]),
            name,
            str(device["channels"]),
            style=row_style,
        )

    title_suffix = (
        f"  [dim]({len(devices)} device{'s' if len(devices) != 1 else ''})[/dim]"
    )
    return Panel(
        table,
        title=f"[bold white]Audio Input Devices[/bold white]{title_suffix}",
        border_style="blue",
        expand=True,
    )


def render_device_nav_panel(status_msg: Optional[str] = None) -> Panel:
    """
    Render the navigation hints panel shown below the device table.

    Args:
        status_msg: Optional confirmation line shown after a save
                    (e.g. "✔ Saved: Headset Mic").

    Returns:
        A compact Rich Panel with keyboard shortcut hints.
    """
    hints = Text(justify="center")
    hints.append("↑ / k", style="bold cyan")
    hints.append("  Up    ", style="dim")
    hints.append("↓ / j", style="bold cyan")
    hints.append("  Down    ", style="dim")
    hints.append("Enter", style="bold green")
    hints.append("  Set as active device    ", style="dim")
    hints.append("q / Esc", style="bold red")
    hints.append("  Exit", style="dim")

    if status_msg:
        from rich.console import Group as RichGroup
        ok = status_msg.startswith("✔")
        status_line = Text(status_msg, justify="center", style="bold green" if ok else "bold red")
        content: object = RichGroup(hints, status_line)
        height = 4
    else:
        content = hints
        height = 3

    return Panel(
        content,  # type: ignore[arg-type]
        title="[dim]Navigation[/dim]",
        border_style="dim white",
        expand=True,
        height=height,
    )
