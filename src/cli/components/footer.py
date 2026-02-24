"""
src/cli/components/footer.py

Reusable navigation footer component for all screens.
Provides a consistent look and feel across the CLI.
"""
from __future__ import annotations

from typing import List, Tuple, Optional, Union
from rich.text import Text
from rich.panel import Panel

def render_footer(
    actions: List[Tuple[str, str, str]],  # (key_label, action_label, color)
    page_info: Optional[Tuple[int, int]] = None,  # (current, total)
    border: bool = True,
    border_style: str = "dim",
    status_msg: Optional[str] = None,
) -> Union[Panel, Text]:
    """
    Renders a consistent footer with key-action pairs and an optional status message.
    
    Example actions: [("▲/▼", "navigate", "yellow"), ("[Space]", "select", "magenta")]
    """
    t = Text(justify="center")
    
    if page_info:
        curr, total = page_info
        t.append(f"  Page {curr + 1} / {total}  ", style="bold white")
        t.append("  ")

    for i, (key, label, color) in enumerate(actions):
        if i > 0 or page_info:
            t.append("  ")
        
        # Consistent style: [Key] in bold, Label in normal
        key_styled = key if (key.startswith("[") or "/" in key) else f"[{key}]"
        
        t.append(key_styled, style=f"bold {color}")
        t.append(f" {label}", style=color)

    content: Union[Text, "RichGroup"] = t
    if status_msg:
        from rich.console import Group as RichGroup
        from rich.align import Align
        # Colour semantics:
        #   ✔  explicit success  → green
        #   ✗ / ✘ / Error       → red
        #   anything else       → dim (neutral state labels like PAUSED, RECORDING)
        if status_msg.startswith(("✔",)):
            status_style = "bold green"
        elif status_msg.startswith(("✗", "✘")) or "error" in status_msg.lower():
            status_style = "bold red"
        else:
            status_style = "dim white"
        status_line = Text(status_msg, justify="center", style=status_style)
        content = RichGroup(t, Align.center(status_line))

    if border:
        return Panel(content, border_style=border_style, padding=(0, 1))
    return t
