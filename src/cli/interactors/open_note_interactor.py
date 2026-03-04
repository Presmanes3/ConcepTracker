"""Open Note Interactor — fetch note data via REST API and display OpenNoteScreen."""
from __future__ import annotations

from typing import Optional

from rich.console import Console

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.screen import SCREEN_EXIT, run_screen
from src.cli.screens.note_actions import NoteAction
from src.cli.screens.open_note_screen import OpenNoteScreen
from src.cli.views.arch_views import archipelago_badge
from src.cli.views.open_note_views import (
    open_note_ai_footer,
    open_note_delete_footer,
    open_note_delete_hint_panel,
    open_note_edit_footer,
    open_note_trace_footer,
)

console = Console()


class OpenNoteInteractor:
    """Fetch a note and its connections via the REST API, then open the note screen."""

    def __init__(self, note_id: int) -> None:
        self._note_id = note_id

    def run(self) -> None:
        """Open the note screen. Blocks until the user quits."""
        screen = self.build_screen()
        if screen is None:
            return
        run_screen(screen)

    def build_screen(self) -> Optional[OpenNoteScreen]:
        """Fetch note data and return a ready-to-push OpenNoteScreen (no run_screen)."""
        with ConcepTrackerClient() as client:
            try:
                note = client.get_note(self._note_id)
            except Exception:
                console.print(f"[red]Note {self._note_id} not found.[/red]")
                return None

            all_links = client.get_links_for_note(self._note_id)
            out_links = [lnk for lnk in all_links if lnk.source_id == self._note_id]
            in_links  = [lnk for lnk in all_links if lnk.target_id == self._note_id]

            # Fetch summaries for connected notes
            note_summaries: dict[int, str] = {}
            for lnk in out_links:
                try:
                    target = client.get_note(lnk.target_id)
                    note_summaries[lnk.target_id] = target.summary
                except Exception:
                    pass
            for lnk in in_links:
                try:
                    source = client.get_note(lnk.source_id)
                    note_summaries[lnk.source_id] = source.summary
                except Exception:
                    pass

            badge = self._resolve_badge(client, note)

        # ── Build screen ────────────────────────────────────────────────────────
        screen = OpenNoteScreen(
            note=note,
            arch_badge=badge,
            out_links=out_links,
            in_links=in_links,
            note_summaries=note_summaries,
        )

        # ── Register actions (Strategy pattern) ─────────────────────────────────
        # Each NoteAction is a self-contained descriptor. To add a new mode in the
        # future, append a NoteAction here — no other code needs to change.
        note_id_captured = self._note_id

        def _delete_note():
            with ConcepTrackerClient() as del_client:
                del_client.delete_note(note_id_captured)
            return SCREEN_EXIT

        actions = [
            NoteAction(
                label="Edit Note",
                hint_color="green",
                hint_text="Open the note in the editor to modify its content.",
                mode_key="edit",
                content_widget_id="editor_textarea",
                enter=screen._enter_note_edit,
                leave=screen._leave_note_edit,
                footer_view=open_note_edit_footer,
            ),
            NoteAction(
                label="AI",
                hint_color="magenta",
                hint_text="Invoke AI utility to refactor, translate or enhance using RAG context.",
                mode_key="ai",
                content_widget_id="ai_prompt",
                enter=screen._enter_ai_enhance,
                leave=screen._leave_ai_enhance,
                footer_view=open_note_ai_footer,
            ),
            NoteAction(
                label="Trace",
                hint_color="cyan",
                hint_text="Visualise the chronological evolution of this concept.",
                mode_key="trace",
                enter=screen._enter_trace,
                leave=screen._leave_trace,
                footer_view=open_note_trace_footer,
            ),
            NoteAction(
                label="Manage Tags",
                hint_color="yellow",
                hint_text="Add, remove or rename tags on this note.",
                disabled=True,
            ),
            NoteAction(
                label="Manage Links",
                hint_color="blue",
                hint_text="Add or remove connections to other notes.",
                disabled=True,
            ),
            NoteAction(
                label="Delete",
                hint_color="red",
                hint_text="[bold red]Permanently delete this note and all its links.[/bold red]",
                mode_key="delete_confirm",
                enter=screen._enter_delete_confirm,
                leave=screen._leave_delete_confirm,
                confirm=_delete_note,
                footer_view=open_note_delete_footer,
                hover_footer=open_note_delete_hint_panel,
            ),
        ]
        screen.set_actions(actions)
        return screen

    # ── Private helpers ────────────────────────────────────────────────────────

    def _resolve_badge(self, client: ConcepTrackerClient, note) -> str:
        if not note.archipelago_id:
            return "[dim]~island~[/dim]"
        try:
            arch = client.get_archipelago(note.archipelago_id)
            return archipelago_badge(arch.name, arch.type)
        except Exception:
            return f"[dim]Archipelago {note.archipelago_id}[/dim]"
