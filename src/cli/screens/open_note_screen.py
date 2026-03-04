"""
Open Note Screen — TUI screen for viewing a note and its connections.
"""
from __future__ import annotations

from typing import Any, List, Optional

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.cli.screen import AppScreen, SCREEN_EXIT, ScreenSignal
from src.cli.client.http_client import ConcepTrackerClient
from src.cli.components.ai_editor import AIEditor
from src.cli.components.editor import MarkdownEditor
from src.cli.screens.note_actions import NoteAction
from src.cli.views.link_views import link_table_view
from src.cli.views.open_note_views import (
    open_note_actions_panel,
    open_note_ai_footer,
    open_note_delete_footer,
    open_note_delete_hint_panel,
    open_note_edit_footer,
    open_note_trace_footer,
)
from src.cli.views.rm_views import render_delete_confirmation
from src.cli.views.trace_views import render_trace_timeline

console = Console()

# Which zone the cursor is on
_ZONE_TOP = "top"
_ZONE_MIDDLE = "middle"
_ZONE_MENU = "menu"
_ZONE_CONTENT = "content"


from textual import work
from textual.binding import Binding
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import ContentSwitcher, Static

class OpenNoteScreen(AppScreen):
    """
    Interactive screen for viewing a note.
    """
    alternate_screen = True

    BINDINGS = [
        Binding("ctrl+r", "run_ai",    "Run AI", priority=True, show=False),
        Binding("ctrl+a", "accept_ai", "Accept", priority=True, show=False),
        Binding("ctrl+left",  "nav_left",  "To Menu",    priority=True, show=False),
        Binding("ctrl+right", "nav_right", "To Content", priority=True, show=False),
        Binding("up",    "nav_up",   "Up",   show=False),
        Binding("down",  "nav_down", "Down", show=False),
        Binding("k",     "nav_up",   "Up",   show=False),
        Binding("j",     "nav_down", "Down", show=False),
        Binding("space", "interact", "Interact", show=False),
        Binding("enter", "select",   "Select",   show=False),
        Binding("escape","back",     "Back", priority=True, show=False),
    ]

    async def action_quit_screen(self) -> None:
        """Ctrl+C — always exit regardless of mode."""
        if self._active_action is not None:
            leave_fn = self._active_action.leave
            self._active_action = None
            leave_fn()
        await self.process_signal(SCREEN_EXIT)

    async def action_back(self) -> None:
        """Escape — leave active mode, or exit screen if already idle."""
        if self._active_action is not None:
            # Clear _active_action BEFORE calling leave so _mode is already
            # "read" when leave() triggers footer/zone refreshes.
            leave_fn = self._active_action.leave
            self._active_action = None
            leave_fn()
        else:
            await self.process_signal(SCREEN_EXIT)

    # ------------------------------------------------------------------ #
    #  Zone management (single source of truth)                           #
    # ------------------------------------------------------------------ #

    @property
    def _content_widget(self):
        """Return the interactive widget that owns ZONE_CONTENT focus.

        Derived entirely from the active action's ``content_widget_id``.
        No mode-specific branching here — adding a new mode with an interactive
        widget only requires setting ``content_widget_id`` on its NoteAction.
        """
        if self._active_action and self._active_action.content_widget_id:
            try:
                return self.query_one(f"#{self._active_action.content_widget_id}")
            except Exception:
                pass
        return None

    def _enter_zone(self, zone: str) -> None:
        """Transition to a focus zone.

        This is the single entry-point for all zone changes. It handles:
        - Disabling the content widget when leaving ZONE_CONTENT.
        - Re-enabling and focusing the content widget when entering ZONE_CONTENT.
        - Returning focus to the screen for all non-content zones.
        """
        w = self._content_widget
        if zone == _ZONE_CONTENT:
            if w is not None:
                w.disabled = False
                w.focus()
            # For modes without an interactive widget (read, trace), just update state.
            self.focus_zone = _ZONE_CONTENT
        else:
            if w is not None:
                w.disabled = True
            self.focus_zone = zone
            self.focus()
        self.refresh_zones()

    # ------------------------------------------------------------------ #
    #  Navigation actions                                                  #
    # ------------------------------------------------------------------ #

    async def action_nav_up(self) -> None:
        """Up / k — move menu cursor up, or scroll content zone."""
        if self.focus_zone == _ZONE_MENU:
            if self.menu_index > 0:
                self.menu_index -= 1
            else:
                self._enter_zone(_ZONE_MIDDLE)
        elif self.focus_zone == _ZONE_CONTENT:
            # Content widget handles its own scrolling — do not intercept.
            pass
        else:
            self._focus_prev()

    async def action_nav_down(self) -> None:
        """Down / j — move menu cursor down, or scroll content zone."""
        if self.focus_zone == _ZONE_MENU:
            if self.menu_index < len(self.actions) - 1:
                self.menu_index += 1
            else:
                self._enter_zone(_ZONE_TOP)
        elif self.focus_zone == _ZONE_CONTENT:
            pass
        else:
            self._focus_next()

    async def action_nav_left(self) -> None:
        """Left / h / Ctrl+Left — jump to the menu zone from content."""
        if self.focus_zone == _ZONE_CONTENT:
            self._enter_zone(_ZONE_MENU)

    async def action_nav_right(self) -> None:
        """Right / l / Ctrl+Right — jump to the content zone from menu."""
        if self.focus_zone in (_ZONE_MENU, _ZONE_TOP, _ZONE_MIDDLE):
            self._enter_zone(_ZONE_CONTENT)

    async def action_interact(self) -> None:
        """Space — expand/collapse top/middle panels, or activate menu item."""
        if self.focus_zone == _ZONE_TOP:
            self.top_expanded = not self.top_expanded
        elif self.focus_zone == _ZONE_MIDDLE:
            self.middle_expanded = not self.middle_expanded
        elif self.focus_zone == _ZONE_MENU:
            await self.action_select()

    async def action_select(self) -> None:
        """Enter — confirm pending action, or activate the highlighted menu item."""
        # Special case: a confirmation step (e.g. delete) is waiting.
        if self._mode == "delete_confirm":
            if self._active_action and self._active_action.confirm:
                sig = self._active_action.confirm()
                if sig: await self.process_signal(sig)
            return

        if self.focus_zone != _ZONE_MENU or not self.actions:
            return
        action = self.actions[self.menu_index]
        if action.disabled:
            return
        if action.is_mode:
            # Record active action BEFORE calling enter() so _mode is correct
            # when enter() calls _refresh_footer() / refresh_zones().
            self._active_action = action
            action.enter()
        else:
            sig = action.enter()
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

    # Reactive state
    top_expanded: reactive[bool] = reactive(False)
    middle_expanded: reactive[bool] = reactive(False)
    focus_zone: reactive[str] = reactive(_ZONE_TOP)
    menu_index: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    OpenNoteScreen {
        layout: vertical;
        background: transparent;
    }
    #top_panel    { height: auto; }
    #middle_panel { height: auto; }
    #bottom_row   { height: 1fr; }
    #menu_panel   { width: 26; height: 100%; }
    #right_pane   { width: 1fr; height: 100%; }
    #footer       { height: auto; dock: bottom; }

    #content_panel {
        width: 1fr;
        height: 100%;
        border: round #666666;
        padding: 0 1;
    }
    #note_trace_zone {
        width: 1fr;
        height: 100%;
        border: round #666666;
    }
    #note_trace_content { height: auto; padding: 0 1; }
    #note_edit_zone    { width: 1fr; height: 100%; }
    #note_ai_zone      { width: 1fr; height: 100%; }
    """

    def __init__(
        self,
        note,
        arch_badge: str,
        out_links: list,
        in_links: list,
        note_summaries: dict,
    ):
        self._note = note
        self._arch_badge = arch_badge
        self._out_links = out_links
        self._in_links = in_links
        self._note_summaries = note_summaries
        # Actions registered via set_actions() after construction.
        self.actions: List[NoteAction] = []
        # The currently active persistent mode action (None = read/idle).
        self._active_action: Optional[NoteAction] = None
        # Raw trace timeline renderable, stored so the Panel border can be
        # refreshed when the focus zone changes without re-fetching.
        self._trace_content: Optional[RenderableType] = None
        super().__init__()
        self.top_expanded = False
        self.middle_expanded = False
        self.focus_zone = _ZONE_TOP
        self.menu_index = 0

    def set_actions(self, actions: List[NoteAction]) -> None:
        """Register the ordered list of menu actions. Call after construction."""
        self.actions = actions

    # ─── Mode / content-widget resolution ──────────────────────────────────

    @property
    def _mode(self) -> str:
        """Current mode key, derived from the active action."""
        return self._active_action.mode_key if self._active_action else "read"

    def compose(self) -> ComposeResult:
        yield Static(id="top_panel")
        yield Static(id="middle_panel")
        with Horizontal(id="bottom_row"):
            yield Static(id="menu_panel")
            # Single right slot. ContentSwitcher shows exactly one child at a time;
            # all children are mounted once and never destroyed.
            with ContentSwitcher(id="right_pane", initial="content_panel"):
                static = Static(id="content_panel")
                static.can_focus = True
                yield static
                with VerticalScroll(id="note_trace_zone"):
                    yield Static(id="note_trace_content")
                yield MarkdownEditor(
                    title="Edit Note",
                    subtitle="Ctrl+S \u00b7 Esc",
                    id="note_edit_zone",
                    auto_focus=False,
                )
                yield AIEditor(id="note_ai_zone", auto_focus=False)
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
        """Swap footer content based on the active action or hovered menu item."""
        try:
            if self._active_action and self._active_action.footer_view:
                # Active mode provides its own footer.
                renderable = self._active_action.footer_view()
            elif (
                self.focus_zone == _ZONE_MENU
                and self.actions
                and self.menu_index < len(self.actions)
                and self.actions[self.menu_index].hover_footer
            ):
                # Hovered item provides a hover-specific footer (e.g. danger hints).
                hover_fn = self.actions[self.menu_index].hover_footer
                renderable = hover_fn()  # type: ignore[misc]  # narrowed by enclosing `and`
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
        # #content_panel is always in DOM inside ContentSwitcher — always refresh it.
        try:
            self.query_one("#content_panel", Static).update(self._render_content())
            self._update_content_panel_border()
        except Exception:
            pass
        # Refresh trace panel border when focus zone changes.
        if self._mode == "trace":
            try:
                self._update_trace_border()
                self.query_one("#note_trace_content", Static).update(self._render_trace_body())
            except Exception:
                pass
        self._refresh_footer()
    # ------------------------------------------------------------------ #
    #  AI enhance lifecycle                                                #
    # ------------------------------------------------------------------ #

    def _update_content_panel_border(self) -> None:
        """Sync the native Textual border of #content_panel with the current state."""
        try:
            panel = self.query_one("#content_panel")
            is_focused = self.focus_zone == _ZONE_CONTENT and self._mode == "read"
            if self.focus_zone == _ZONE_MENU and self.actions and self.menu_index < len(self.actions):
                action = self.actions[self.menu_index]
                panel.styles.border = ("round", action.hint_color)
                panel.border_title = f"[bold]{action.label}[/bold]"
            elif is_focused:
                panel.styles.border = ("round", "green")
                panel.border_title = "[bold green]Content[/bold green]"
            else:
                panel.styles.border = ("round", "#666666")
                panel.border_title = "[bold dim]Content[/bold dim]"
        except Exception:
            pass

    def _update_trace_border(self) -> None:
        """Sync the native Textual border of #note_trace_zone with the current state."""
        try:
            zone = self.query_one("#note_trace_zone")
            is_focused = self.focus_zone == _ZONE_CONTENT
            if is_focused:
                zone.styles.border = ("round", "green")
                zone.border_title = "[bold green]Trace • Ctrl+← to menu[/bold green]"
            else:
                zone.styles.border = ("round", "cyan")
                zone.border_title = "[bold cyan]Trace[/bold cyan]"
        except Exception:
            pass

    def _switch_right_pane(self, widget_id: str) -> None:
        """Show one child of the right-pane ContentSwitcher."""
        try:
            self.query_one("#right_pane", ContentSwitcher).current = widget_id
        except Exception:
            pass

    def _enter_ai_enhance(self) -> None:
        """Switch the right pane to the AI editor and populate it with current note text."""
        note_text = getattr(self._note, "content", "") or ""
        ai = self.query_one("#note_ai_zone", AIEditor)
        ai.set_original(note_text)
        # Clear any previous result so the pane starts fresh.
        try:
            ai.query_one("#ai_result_content", Static).update("")
            ai.query_one("#ai_result").border_title = "[bold dim]Result[/bold dim]"
        except Exception:
            pass
        self._switch_right_pane("note_ai_zone")
        self._enter_zone(_ZONE_CONTENT)
        self._refresh_footer()

    def _leave_ai_enhance(self) -> None:
        """Return the right pane to the static content view."""
        self._active_action = None
        self._switch_right_pane("content_panel")
        self.focus_zone = _ZONE_MENU
        self.focus()
        self.refresh_zones()
        self._refresh_footer()

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
        """AI enhancement in a background thread using the professional professional workflow."""
        try:
            from src.cli.client.http_client import ConcepTrackerClient
            with ConcepTrackerClient() as client:
                # Rule 2: Exclusively via REST API. 
                # This now calls the professional enhancement endpoint
                # which uses the enhancement_workflow (RAG + Professional Refactor).
                result = client.enhance_note(
                    note_id=self._note.id, 
                    user_instruction=prompt or "Professional refactor and cleanup"
                )
            # result is a NoteResponse from the backend
            self.app.call_from_thread(self._on_ai_done, result.content)
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

    # ------------------------------------------------------------------ #    #  Trace-mode lifecycle                                                #
    # ------------------------------------------------------------------ #

    def _enter_trace(self) -> None:
        """Switch the right pane to the trace view and start the background worker."""
        self._trace_content = None
        self._switch_right_pane("note_trace_zone")
        self._update_trace_border()
        self.query_one("#note_trace_content", Static).update(self._render_trace_body())
        self._enter_zone(_ZONE_CONTENT)
        self._refresh_footer()
        self._run_trace_worker()

    def _leave_trace(self) -> None:
        """Return the right pane to the static content view."""
        self._active_action = None
        self._trace_content = None
        self._switch_right_pane("content_panel")
        self.focus_zone = _ZONE_MENU
        self.focus()
        self.refresh_zones()
        self._refresh_footer()

    @work(thread=True, exclusive=True)
    def _run_trace_worker(self) -> None:
        """Background thread to perform semantic search and link mapping for concepts."""
        try:
            # 1. Determine concept
            concept = ""
            if self._note.tags:
                tags = [t.strip() for t in self._note.tags.replace(',', ' ').split() if t.strip()]
                if tags:
                    concept = tags[0]
            if not concept:
                concept = self._note.summary or "concept"

            # 2. Fetch data
            with ConcepTrackerClient() as client:
                response = client.search(query=concept, limit=10)
                note_ids = [r.id for r in response.results]
                
                # Fetch full note data for created_at
                notes = sorted(
                    [client.get_note(nid) for nid in note_ids],
                    key=lambda n: n.created_at,
                )

                # Trace links for the subset
                links_by_source: dict[int, list] = {}
                for note in notes:
                    all_links = client.get_links_for_note(note.id)
                    links_by_source[note.id] = [lnk for lnk in all_links if lnk.source_id == note.id]

            def _get_links(note_id: int):
                return links_by_source.get(note_id, [])

            # 3. Render
            renderable = render_trace_timeline(concept, notes, note_ids, _get_links)
            self.app.call_from_thread(self._on_trace_ready, renderable)

        except Exception as e:
            self.app.call_from_thread(self._on_trace_error, str(e))

    def _on_trace_ready(self, renderable: RenderableType) -> None:
        self._trace_content = renderable
        self.query_one("#note_trace_content", Static).update(self._render_trace_body())

    def _on_trace_error(self, error_msg: str) -> None:
        self._trace_content = Text(f"Error: {error_msg}", style="bold red")
        self.query_one("#note_trace_content", Static).update(self._render_trace_body())
        self.notify(f"Trace failed: {error_msg}", severity="error")

    def _render_trace_body(self) -> RenderableType:
        """Return the raw trace body without Panel wrapper (border is handled by CSS)."""
        return self._trace_content or Text("Loading trace...", style="dim italic")

    def _render_trace_panel(self) -> RenderableType:
        """Deprecated wrapper kept to avoid breaking any residual calls."""
        return self._render_trace_body()

    # ------------------------------------------------------------------ #    #  Edit-mode lifecycle                                                 #
    # ------------------------------------------------------------------ #

    def _enter_note_edit(self) -> None:
        """Switch the right pane to the Markdown editor and load the current note text."""
        note_text = getattr(self._note, "content", "") or ""
        self.query_one("#note_edit_zone", MarkdownEditor).load_text(note_text)
        self._switch_right_pane("note_edit_zone")
        self._enter_zone(_ZONE_CONTENT)
        self._refresh_footer()
        self.query_one("#menu_panel", Static).update(self._render_menu())

    def _mode_transition_to_read(self) -> None:
        """Return the right pane to the static content view after editing."""
        self._active_action = None
        self._switch_right_pane("content_panel")
        self.focus_zone = _ZONE_MENU
        self.focus()
        self.refresh_zones()
        self._refresh_footer()

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
        for i, action in enumerate(self.actions):
            is_selected = i == self.menu_index
            is_active_cursor = is_zone_focused and is_selected
            is_active_mode = self._active_action is action
            bullet = "●" if (is_active_cursor or is_active_mode) else "○"
            if is_active_cursor:
                row = Text(f" {bullet} {action.label}", style="bold black on green")
            elif is_active_mode:
                # Mode is running but cursor is elsewhere — highlight in colour.
                row = Text(f" {bullet} {action.label}", style=f"bold {action.hint_color}")
            elif is_selected:
                row = Text(f" {bullet} {action.label}", style="green")
            elif action.disabled:
                row = Text(f" {bullet} {action.label}", style="dim")
            else:
                row = Text(f" {bullet} {action.label}", style="white")
            items.append(row)

        if not items:
            items.append(Text("  (empty)", style="dim"))

        border = "green" if is_zone_focused else "dim"
        menu_title = "[bold green]Actions[/bold green]" if is_zone_focused else "[bold dim]Actions[/bold dim]"
        return Panel(Group(*items), title=menu_title, border_style=border)

    def _render_content(self) -> RenderableType:
        """Return the body for #content_panel (border handled by Textual CSS)."""
        if self.focus_zone == _ZONE_MENU and self.actions and self.menu_index < len(self.actions):
            return Text.from_markup(self.actions[self.menu_index].hint_text)
        return Text("Navigate to Actions and press Enter.", style="dim italic")

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
        """Show delete-confirmation panel in the content area."""
        self._switch_right_pane("content_panel")
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
        """Cancel delete and return to idle read state."""
        self._active_action = None
        self.refresh_zones()
        self._refresh_footer()
