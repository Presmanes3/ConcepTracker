from __future__ import annotations
from typing import List, Dict, Any, Optional, Set, Callable
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.columns import Columns
from src.cli.pager import _getch_with_timeout, _is_up, _is_down, _is_select, _is_quit, _is_prev_page, _is_next_page

console = Console()


# ---------------------------------------------------------------------------
# TagPanel  – renders one collapsible section and owns its tag list
# ---------------------------------------------------------------------------

class TagPanel:
    def __init__(self, title: str, color: str, tags: List[Dict[str, Any]]):
        self.title    = title
        self.color    = color
        self.tags     = tags
        self.expanded = True

    @property
    def display_count(self) -> int:
        return sum(1 for t in self.tags if not t.get("is_action"))

    def render(
        self,
        focused: bool,
        cursor: int,        # tag-row index under cursor; -1 = header
        selected: Set[str],
        input_mode: bool,
        input_text: str,
        height: Optional[int] = None,
    ) -> Panel:
        icon    = "▼" if self.expanded else "▶"
        c       = self.color
        h_style = f"bold {c}" if (focused and cursor == -1) else c
        title   = f"[{h_style}]{icon} {self.title} ({self.display_count})[/{h_style}]"
        border  = "cyan" if focused else "dim"

        if not self.expanded:
            # Fixed height so collapsing never leaves ghost lines
            return Panel("", title=title, title_align="left",
                         border_style=border, height=height, padding=(0, 1))

        tbl = Table(box=None, show_header=False, padding=(0, 1))
        tbl.add_column("cb",   justify="center", width=3, no_wrap=True)
        tbl.add_column("tag",  style="bold white")
        tbl.add_column("info", style="dim")

        for j, item in enumerate(self.tags):
            row_style = "on bright_black" if (focused and j == cursor) else None

            if item.get("is_action"):
                if input_mode and focused and j == cursor:
                    tbl.add_row(
                        "✏️",
                        f"[yellow]{input_text}█[/yellow]",
                        "[dim]Enter → add   Esc → cancel[/dim]",
                        style=row_style,
                    )
                else:
                    tbl.add_row("➕", "[italic dim]+ Add new tag[/italic dim]", "",
                                style=row_style)
            else:
                sel = item["name"] in selected
                cb  = "[bold green]●[/bold green]" if sel else "[dim]○[/dim]"
                src = ""
                s   = item.get("source", "")
                if s == "AI+DB":
                    src = f"AI · {item['count']} similar"
                elif s == "DB":
                    src = f"{item['count']} similar"
                tbl.add_row(cb, item["name"], src, style=row_style)

        return Panel(tbl, title=title, title_align="left",
                     border_style=border, height=height, padding=(0, 1))


# ---------------------------------------------------------------------------
# TagSelectorUI  – orchestrates panels, owns the key-handling logic
# ---------------------------------------------------------------------------

class TagSelectorUI:
    def __init__(
        self,
        panels: List[TagPanel],
        initial_selected: Set[str],
        on_done: Optional[Callable[[List[str]], None]] = None,
    ):
        self.panels      = panels
        self.selected    = set(initial_selected)
        self.on_done     = on_done

        self.panel_focus = 0
        self.tag_focus   = -1   # -1 = panel header is focused
        self.input_mode  = False
        self.input_text  = ""

    # -- Rendering ------------------------------------------------------------

    def _preview(self) -> Panel:
        if self.selected:
            body = "  ".join(
                f"[bold green]#{t}[/bold green]" for t in sorted(self.selected)
            )
        else:
            body = "[dim]No tags selected yet[/dim]"
        return Panel(body, title="[bold]Selected[/bold]",
                     border_style="green", padding=(0, 1))

    def render(self) -> RenderableType:
        # Calculate max possible height to prevent UI jumping
        max_panel_height = 0
        for p in self.panels:
            p_max = max(len(p.tags) + 2, 3)
            if p_max > max_panel_height:
                max_panel_height = p_max
                
        panels = [
            p.render(
                focused    = (i == self.panel_focus),
                cursor     = self.tag_focus if i == self.panel_focus else -1,
                selected   = self.selected,
                input_mode = self.input_mode,
                input_text = self.input_text,
                height     = max_panel_height if p.expanded else 3,
            )
            for i, p in enumerate(self.panels)
        ]
        
        columns = Columns(panels, expand=True, equal=True)
        
        hint = Text(
            "\n↑↓ Navigate   ←→ Switch Category   Space / Enter  Toggle   q  Confirm   Esc  Cancel",
            style="dim", justify="center",
        )
        
        items = [columns, self._preview(), hint]
            
        selector = Group(*items)
        return Panel(selector, title="[bold magenta]Manage Tags[/bold magenta]", border_style="magenta")

    # -- Key handling ---------------------------------------------------------

    def handle_key(self, kind: str, key: bytes) -> Optional[str]:
        """Returns "done" when the user confirms, otherwise None."""
        if self.input_mode:
            return self._handle_input(kind, key)
        return self._handle_nav(kind, key)

    def _handle_input(self, kind, key):
        if kind == "char" and key in (b"\x03", b"\x1b"):  # Ctrl+C, Esc
            self.input_mode = False
            self.input_text = ""
        elif _is_select(kind, key):
            text = self.input_text.strip()
            if text:
                self.panels[0].tags.insert(-1, {
                    "name": text, "source": "Manual", "count": 0
                })
                self.selected.add(text)
            self.input_mode = False
            self.input_text = ""
        elif kind == "char":
            if key in (b"\x08", b"\x7f"):  # Backspace
                self.input_text = self.input_text[:-1]
            else:
                try:
                    ch = key.decode("utf-8")
                    if ch.isprintable() and ch not in ("\r", "\n"):
                        self.input_text += ch
                except UnicodeDecodeError:
                    pass
        return None

    def _handle_nav(self, kind, key):
        panel = self.panels[self.panel_focus]
        n     = len(panel.tags)
        is_ex = panel.expanded

        if _is_up(kind, key):
            if self.tag_focus > -1:
                self.tag_focus -= 1

        elif _is_down(kind, key):
            if is_ex and self.tag_focus < n - 1:
                self.tag_focus += 1

        elif _is_prev_page(kind, key):
            if self.panel_focus > 0:
                self.panel_focus -= 1
                prev = self.panels[self.panel_focus]
                self.tag_focus = min(self.tag_focus, len(prev.tags) - 1) if prev.expanded else -1

        elif _is_next_page(kind, key):
            if self.panel_focus < len(self.panels) - 1:
                self.panel_focus += 1
                next_panel = self.panels[self.panel_focus]
                self.tag_focus = min(self.tag_focus, len(next_panel.tags) - 1) if next_panel.expanded else -1

        elif kind == "char" and key == b" ":
            if self.tag_focus == -1:
                panel.expanded = not panel.expanded
            else:
                item = panel.tags[self.tag_focus]
                if item.get("is_action"):
                    self.input_mode = True
                    self.input_text = ""
                else:
                    t = item["name"]
                    (self.selected.discard if t in self.selected else self.selected.add)(t)

        elif _is_select(kind, key):
            item = panel.tags[self.tag_focus] if self.tag_focus > -1 else None
            if item and item.get("is_action"):
                self.input_mode = True
                self.input_text = ""
            else:
                if self.on_done:
                    self.on_done(list(self.selected))
                return "done"

        elif _is_quit(kind, key):
            if self.on_done:
                self.on_done(list(self.selected))
            return "done"

        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_tag_selector_ui(
    current_tags: List[str],
    ai_tags:      List[str],
    db_tags:      List[Dict[str, Any]],
    on_done: Optional[Callable[[List[str]], None]] = None,
) -> TagSelectorUI:
    """Builds the interactive tag selector UI component."""
    seen: Set[str] = set()

    manual: List[Dict] = []
    for tag in current_tags:
        if tag not in seen:
            manual.append({"name": tag, "source": "Manual", "count": 0})
            seen.add(tag)
    manual.append({"name": "+ Add new tag", "source": "Action", "is_action": True})

    ai_rec: List[Dict] = []
    for tag in ai_tags:
        if tag not in seen:
            match = next((t for t in db_tags if t["name"] == tag), None)
            src   = "AI+DB" if match else "AI"
            cnt   = match["count"] if match else 0
            ai_rec.append({"name": tag, "source": src, "count": cnt})
            seen.add(tag)

    system: List[Dict] = []
    for db_tag in db_tags:
        tag = db_tag["name"]
        if tag not in seen:
            system.append({"name": tag, "source": "DB", "count": db_tag["count"]})
            seen.add(tag)

    panels = [
        TagPanel("📝 Manual",          "blue",    manual),
        TagPanel("✨ AI Recommended",      "magenta", ai_rec),
        TagPanel("📚 System / Similar", "green",   system),
    ]

    return TagSelectorUI(panels, set(current_tags), on_done=on_done)

def select_tags_ui(
    current_tags: List[str],
    ai_tags:      List[str],
    db_tags:      List[Dict[str, Any]],
    dashboard_renderable: Optional[RenderableType] = None,
) -> List[str]:
    """Launch the interactive tag selector; returns final selected tags."""
    ui = build_tag_selector_ui(current_tags, ai_tags, db_tags)
    if dashboard_renderable:
        # Wrap it if needed for legacy calls
        pass

    # Use Live without screen=True, but with fixed height padding to prevent ghost lines
    with Live(ui.render(), auto_refresh=False) as live:
        while True:
            kind, key = _getch_with_timeout(0.1)
            if not kind:
                continue
            if ui.handle_key(kind, key) == "done":
                return list(ui.selected)
            live.update(ui.render(), refresh=True)
