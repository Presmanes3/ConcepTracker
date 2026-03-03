---
name: cli_architecture
description: >
  Enforces the layered CLI architecture of ConcepTracker.
  Use this skill whenever adding, editing, or reviewing code in src/cli/ —
  including new commands, interactors, views, screens, or components.
  Activating this skill ensures correct layer ownership, dependency direction,
  and naming conventions are respected throughout the CLI stack.
---

# CLI Architecture Skill

## Layer Map

```
src/cli/
├── commands/       Entry points. Parse args, call an Interactor.
├── interactors/    Orchestrators. Own the use-case flow.
├── views/          Pure rendering functions. Return Rich renderables.
├── screens/        Textual AppScreen subclasses. Layout + events.
└── components/     Shared UI widgets and helpers (footer, editor, etc.).
```

Registry: `src/cli/registry.py` → shim to `src/registry/command_registry.py`.  
Base screen: `src/cli/screen.py` → `AppScreen`, `run_screen`, `SCREEN_EXIT`, `ScreenSignal`.

---

## Layer Responsibilities

### commands/

- Declare and register one CLI command per file using `@registry.register(name=..., description=..., example=...)`.
- Parse Typer arguments and options only.
- Instantiate one Interactor, call `.run()`, and handle exceptions at the top level.
- Print errors via `Console().print(Panel(..., border_style="red"))`.

```python
@registry.register(name="open_note", description="Open a note in a TUI screen.", example="ct open_note 42")
def open_note(note_id: int = typer.Argument(..., help="ID of the note to open")):
    """Open a note and view its details, connections, and actions."""
    try:
        OpenNoteInteractor(note_id=note_id).run()
    except ValueError as exc:
        console.print(Panel(str(exc), title="[bold]Error[/bold]", border_style="red"))
```

**Rules:**
- No business logic.
- No direct repository or service calls.
- No `print()`. Use `Rich Console`.

---

### interactors/

- One file per use case. Name: `<use_case>_interactor.py`.
- Inject repositories via constructor parameters with defaults from `src.registry.repos`.
- Expose a `run()` method as the public entry point.
- Expose a `build_screen()` method when TUI initialization logic must be testable in isolation.
- Call `run_screen(screen)` to start an `AppScreen`.

```python
class OpenNoteInteractor:
    """Interactive screen for viewing a single note and its connections."""

    def __init__(self, note_id: int, note_repo=None, link_repo=None, arch_repo=None):
        self._note_id  = note_id
        self._note_repo = note_repo or repos.notes
        self._link_repo = link_repo or repos.links
        self._arch_repo = arch_repo or repos.archipelagos

    def run(self) -> None:
        """Open the note screen. Blocks until the user quits."""
        screen = self.build_screen()
        if screen:
            run_screen(screen)

    def build_screen(self) -> Optional[AppScreen]:
        """Fetch data and return a configured AppScreen, or None if not found."""
        ...
```

**Rules:**
- No direct SQL — only repository calls.
- No `print()` or Rich output except brief error notices before returning.
- No Textual layout code (that belongs in `screens/`).
- No view-rendering logic (that belongs in `views/`).

---

### views/

- One file per domain area: `note_views.py`, `link_views.py`, etc.
- All functions are pure: same inputs always produce the same Rich renderable.
- Functions return `Panel`, `Table`, `Text`, `Group`, `Markdown`, or any Rich `RenderableType`.
- No imports from `screens/` or `interactors/`.

```python
def open_note_top_panel(note: "Note", arch_badge: str) -> Panel:
    """Full-detail card for a note: metadata table and Markdown body."""
    meta_tbl = Table.grid(padding=(0, 4))
    meta_tbl.add_row(f"[bold cyan]ID:[/bold cyan] {note.id}", ...)
    return Panel(
        Group(meta_tbl, "", Markdown(note.content)),
        title=f"[bold green]Note #{note.id}[/bold green]",
        border_style="green",
        expand=True,
    )
```

**Rules:**
- Stateless. No `self`. No side effects.
- Import `TYPE_CHECKING` guards for model types to avoid circular imports.
- Footer views must delegate to `render_footer()` from `components/footer.py`.

---

### screens/

- Subclass `AppScreen` (from `src.cli.screen`).
- Define layout in `DEFAULT_CSS` (inline TCSS) or a companion `.tcss` file.
- Declare global shortcuts in `BINDINGS`. Use `on_key` for context-sensitive keys.
- State is held in Textual `reactive` attributes.
- Visual updates call a view function and pass the result to `Static.update()`.
- Exit via `self.dismiss(signal)` where `signal` matches the `ScreenSignal` contract.

```python
class RecordingScreen(AppScreen):
    """Live transcription screen driven by async audio events."""

    elapsed_seconds: reactive[float] = reactive(0.0)

    DEFAULT_CSS = """
    RecordingScreen { layout: vertical; }
    #transcription_zone { height: 1fr; }
    #navigation_zone    { dock: bottom; height: auto; }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="recording_zone")
        yield Static(id="transcription_zone")
        yield Static(id="navigation_zone")

    def watch_elapsed_seconds(self, value: float) -> None:
        self.query_one("#recording_zone", Static).update(render_recording_status(value, ...))
```

**Rules:**
- `background: transparent` in CSS. Never `$surface` or a hard-coded color.
- Never call repositories or services directly from a screen.
- Never render Rich content inline — always delegate to a view function.
- Call `editor.focus()` immediately after switching `ContentSwitcher` to an edit widget.
- Always update the footer when switching modes.

---

### components/

Shared, reusable UI primitives. Current components:

| File | Responsibility |
|---|---|
| `footer.py` | `render_footer(actions, ...)` — canonical footer for all screens |
| `editor.py` | `MarkdownEditor` — Textual widget for editing Markdown |
| `ai_editor.py` | `AIEditor` — editor variant with AI-assisted rewrite |
| `keys.py` | Shared key constants |

**Rules:**
- Components expose a stable public API. Screens must not reach into component internals.
- `render_footer` is the **only** way to render a footer. Never build footer markup inline in a screen.

---

## Dependency Direction

```
commands → interactors → services / repositories
                      → screens  → views
                                 → components
```

Cross-layer imports in the wrong direction (e.g., a view importing a screen) are forbidden.

---

## ScreenSignal Contract

Defined in `src/cli/screen.py`. Screens communicate with their caller by passing a signal to `self.dismiss(signal)`.

| Signal value | Meaning |
|---|---|
| `None` | No state change. |
| `SCREEN_EXIT` (`"exit"`) | Close screen, return to caller. |
| `AppScreen` instance | Transition to another screen in the same session. |
| `("suspend", callable)` | Suspend TUI, run `callable()`, restart. Return value is re-dispatched. |

---

## Naming Conventions

| Artifact | Convention | Example |
|---|---|---|
| Command file | `<verb_noun>.py` | `open_note.py` |
| Interactor class | `<VerbNoun>Interactor` | `OpenNoteInteractor` |
| View file | `<domain>_views.py` | `open_note_views.py` |
| View function | `render_<thing>` or `<thing>_panel` | `render_footer`, `open_note_top_panel` |
| Screen class | `<VerbNoun>Screen` | `OpenNoteScreen` |
| Widget ID (CSS) | `snake_case` | `#status_bar`, `#content_panel` |

---

## Adding a New Command — Checklist

- [ ] `commands/<verb_noun>.py` — register with `@registry.register`, call one Interactor.
- [ ] `interactors/<verb_noun>_interactor.py` — orchestrate data and screen.
- [ ] `views/<domain>_views.py` (or add to existing) — pure render functions.
- [ ] `screens/<verb_noun>_screen.py` — `AppScreen` subclass if a TUI is needed.
- [ ] No layer imports against the dependency direction above.
- [ ] `__init__.py` updated if the module is discovered by import (e.g., `commands/__init__.py`).
