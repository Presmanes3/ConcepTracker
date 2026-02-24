# CLI Visual Aspect Guide

Visual design system for the ConcepTracker CLI.
All screens must follow this guide to provide a consistent, professional UX.

---

## Technical Vocabulary

To communicate effectively, we distinguish between **Textual** (the skeleton/interactivity) and **Rich** (the skin/content).

### Textual (Structure & Layout)

- **App**: The root engine. Manages the screen stack.
- **Screen**: A full-screen view. Only one is active at a time.
- **Widget**: Any UI element (Button, Input, Static).
- **Container**: A widget that holds others (`Vertical`, `Horizontal`, `Grid`).
- **Static**: A specialized widget used as a bridge to display **Rich** content.
- **Docking**: Pinning a widget to an edge (`top`, `bottom`, `left`, `right`) via CSS.
- **Mounting**: The process of adding a widget to the TUI.

### Rich (Visual Content)

- **Renderable**: Anything Rich can draw (Panel, Table, Markdown).
- **Panel**: A box with a border and a title. Our primary container for text.
- **Group**: A way to stack multiple Rich elements inside a single `Static` widget.
- **Segment/Style**: Low-level control for colors and effects.

---

## Anatomy of a Screen

Every screen is a `Vertical` container by default, following this layout strategy:

```
┌─────────────────────────────────────────────────────┐
│  STATUS BAR (Static) — Dock: Top                    │
│  Shows state via Rich Panel                         │
├──────────────────────┬──────────────────────────────┤
│  BODY (Horizontal)   │  CONTENT ZONE (Vertical)     │
│                      │                              │
│  SIDEBAR (Static)    │  Primary information area    │
│  Width: 30-35        │  Height: 1fr (fills space)   │
│                      │                              │
├──────────────────────┴──────────────────────────────┤
│  FOOTER (Static) — Dock: Bottom                     │
│  Shows valid keys via render_footer()               │
└─────────────────────────────────────────────────────┘
```

**Rules:**

- Use `Dock: Top/Bottom` for bars that should never scroll.
- Use `Height: 1fr` on the main content to ensure it expands to fill the screen.
- Never use print() — always `self.notify()` or update a `Static` widget.

---

## Textual Layout Skeleton

```python
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ContentSwitcher, Static, TextArea

def compose(self) -> ComposeResult:
    yield Static(id="status")            # Docked top in CSS
    with Horizontal(id="body"):
        yield Static(id="sidebar")       # Fixed width
        with Vertical(id="content-container"):
            with ContentSwitcher(initial="content_read"):
                yield Static(id="content_read")
                yield TextArea(id="content_edit")
    yield Static(id="footer")            # Docked bottom in CSS
```

**CSS Strategy (TCSS):**
```css
Screen {
    layout: vertical;
}

#status {
    dock: top;
    height: auto;
}

#body {
    height: 1fr; /* Takes all remaining vertical space */
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

---

## Color Semantics

| Color       | Usage                                             | Example                      |
|-------------|---------------------------------------------------|------------------------------|
| `blue`      | System state panels, info bars                    | Recording status, panel borders |
| `bold red`  | Active alerts, recording dot, destructive actions | `● RECORDING`, Discard button |
| `green`     | Content panels, notes, saved state, success       | Transcript, Note cards       |
| `yellow`    | Paused / warning state                            | `⏸ PAUSED` status bar       |
| `cyan`      | Metadata labels and values, keystroke hints       | `Words: 34`, `[Space] Pause` |
| `magenta`   | Tags, selections, highlights                      | `#tag-name`, selected row    |
| `dim`       | Secondary info, hints, placeholders, partials     | `"Listening…"`, footer sub-text |

---

## Panels (Rich)

The primary visual unit. **Always rendered from a View function.**

```python
# Status bar
Panel(info_text, border_style="blue",   title="[bold]Recording[/bold]")
Panel(info_text, border_style="yellow", title="[bold]Paused[/bold]")

# Content panels
Panel(Markdown(text), border_style="green", title="[bold]Transcript[/bold]")

# Metadata + content (note cards)
Panel(Group(meta_table, "", Markdown(content)), border_style="green",
      title=f"[bold green]Note #{note.id}[/bold green]")
```

**Rules:**
- `title` must always be `"[bold]Label[/bold]"` format.
- `border_style` must follow the color semantics table above.
- Never build a Panel inside a Screen — always call the View.

---

## Status Bar Pattern

One `Static` widget at the top, updated via View on every state change.

```python
# In the View:
def render_my_status(time_str: str, words: int) -> Panel:
    t = Text()
    t.append("● STATE",    style="bold red")
    t.append("  │  ",      style="dim")
    t.append("Time: ",     style="dim cyan")
    t.append(time_str,     style="cyan")
    t.append("  │  ",      style="dim")
    t.append("Words: ",    style="dim cyan")
    t.append(str(words),   style="cyan")
    return Panel(t, border_style="blue", title="[bold]Status[/bold]")

# In the Screen:
self.query_one("#status", Static).update(render_my_status(...))
```

**Rules:**
- Separator between items is `  │  ` with `style="dim"`.
- Values always in `cyan`. Labels always in `dim cyan`.
- The leading indicator (state label) is `bold <color>`.

---

## Footer Pattern

**Always** use `render_footer()` from `src/cli/components/footer.py`. Never use Textual's native `Footer` widget.

```python
from src.cli.components.footer import render_footer

# signature: (key_label, action_label, color)
render_footer([
    ("Space",  "Pause",   "cyan"),
    ("s",      "Save",    "green"),
    ("Ctrl+C", "Discard", "red"),
])
```

**Rules:**
- Keys in `[brackets]` or `Ctrl+X` format — `render_footer` handles styling automatically.
- Colors must match semantics: green = positive action, red = destructive, cyan = neutral navigation.
- Footer **must change** when the screen switches modes (e.g., read vs. edit).
- Always `border=True, border_style="dim cyan"` unless overriding for a specific reason.

---

## Sidebar / Side Panel Pattern

Use when a screen has persistent navigation options (e.g., actions menu for a note, pause menu options). Implemented as a fixed-width `Static` showing a Rich `Panel`.

```python
# In the View:
def render_sidebar(items: list, selected: int) -> Panel:
    t = Text()
    for i, (label, _) in enumerate(items):
        prefix = "▶ " if i == selected else "  "
        style  = "bold cyan" if i == selected else ""
        t.append(f"{prefix}{label}\n", style=style)
    return Panel(t, title="[bold]Actions[/bold]", border_style="cyan")
```

**Rules:**
- Width: `30–35` characters.
- Use `▶` prefix on the selected item.
- Selected item: `bold cyan`. Others: plain or `dim`.
- Never put business logic in the sidebar View. One function, one renderable.

---

## Content Modes (Read / Edit)

When a screen needs two modes over the same content area, use `ContentSwitcher`.

```python
with ContentSwitcher(initial="read"):
    yield Static(id="read")    # Rich Panel with Markdown content
    yield TextArea(id="edit")  # Native Textual editor
```

Switching modes:
```python
def enter_edit_mode(self) -> None:
    editor = self.query_one("#edit", TextArea)
    editor.load_text(self._full_text)
    self.query_one(ContentSwitcher).current = "edit"
    editor.focus()
    self.query_one("#footer", Static).update(render_my_footer("edit"))

def exit_edit_mode(self) -> None:
    self.query_one(ContentSwitcher).current = "read"
    self.query_one("#footer", Static).update(render_my_footer("read"))
```

**Rules:**
- ALWAYS call `editor.focus()` immediately after switching to edit mode. Without this, the TextArea does not receive keyboard input.
- ALWAYS update the footer when switching modes.
- NEVER use `Binding` declarations as the sole key handler for edit mode — use `on_key` as a fallback to ensure `escape` and `ctrl+s` are captured even when TextArea has focus.

---

## Key Handling Rules

```python
def on_key(self, event) -> None:
    """Explicit fallback for context-sensitive keys."""
    if event.key == "escape":
        if self._mode == "edit":
            self.exit_edit_mode()
        else:
            self.dismiss(("resume", None))
        event.stop()
    elif event.key == "ctrl+s" and self._mode == "edit":
        self.action_save()
        event.stop()
```

**Rules:**
- Use `Binding` for global screen-level shortcuts (e.g., `Ctrl+C`).
- Use `on_key` for **context-sensitive** shortcuts where the same key means different things depending on which widget is focused or which mode is active.
- Always call `event.stop()` after handling a key explicitly to prevent propagation.

---

## Typography Quick Reference

| Pattern               | Markup                          | Use case                      |
|-----------------------|---------------------------------|-------------------------------|
| Section title (panel) | `"[bold]Label[/bold]"`        | `Panel(title=...)`            |
| Active state label    | `"[bold red]● RECORDING[/bold red]"` | Status bar leading text  |
| Metadata label        | `"[dim cyan]Words:[/dim cyan]"` | Stats in status bar          |
| Metadata value        | `"[cyan]34[/cyan]"`           | Stats in status bar           |
| Tags                  | `"[magenta]#tag[/magenta]"`   | Note metadata                 |
| Placeholder / hint    | `"[dim italic]No content.[/dim italic]"` | Empty states       |
| Separator             | `"  │  "` with `style="dim"`  | Between status bar items      |
| Long-form content     | `Markdown(text)`              | Note bodies, transcripts      |

---

## Summary Checklist for New Screens

- [ ] Status bar at top (`Static`, updated via a View that returns a `Panel`).
- [ ] Screen CSS uses `background: transparent` — never `$surface` or any colour.
- [ ] Content zone fills remaining height (`height: 1fr`).
- [ ] Footer at bottom (`Static`, updated via `render_footer()`), always `dock: bottom` in CSS.
- [ ] Footer changes when screen mode changes.
- [ ] All Rich content built in `views/` — Screens only wire widgets.
- [ ] `on_key` handles context-sensitive keys (never rely on `Binding` alone for mode-switching).
- [ ] `editor.focus()` called immediately when switching to edit mode.
- [ ] Colors follow the semantics table.
- [ ] Panel titles use `[bold]Label[/bold]` format.
