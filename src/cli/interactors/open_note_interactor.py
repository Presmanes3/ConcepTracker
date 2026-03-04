"""Open Note Interactor — fetch note data via REST API and display OpenNoteScreen."""
from __future__ import annotations

from typing import Optional

from rich.console import Console

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.screen import SCREEN_EXIT, run_screen
from src.cli.screens.open_note_screen import OpenNoteScreen
from src.cli.views.arch_views import archipelago_badge

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

        note_id_captured = self._note_id

        def _delete_note():
            with ConcepTrackerClient() as del_client:
                del_client.delete_note(note_id_captured)
            return SCREEN_EXIT

        menu_items = [
            ("Edit Note",    lambda: None),
            ("AI",           lambda: None),
            ("Trace",        lambda: None),
            ("Manage Tags",  lambda: None),
            ("Manage Links", lambda: None),
            ("Delete",       _delete_note),
        ]

        return OpenNoteScreen(
            note=note,
            arch_badge=badge,
            out_links=out_links,
            in_links=in_links,
            note_summaries=note_summaries,
            menu_items=menu_items,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _resolve_badge(self, client: ConcepTrackerClient, note) -> str:
        if not note.archipelago_id:
            return "[dim]~island~[/dim]"
        try:
            arch = client.get_archipelago(note.archipelago_id)
            return archipelago_badge(arch.name, arch.type)
        except Exception:
            return f"[dim]Archipelago {note.archipelago_id}[/dim]"
