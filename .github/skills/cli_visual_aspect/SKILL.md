---
name: cli_visual_aspect
description: >
  Enforces the visual design system for ConcepTracker's TUI.
  Use this skill whenever building or modifying any Textual screen, Rich panel,
  status bar, footer, sidebar, or color usage in src/cli/.
  Activating this skill ensures consistent layout, color semantics, and
  component patterns across all screens.
---

# CLI Visual Aspect Skill

## Vocabulary

| Term | Definition |
|---|---|
| **App** | Textual root engine. Manages the screen stack. |
| **Screen** | Full-screen view. Only one active at a time. Subclass of `AppScreen`. |
| **Widget** | Any UI element (`Static`, `Button`, `TextArea`). |
| **Container** | A widget that holds others (`Vertical`, `Horizontal`). |
| **Static** | Bridge widget between Textual layout and Rich renderables. |
| **Renderable** | Anything Rich can draw (`Panel`, `Table`, `Markdown`, `Text`). |
| **Panel** | Rich box with a border and title. Primary container for all content areas. |
| **Group** | Stacks multiple Rich renderables inside a single `Static.update()`. |

---

## Screen Layout

Every screen follows this structure:

```
┌─────────────────────────────────────────────┐
│  STATUS BAR — dock: top                     │
├──────────────────┬──────────────────────────┤
│  SIDEBAR         │  CONTENT ZONE            │
│  width: 30–35    │  height: 1fr             │
├──────────────────┴──────────────────────────┤
│  FOOTER — dock: bottom                      │
└─────────────────────────────────────────────┘
```

### TCSS skeleton

```css
Screen {
    layout: vertical;
    background: transparent;
}
#status {
    dock: top;
    height: auto;
}
#body {
    height: 1fr;
}
#sidebar {
    width: 32;
    border-right: tall $accent;
}
#footer {
    dock: bottom;
    height: auto;
}
```

### Compose skeleton

```python
def compose(self) -> ComposeResult:
    yield Static(id="status")
    with Horizontal(id="body"):
        yield Static(id="sidebar")
        with Vertical(id="content_container"):
            with ContentSwitcher(initial="content_read"):
                yield Static(id="content_read")
                yield TextArea(id="content_edit")
    yield Static(id="footer")
```

**Rules:**
- `background: transparent` on every screen. Never `$surface` or a hard-coded color.
- `height: 1fr` on the main content zone so it fills remaining space.
- `dock: top` and `dock: bottom` for bars that must never scroll.
- Never call `print()`. Use `self.notify()` or `Static.update()`.

---

## Color Semantics

| Color | Usage |
|---|---|
| `blue` | System/info panels, status bar borders |
| `bold red` | Active alerts, recording indicator, destructive actions |
| `green` | Note content, saved state, success |
| `yellow` | Paused state, warnings |
| `cyan` | Metadata labels and values, neutral navigation hints |
| `magenta` | Tags, selections, highlights |
| `dim` | Secondary info, hints, placeholders, separators |

---

## Panels

All content areas are Rich `Panel` instances built in `views/` functions and passed to `Static.update()`.

```python
# Info / status
Panel(text, border_style="blue",  title="[bold]Status[/bold]")

# Note content
Panel(Group(meta_table, "", Markdown(content)),
      border_style="green",
      title=f"[bold green]Note #{note.id}[/bold green]")

# Warning / paused
Panel(text, border_style="yellow", title="[bold]Paused[/bold]")
```

**Rules:**
- `title` must always be `"[bold]Label[/bold]"`. Exception: note panels use `"[bold green]Note #N[/bold green]"`.
- `border_style` must match the color semantics table.
- Never build a `Panel` inline inside a screen method — always call the view function.

---

## Status Bar

One `Static(id="status")` at the top, updated on every state change.

```python
# In views/<domain>_views.py
def render_recording_status(elapsed: str, words: int) -> Panel:
    t = Text()
    t.append("● RECORDING", style="bold red")
    t.append("  │  ",        style="dim")
    t.append("Time: ",       style="dim cyan")
    t.append(elapsed,        style="cyan")
    t.append("  │  ",        style="dim")
    t.append("Words: ",      style="dim cyan")
    t.append(str(words),     style="cyan")
    return Panel(t, border_style="blue", title="[bold]Status[/bold]")

# In the screen
self.query_one("#status", Static).update(render_recording_status(...))
```

**Rules:**
- Separator between items: `"  │  "` with `style="dim"`.
- Metric values: `cyan`. Metric labels: `dim cyan`.
- State indicator (leading label): `bold <color>` per the semantics table.

---

## Footer

Always use `render_footer()` from `src/cli/components/footer.py`. Never build footer markup inline.

```python
from src.cli.components.footer import render_footer

self.query_one("#footer", Static).update(
    render_footer([
        ("Space",  "Pause",   "cyan"),
        ("s",      "Save",    "green"),
        ("Ctrl+C", "Discard", "red"),
    ])
)
```

`render_footer` signature:
```python
def render_footer(
    actions: List[Tuple[str, str, str]],   # (key_label, action_label, color)
    page_info: Optional[Tuple[int, int]] = None,
    border: bool = True,
    border_style: str = "dim",
    status_msg: Optional[str] = None,
) -> Union[Panel, Text]:
```

**Rules:**
- Colors must follow semantics: `green` = positive action, `red` = destructive, `cyan` = neutral navigation, `yellow` = warning.
- The footer **must be updated** every time the screen switches modes (read ↔ edit ↔ delete ↔ AI).
- Default `border=True, border_style="dim"`. Override only when justified.

---

## Sidebar

Fixed-width `Static` on the left side showing a Rich `Panel` with a vertical action list.

```python
# In views/
def render_sidebar(items: list[tuple[str, Any]], selected: int) -> Panel:
    t = Text()
    for i, (label, _) in enumerate(items):
        prefix = "▶ " if i == selected else "  "
        style  = "bold cyan" if i == selected else ""
        t.append(f"{prefix}{label}\n", style=style)
    return Panel(t, title="[bold]Actions[/bold]", border_style="cyan")
```

**Rules:**
- Width: `30–35` characters.
- Selected item: `▶` prefix + `bold cyan`. Unselected: plain.
- No business logic in sidebar view functions.

---

## ContentSwitcher (Read / Edit Modes)

Use `ContentSwitcher` when a single content zone has multiple modes.

```python
with ContentSwitcher(initial="content_read"):
    yield Static(id="content_read")
    yield TextArea(id="content_edit")
```

Switching modes:

```python
def _enter_edit_mode(self) -> None:
    editor = self.query_one("#content_edit", TextArea)
    editor.load_text(self._note.content)
    self.query_one(ContentSwitcher).current = "content_edit"
    editor.focus()                          # MANDATORY: TextArea won't capture keys otherwise
    self._mode = "edit"
    self.query_one("#footer", Static).update(render_my_footer("edit"))

def _exit_edit_mode(self) -> None:
    self.query_one(ContentSwitcher).current = "content_read"
    self._mode = "read"
    self.query_one("#footer", Static).update(render_my_footer("read"))
```

**Rules:**
- `editor.focus()` is mandatory immediately after switching to an edit widget.
- Footer must update on every mode transition.

---

## Key Handling

```python
BINDINGS = [
    Binding("ctrl+c", "quit_screen", "Quit", priority=True, show=False),
]

def on_key(self, event) -> None:
    """Context-sensitive keys that depend on the current mode."""
    if event.key == "escape":
        if self._mode == "edit":
            self._exit_edit_mode()
        else:
            self.dismiss(SCREEN_EXIT)
        event.stop()
    elif event.key == "ctrl+s" and self._mode == "edit":
        self._save()
        event.stop()
```

**Rules:**
- `BINDINGS` handles global, always-active shortcuts.
- `on_key` handles context-sensitive shortcuts where the same key means different things by mode or focused widget.
- Always call `event.stop()` after explicitly handling a key.

---

## Typography Reference

| Pattern | Markup | Context |
|---|---|---|
| Panel title | `"[bold]Label[/bold]"` | All panels except note cards |
| Note card title | `"[bold green]Note #N[/bold green]"` | Note content panels |
| State indicator | `"[bold red]● RECORDING[/bold red]"` | Status bar |
| Metric label | `"[dim cyan]Words:[/dim cyan]"` | Status bar |
| Metric value | `"[cyan]34[/cyan]"` | Status bar |
| Tag | `"[magenta]#tag[/magenta]"` | Note metadata |
| Placeholder | `"[dim italic]No content.[/dim italic]"` | Empty states |
| Separator | `"  │  "` with `style="dim"` | Between status bar items |
| Long-form content | `Markdown(text)` | Note bodies, transcripts |
| Sidebar cursor | `"▶ "` with `style="bold cyan"` | Selected menu item |

---

## New Screen Checklist

- [ ] `AppScreen` subclass in `screens/`.
- [ ] `DEFAULT_CSS` uses `background: transparent`.
- [ ] `Static(id="status")` at top, updated via a view function returning a `Panel`.
- [ ] `Static(id="footer")` at bottom with `dock: bottom`, updated via `render_footer()`.
- [ ] Content zone has `height: 1fr`.
- [ ] Footer is updated on every mode change.
- [ ] All Rich content built in `views/` — screen only calls `Static.update(view_fn(...))`.
- [ ] `on_key` covers context-sensitive shortcuts; `BINDINGS` covers global ones.
- [ ] `editor.focus()` called immediately after switching `ContentSwitcher` to an edit widget.
- [ ] All colors comply with the semantics table.
- [ ] All `Panel` titles use `[bold]Label[/bold]` format.
