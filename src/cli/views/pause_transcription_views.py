"""
src/cli/views/pause_transcription_views.py

Pure render functions for the pause transcription screen.
No lifecycle, no Live, no console — data in, Rich renderable out.

Per CLI_ARCHITECTURE.MD: Views are stateless and data-driven.

Exported:
  PAUSE_MENU_ITEMS        List[Tuple[str, str]]  constant shared with the screen
  render_pause_status()   → Panel                status bar
  render_pause_transcript()→ Panel               transcript pane
"""
from __future__ import annotations

from typing import List, Tuple

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from src.cli.components.footer import render_footer

# ── Menu items ─────────────────────────────────────────────────────────────────

# Each item: (label, action_id, parent_action_id | None)
# Items with a parent_id are children and only shown when parent is expanded.
PAUSE_MENU_ITEMS: List[Tuple[str, str, str | None]] = [
    ("Edit",                 "edit",            None),
    ("Resume",               "resume",          None),
    ("AI",                   "ai",              None),      # parent — toggles expand
    ("Enhance",              "enhance",         "ai"),     # child
    ("Enhance with prompt",  "enhance_prompt",  "ai"),     # child
    ("Save",                 "save",            None),
    ("Cancel",               "discard",         None),
]

# Set of action_ids that are parents (computed once)
_PARENT_IDS: set[str] = {item[1] for item in PAUSE_MENU_ITEMS if item[2] is None
                          and any(c[2] == item[1] for c in PAUSE_MENU_ITEMS)}


# ── Render functions ───────────────────────────────────────────────────────────

def render_pause_status(time_str: str, words: int, tokens: int) -> Panel:
    """Status bar: pause indicator, elapsed time, word and token counts.

    Returns a Rich Panel — same style as render_recording_status() but yellow.
    """
    info = Text()
    info.append("⏸  PAUSED", style="bold yellow")
    info.append("  │  ", style="dim")
    info.append("Time: ",         style="dim cyan")
    info.append(time_str,          style="cyan")
    info.append("  │  ", style="dim")
    info.append("Words: ",        style="dim cyan")
    info.append(str(words),        style="cyan")
    info.append("  │  ", style="dim")
    info.append("Tokens (est): ", style="dim cyan")
    info.append(f"~{tokens}",      style="cyan")
    return Panel(info, border_style="dim", title="[bold yellow]Paused[/bold yellow]")


def render_pause_menu(
    visible_items: List[Tuple[str, str, str | None]],
    selected_idx: int,
    has_focus: bool = True,
    expanded_ids: set | None = None,
) -> Panel:
    """Radio-button style menu with optional inline sub-menus.

    visible_items — pre-filtered list (Screen hides children of collapsed parents).
    expanded_ids  — set of parent action_ids currently open (for ▼/▶ arrow).
    """
    if expanded_ids is None:
        expanded_ids = set()

    items_text = []
    for i, (label, action_id, parent_id) in enumerate(visible_items):
        is_selected = i == selected_idx
        is_child    = parent_id is not None
        is_parent   = action_id in _PARENT_IDS

        radio = "●" if is_selected else "○"
        indent = "    " if is_child else " "

        if is_parent:
            display = label   # no expand/collapse arrow — the children appear inline
        else:
            display = label

        if is_selected and has_focus:
            style = "bold green"
        elif is_child:
            style = "cyan" if not is_selected else "bold green"
        else:
            style = "white"

        items_text.append(Text(f"{indent}{radio} {display}", style=style))

    return Panel(
        Group(*items_text),
        title="[bold]Actions[/bold]",
        border_style="dim",
    )


def render_pause_transcript_body(text: str) -> "Markdown | Text":
    """Return the Rich renderable body for the transcript/preview panel.

    No Panel wrapper — the Textual VerticalScroll container provides the border.
    """
    if text and text.strip():
        return Markdown(text)
    return Text("No transcript yet.", style="dim italic")


def pause_transcript_title(title: str, expanded: bool, has_focus: bool) -> str:
    """Return the markup string to use as VerticalScroll.border_title."""
    icon  = "▼" if expanded else "▶"
    color = "green" if has_focus else "dim"
    return f"[bold {color}]{icon} {title}[/bold {color}]"


def render_pause_footer(mode: str, focus_zone: str = "menu") -> Panel:
    """Context-sensitive footer with mnemonic keys."""
    if mode == "edit":
        actions: list = [
            ("Ctrl+S",     "Save edit", "green"),
            ("Esc",        "Cancel",    "yellow"),
        ]
    elif mode == "enhance_prompt":
        actions = [
            ("Ctrl+R", "Run AI",   "cyan"),
            ("Ctrl+A", "Accept",   "green"),
            ("Esc",    "Cancel",   "yellow"),
        ]
    else:
        actions = [
            ("Enter",   "Select",   "green"),
            ("▲/▼",     "Navigate", "dim"),
            ("Esc",     "Resume",   "cyan"),
        ]

    return render_footer(
        actions=actions,
        border=True,
        border_style="dim",
    )


def render_pause_flex() -> Panel:
    """Empty flexible panel (Col 2 of Row 3)."""
    return Panel(
        Text("(No suggested items for this session yet)", style="dim italic"),
        title="[bold]Suggestions[/bold]",
        border_style="dim",
    )
