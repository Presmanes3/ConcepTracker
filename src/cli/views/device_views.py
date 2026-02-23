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
) -> Panel:
    """
    Render a navigable table of audio input devices inside a Panel.

    Columns: cursor arrow | ID | Device Name | Ch | ★ (saved)

    Args:
        devices:           List of device dicts from AudioDeviceService.
        current_device_id: ID persisted in settings.yaml — shown with ★.
        cursor:            Row index highlighted by the keyboard cursor.

    Returns:
        A Rich Panel containing the device table.
    """
    table = Table(show_header=True, header_style="bold", expand=True, box=None, padding=(0, 1))
    table.add_column("",       justify="center", width=2)   # cursor arrow
    table.add_column("ID",     justify="right",  width=4,  style="dim")
    table.add_column("Device",               ratio=4,  style="cyan")
    table.add_column("Ch",     justify="right",  width=4,  style="dim")
    table.add_column("",       justify="center", width=3)   # saved ★

    for i, device in enumerate(devices):
        is_cursor = (i == cursor)
        is_saved  = (device["id"] == current_device_id)

        arrow = "[bold cyan]▶[/bold cyan]" if is_cursor else " "
        star  = "[yellow]★[/yellow]"        if is_saved  else " "
        style = "bold reverse" if is_cursor else ""

        name = device["name"]
        if device.get("default"):
            name += "  [dim italic](system default)[/dim italic]"

        table.add_row(
            arrow,
            str(device["id"]),
            name,
            str(device["channels"]),
            star,
            style=style,
        )

    count = f"[dim]{len(devices)} device{'s' if len(devices) != 1 else ''}[/dim]"
    return Panel(
        table,
        title=f"[bold]Audio Input Devices[/bold]  {count}",
        border_style="blue",
        expand=True,
    )


def render_device_nav_panel(status_msg: Optional[str] = None) -> Panel:
    """
    Render the navigation-hints footer below the device table.

    Args:
        status_msg: Optional status line (e.g. "✔ Headset Mic selected").
    """
    from src.cli.components.footer import render_footer

    actions = [
        ("↑ / k", "Up",     "cyan"),
        ("↓ / j", "Down",   "cyan"),
        ("Enter",  "Select", "green"),
        ("Esc",    "Cancel", "red"),
    ]
    return render_footer(
        actions,
        status_msg=status_msg,
        border=True,
        border_style="dim white",
    )  # type: ignore[return-value]

