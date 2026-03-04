"""
Open Note Screen — TUI screen for viewing a note and its connections.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.screen import AppScreen, SCREEN_EXIT, ScreenSignal
from src.cli.client.http_client import ConcepTrackerClient
from src.cli.components.ai_editor import AIEditor
from src.cli.components.editor import MarkdownEditor
from src.cli.views.link_views import link_table_view
from src.cli.views.open_note_views import open_note_actions_panel, open_note_ai_footer, open_note_delete_footer, open_note_delete_hint_panel, open_note_edit_footer
from src.cli.views.rm_views import render_delete_confirmation

console = Console()

# Which zone the cursor is on
_ZONE_TOP = "top"
_ZONE_MIDDLE = "middle"
_ZONE_MENU = "menu"


from textual import work
from textual.binding import Binding
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

class OpenNoteScreen(AppScreen):
    """
    Interactive screen for viewing a note.
    """
    alternate_screen = True

    BINDINGS = [
        Binding("ctrl+r", "run_ai",    "Run AI", priority=True, show=False),
        Binding("ctrl+a", "accept_ai", "Accept", priority=True, show=False),
        Binding("up",    "nav_up",    "Up",      show=False),
        Binding("down",  "nav_down",  "Down",    show=False),
        Binding("k",     "nav_up",    "Up",      show=False),
        Binding("j",     "nav_down",  "Down",    show=False),
        Binding("space", "interact",  "Interact", show=False),
        Binding("enter", "select",    "Select",  show=False),
        Binding("escape","back",      "Back",    priority=True, show=False),
    ]

    async def action_quit_screen(self) -> None:
        """Ctrl+C — always exit, no matter the mode."""
        if self._mode == "edit":
            self._leave_note_edit()
        if self._mode == "ai":
            self._leave_ai_enhance()
        await self.process_signal(SCREEN_EXIT)

    async def action_back(self) -> None:
        """Escape — situational back/exit behavior."""
        if self._mode == "edit":
            self._leave_note_edit()
        elif self._mode == "ai":
            self._leave_ai_enhance()
        elif self._mode == "delete_confirm":
            self._leave_delete_confirm()
        else:
            await self.process_signal(SCREEN_EXIT)

    async def action_nav_up(self) -> None:
        if self._mode != "read": return
        if self.focus_zone == _ZONE_MENU:
            if self.menu_index > 0:
                self.menu_index -= 1
            else:
                self.focus_zone = _ZONE_MIDDLE
        else:
            self._focus_prev()

    async def action_nav_down(self) -> None:
        if self._mode != "read": return
        if self.focus_zone == _ZONE_MENU:
            if self.menu_index < len(self.menu_items) - 1:
                self.menu_index += 1
            else:
                self.focus_zone = _ZONE_TOP
        else:
            self._focus_next()

    async def action_interact(self) -> None:
        """Space — expand/collapse or select menu item."""
        if self._mode != "read": return
        sig = self._handle_space()
        if sig:
            await self.process_signal(sig)

    async def action_select(self) -> None:
        """Enter — confirm deletion or select menu item."""
        if self._mode == "delete_confirm":
            sig = await self._execute_delete()
            if sig: await self.process_signal(sig)
            return

        if self._mode == "read" and self.focus_zone == _ZONE_MENU and self.menu_items:
            label, callback = self.menu_items[self.menu_index]
            if label == "Edit Note":
                self._enter_note_edit()
            elif label == "AI":
                self._enter_ai_enhance()
            elif label == "Delete":
                self._enter_delete_confirm()
            else:
                sig = callback()
                if sig: await self.process_signal(sig)

    def action_run_ai(self) -> None:
        """Ctrl+R — submit the AI prompt (only active in ai mode)."""
        if self._mode != "ai":
            return
        try:
            editor = self.query_one("#note_ai_zone", AIEditor)
            editor.start_loading()
            note_text = getattr(self._note, "content", "") or ""
            self._run_note_ai_worker(note_text, editor.prompt_text or None)
        except Exception:
            pass

    def action_accept_ai(self) -> None:
        """Ctrl+A — accept the AI result (only active in ai mode)."""
        if self._mode != "ai":
            return
        try:
            editor = self.query_one("#note_ai_zone", AIEditor)
            if editor._has_result:
                self._note.content = editor.result_text
                self._leave_ai_enhance()
        except Exception:
            pass

    DEFAULT_CSS = """
    OpenNoteScreen {
        layout: vertical;
        background: transparent;
    }
    #top_panel     { height: auto; }
    #middle_panel  { height: auto; }
    #bottom_row    { height: 1fr; }
    #menu_panel    { width: 26; height: 100%; }
    #content_panel { width: 1fr; height: 100%; }
    #footer        { height: auto; dock: bottom; }

    #note_edit_zone { 
        width: 1fr; 
        height: 100%; 
    }
    """

    # Reactive state
    top_expanded: reactive[bool] = reactive(False)
    middle_expanded: reactive[bool] = reactive(False)
    focus_zone: reactive[str] = reactive(_ZONE_TOP)
    menu_index: reactive[int] = reactive(0)

    def __init__(
        self,
        note,
        arch_badge: str,
        out_links: list,
        in_links: list,
        note_summaries: dict,
        menu_items: List[Tuple[str, Callable[[], Any]]],
    ):
        # 1. Non-reactive data members
        self._note = note
        self._arch_badge = arch_badge
        self._out_links = out_links
        self._in_links = in_links
        self._note_summaries = note_summaries
        self.menu_items = menu_items
        self.right_pane_renderable: Optional[RenderableType] = None
        self._mode: str = "read"
        
        # 2. Call super
        super().__init__()

        # 3. Initialise reactive attributes (only if different from class defaults)
        # top_expanded and others already have correct defaults in their reactive() call.
        # But we set them explicitly here after super to ensure they are synchronized.
        self.top_expanded = False
        self.middle_expanded = False
        self.focus_zone = _ZONE_TOP
        self.menu_index = 0

    def compose(self) -> ComposeResult:
        yield Static(id="top_panel")
        yield Static(id="middle_panel")
        with Horizontal(id="bottom_row"):
            yield Static(id="menu_panel")
            # Content panel (right side). The MarkdownEditor is mounted dynamically
            # on demand so it never silently absorbs focus while hidden.
            yield Static(id="content_panel")
        yield Static(id="footer")

    def watch_top_expanded(self, _) -> None:
        self.refresh_zones()

    def watch_middle_expanded(self, _) -> None:
        self.refresh_zones()

    def watch_focus_zone(self, _) -> None:
        self.refresh_zones()

    def watch_menu_index(self, _) -> None:
        self.refresh_zones()

    def on_mount(self) -> None:
        super().on_mount()
        self._refresh_footer()
        self.refresh_zones()

    def _refresh_footer(self) -> None:
        """Swap footer content based on current mode."""
        try:
            if self._mode == "edit":
                renderable = open_note_edit_footer()
            elif self._mode == "ai":
                renderable = open_note_ai_footer()
            elif self._mode == "delete_confirm":
                renderable = open_note_delete_footer()
            elif (
                self._mode == "read"
                and self.focus_zone == _ZONE_MENU
                and self.menu_items
                and self.menu_index < len(self.menu_items)
                and self.menu_items[self.menu_index][0] == "Delete"
            ):
                renderable = open_note_delete_hint_panel()
            else:
                renderable = open_note_actions_panel()
            self.query_one("#footer", Static).update(renderable)
        except Exception:
            pass

    def refresh_zones(self) -> None:
        """Push Rich renderables into the individual Textual widgets."""
        try:
            self.query_one("#top_panel", Static).update(self._render_top())
        except Exception:
            pass
        try:
            self.query_one("#middle_panel", Static).update(self._render_middle())
        except Exception:
            pass
        try:
            self.query_one("#menu_panel", Static).update(self._render_menu())
        except Exception:
            pass
        if self._mode == "read":
            try:
                self.query_one("#content_panel", Static).update(self._render_content())
            except Exception:
                pass
        self._refresh_footer()
    # ------------------------------------------------------------------ #
    #  AI enhance lifecycle                                                #
    # ------------------------------------------------------------------ #

    def _enter_ai_enhance(self) -> None:
        """Mount AIEditor into #bottom_row for AI-assisted note enhancement."""
        note_text = getattr(self._note, "content", "") or ""
        self.query_one("#content_panel", Static).display = False
        bottom_row = self.query_one("#bottom_row", Horizontal)
        bottom_row.mount(AIEditor(original_text=note_text, id="note_ai_zone"))
        # AIEditor.on_mount focuses its prompt TextArea automatically.
        self._mode = "ai"
        self._refresh_footer()
        self.query_one("#menu_panel", Static).update(self._render_menu())

    def _leave_ai_enhance(self) -> None:
        """Remove the AIEditor and restore read mode."""
        self._mode = "read"
        try:
            self.query_one("#note_ai_zone", AIEditor).remove()
        except Exception:
            pass
        try:
            self.query_one("#content_panel", Static).display = True
            self.focus()
            self.refresh_zones()
            self._refresh_footer()
        except Exception:
            pass

    # ── AIEditor message handlers ────────────────────────────────────────

    def on_ai_editor_submit_prompt(self, message: AIEditor.SubmitPrompt) -> None:
        """Ctrl+R in AIEditor — start the AI worker."""
        message.editor.start_loading()
        note_text = getattr(self._note, "content", "") or ""
        self._run_note_ai_worker(note_text, message.prompt or None)

    def on_ai_editor_accept(self, message: AIEditor.Accept) -> None:
        """Ctrl+A in AIEditor — apply the result to the note and return to read."""
        self._note.content = message.result
        self._leave_ai_enhance()

    def on_markdown_editor_save_request(self, message: MarkdownEditor.SaveRequest) -> None:
        """Handle Ctrl+S from the MarkdownEditor component."""
        message.stop()  # Prevent double bubbling/handling
        self._save_note_edit()

    @work(thread=True, exclusive=True)
    def _run_note_ai_worker(self, text: str, prompt: str | None) -> None:
        """AI enhancement in a background thread."""
        try:
            from src.cli.client.http_client import ConcepTrackerClient
            with ConcepTrackerClient() as client:
                result = client.enhance_transcription(text, prompt)
            if result.error:
                self.app.call_from_thread(self._on_ai_error, str(result.error))
            else:
                self.app.call_from_thread(self._on_ai_done, result.enhanced_text)
        except Exception as exc:
            self.app.call_from_thread(self._on_ai_error, str(exc))

    def _on_ai_agent_step(self, label: str) -> None:
        try:
            self.query_one("#note_ai_zone", AIEditor).update_agent(label)
        except Exception:
            pass

    def _on_ai_done(self, enhanced_text: str) -> None:
        try:
            self.query_one("#note_ai_zone", AIEditor).set_result(enhanced_text)
        except Exception:
            pass
        self._refresh_footer()

    def _on_ai_error(self, error_msg: str) -> None:
        try:
            self.query_one("#note_ai_zone", AIEditor).set_error(error_msg)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Edit-mode lifecycle                                                 #
    # ------------------------------------------------------------------ #

    def _enter_note_edit(self) -> None:
        """Dynamically mount MarkdownEditor into #bottom_row and focus it."""
        note_text = getattr(self._note, "content", "") or ""

        # Hide the content hint panel; menu stays visible
        self.query_one("#content_panel", Static).display = False

        # Mount the editor fresh — avoids the hidden-TextArea focus-absorption bug.
        bottom_row = self.query_one("#bottom_row", Horizontal)
        editor = MarkdownEditor(
            initial_text=note_text,
            title="Edit Note",
            subtitle="Ctrl+S \u00b7 Esc",
            id="note_edit_zone",
        )
        bottom_row.mount(editor)
        # Focus is handled automatically by MarkdownEditor.on_mount, which runs
        # after compose() so #editor_textarea is guaranteed to exist.

        self._mode = "edit"
        self._refresh_footer()
        self.query_one("#menu_panel", Static).update(self._render_menu())

    def _mode_transition_to_read(self) -> None:
        """Remove the dynamic editor widget and restore read mode cleanly."""
        self._mode = "read"
        try:
            self.query_one("#note_edit_zone", MarkdownEditor).remove()
        except Exception:
            pass
        try:
            self.query_one("#content_panel", Static).display = True
            # Return focus to the screen so key events (Space, arrows…) work again
            self.focus()
            self.refresh_zones()
            self._refresh_footer()
        except Exception:
            pass

    def _leave_note_edit(self) -> None:
        """Commit discard and return."""
        self._mode_transition_to_read()

    @work(thread=True, exclusive=True)
    def _save_note_edit(self) -> None:
        """Commit the edited text to the note object, then leave edit mode."""
        try:
            editor = self.query_one("#note_edit_zone", MarkdownEditor)
            new_content = editor.text
            
            # Update the note on the server
            with ConcepTrackerClient() as client:
                updated_note = client.update_note(note_id=self._note.id, content=new_content)
                self._note = updated_note
            
            self.app.call_from_thread(self._mode_transition_to_read)
        except Exception as e:
            self.notify(f"Error saving note: {e}", severity="error")

    def _update_preview(self) -> None:
        """No longer used — logic moved into MarkdownEditor component."""
        pass

    # ------------------------------------------------------------------ #
    #  Layout construction (top + middle zones only; bottom is Textual)   #
    # ------------------------------------------------------------------ #

    def build_layout(self) -> None:
        return None  # layout driven entirely by refresh_zones()

    # ------------------------------------------------------------------ #
    #  Zone renderers                                                      #
    # ------------------------------------------------------------------ #

    def _render_top(self) -> RenderableType:
        note = getattr(self, "_note", None)
        if not note:
            return Panel("[red]Error: Note not found[/red]")

        is_focused = self.focus_zone == _ZONE_TOP
        border = "green" if is_focused else "dim"
        icon = "▼" if self.top_expanded else "▶"
        title_color = "green" if is_focused else "dim"
        title = f"[bold {title_color}]{icon} Note #{note.id}[/bold {title_color}]"

        try:
            date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = "(unknown date)"

        tags_str = f"[magenta]{note.tags}[/magenta]" if getattr(note, "tags", None) else "[dim]No Tags[/dim]"
        raw = getattr(note, "content", "") or ""

        # Meta row is always the same single line regardless of expand/collapse
        meta = Table.grid(padding=(0, 4))
        meta.add_row(
            f"[bold cyan]ID:[/bold cyan] {note.id}",
            f"[bold cyan]Arch:[/bold cyan] {getattr(self, '_arch_badge', '~')}",
            f"[bold cyan]Date:[/bold cyan] {date_str}",
            f"[bold cyan]Tags:[/bold cyan] {tags_str}",
        )

        if self.top_expanded:
            body = Markdown(raw) if raw.strip() else Text("No content.", style="dim italic")
        else:
            preview = (raw[:400].strip() + "\n\n…") if len(raw) > 400 else raw.strip()
            body = Markdown(preview) if preview else Text("No content.", style="dim italic")

        return Panel(
            Group(meta, "", body),
            title=title,
            border_style=border,
            expand=True,
        )

    def _render_middle(self) -> RenderableType:
        is_focused = self.focus_zone == _ZONE_MIDDLE
        border = "green" if is_focused else "dim"
        icon = "▼" if self.middle_expanded else "▶"
        title_color = "green" if is_focused else "dim"
        title = f"[bold {title_color}]{icon} Connections[/bold {title_color}]"

        out_links = getattr(self, "_out_links", [])
        in_links = getattr(self, "_in_links", [])
        
        if not self.middle_expanded:
            summary = f"[dim]{len(out_links)} outgoing, {len(in_links)} incoming[/dim]"
            return Panel(Text.from_markup(summary), title=title, border_style=border, expand=True)

        # Expanded: full link table (no row limit)
        return link_table_view(
            out_links,
            in_links,
            getattr(self, "_note_summaries", {}),
            title=title,
            border_style=border,
        )

    def _render_bottom(self) -> RenderableType:
        """Kept for compatibility — not used when layout uses Textual containers."""
        return Group(self._render_menu(), self._render_content())

    def _render_menu(self) -> RenderableType:
        is_zone_focused = self.focus_zone == _ZONE_MENU
        items: list[Text] = []
        menu_items = getattr(self, "menu_items", [])
        for i, (label, _) in enumerate(menu_items):
            is_selected = is_zone_focused and i == self.menu_index
            bullet = "●" if is_selected else "○"
            if is_selected:
                row = Text(f" {bullet} {label}", style="bold black on green")
            elif "(not implemented)" in label.lower() or label == "AI":
                row = Text(f" {bullet} {label}", style="dim")
            else:
                row = Text(f" {bullet} {label}", style="white")
            items.append(row)

        if not items:
            items.append(Text("  (empty)", style="dim"))

        border = "green" if is_zone_focused else "dim"
        menu_title = "[bold green]Actions[/bold green]" if is_zone_focused else "[bold dim]Actions[/bold dim]"
        return Panel(
            Group(*items),
            title=menu_title,
            border_style=border,
        )

    def _render_content(self) -> RenderableType:
        # If a callback has set explicit content, show it
        explicit = getattr(self, "right_pane_renderable", None)
        if explicit:
            return Panel(explicit, title="[bold]Content[/bold]", border_style="dim")

        # Otherwise show a contextual hint for the focused menu item
        if self.focus_zone == _ZONE_MENU:
            menu_items = getattr(self, "menu_items", [])
            if menu_items and self.menu_index < len(menu_items):
                label, _ = menu_items[self.menu_index]
                hints = {
                    "Edit Note":     ("green",  "Open the note in the editor to modify its content."),
                    "AI":            ("magenta", "[dim]AI actions are not implemented yet.[/dim]"),
                    "Trace":         ("cyan",    "Visualise the chronological evolution of this concept."),
                    "Manage Tags":   ("yellow",  "Add, remove or rename tags on this note."),
                    "Manage Links":  ("blue",    "Add or remove connections to other notes."),
                    "Delete":        ("red",     "[bold red]Permanently delete this note and all its links.[/bold red]"),
                }
                color, hint = hints.get(label, ("dim", "Press Enter to execute."))
                return Panel(
                    Text.from_markup(hint),
                    title=f"[bold]{label}[/bold]",
                    border_style=color,
                )

        return Panel(
            Text("Navigate to Actions and press Enter.", style="dim italic"),
            title="[bold]Content[/bold]",
            border_style="dim",
        )

    # ------------------------------------------------------------------ #
    #  Focus helpers                                                       #
    # ------------------------------------------------------------------ #

    _FOCUS_ORDER = [_ZONE_TOP, _ZONE_MIDDLE, _ZONE_MENU]

    def _focus_next(self) -> None:
        idx = self._FOCUS_ORDER.index(self.focus_zone)
        self.focus_zone = self._FOCUS_ORDER[(idx + 1) % len(self._FOCUS_ORDER)]

    def _focus_prev(self) -> None:
        idx = self._FOCUS_ORDER.index(self.focus_zone)
        self.focus_zone = self._FOCUS_ORDER[(idx - 1) % len(self._FOCUS_ORDER)]

    # ------------------------------------------------------------------ #
    #  Key handling                                                        #
    # ------------------------------------------------------------------ #

    def handle_action(self, key: str) -> ScreenSignal:
        """Deprecated legacy bridge."""
        pass

    # ------------------------------------------------------------------ #
    #  Delete-confirm lifecycle                                            #
    # ------------------------------------------------------------------ #

    def _enter_delete_confirm(self) -> None:
        """Switch to delete-confirmation mode, showing a confirmation panel."""
        self._mode = "delete_confirm"
        try:
            self.query_one("#content_panel", Static).update(
                render_delete_confirmation(self._note)
            )
        except Exception:
            pass
        self._refresh_footer()
        try:
            self.query_one("#menu_panel", Static).update(self._render_menu())
        except Exception:
            pass

    def _leave_delete_confirm(self) -> None:
        """Cancel delete and return to normal read mode."""
        self._mode = "read"
        self.refresh_zones()
        self._refresh_footer()

    def _execute_delete(self) -> ScreenSignal:
        """Run the Delete callback from menu_items and return its signal."""
        for label, callback in self.menu_items:
            if label == "Delete":
                return callback()
        return None

    def _handle_space(self) -> ScreenSignal:
        if self.focus_zone == _ZONE_TOP:
            self.top_expanded = not self.top_expanded
            return True  # refresh_zones() will rebuild the Group
        elif self.focus_zone == _ZONE_MIDDLE:
            self.middle_expanded = not self.middle_expanded
            return True  # refresh_zones() will rebuild the Group
        elif self.focus_zone == _ZONE_MENU and self.menu_items:
            _, callback = self.menu_items[self.menu_index]
            return callback()
        return None
