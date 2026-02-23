"""
Open Note Interactor — Orchestrates fetching note data and displaying the OpenNoteScreen.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from rich.console import Console

from src.cli.screens.open_note_screen import OpenNoteScreen
from src.cli.screen import run_screen, SCREEN_EXIT
from src.cli.views.open_note_views import open_note_actions_panel
from src.cli.views.arch_views import archipelago_badge
from src.registry import repos

if TYPE_CHECKING:
    from shared.schemas.models.note import Note

console = Console()

class OpenNoteInteractor:
    """
    Interactive screen for viewing a single note and its connections.
    """

    def __init__(
        self,
        note_id: int,
        note_repo=None,
        link_repo=None,
        arch_repo=None,
    ):
        self._note_id = note_id
        self._note_repo = note_repo or repos.notes
        self._link_repo = link_repo or repos.links
        self._arch_repo = arch_repo or repos.archipelagos

        self._note: Optional["Note"] = None

    def run(self) -> None:
        """Open the note screen. Blocks until the user quits."""
        screen = self.build_screen()
        if screen is None:
            return
        run_screen(screen)

    def build_screen(self):
        """Fetch note data and return a ready-to-push OpenNoteScreen (no run_screen)."""
        self._note = self._note_repo.get_note_by_id(self._note_id)
        if not self._note:
            console.print(f"[red]Note {self._note_id} not found.[/red]")
            return None

        # Fetch connections
        out_links = self._link_repo.get_links_by_source(self._note_id)
        in_links = self._link_repo.get_links_by_target(self._note_id)

        # Fetch summaries for connected notes
        note_summaries: dict[int, str] = {}
        for link in out_links:
            target_note = self._note_repo.get_note_by_id(link.target_id)
            if target_note:
                note_summaries[link.target_id] = target_note.summary
        for link in in_links:
            source_note = self._note_repo.get_note_by_id(link.source_id)
            if source_note:
                note_summaries[link.source_id] = source_note.summary

        badge = self._resolve_badge()
        actions_renderable = open_note_actions_panel()

        menu_items = [
            ("🔙 Back", lambda: SCREEN_EXIT),
        ]

        return OpenNoteScreen(
            note=self._note,
            arch_badge=badge,
            out_links=out_links,
            in_links=in_links,
            note_summaries=note_summaries,
            actions_renderable=actions_renderable,
            menu_items=menu_items,
        )

    def _resolve_badge(self) -> str:
        if not self._note.archipelago_id:
            return "[dim]~island~[/dim]"
        arch = self._arch_repo.get_archipelago_by_id(self._note.archipelago_id)
        if not arch:
            return f"[dim]Archipelago {self._note.archipelago_id}[/dim]"
        return archipelago_badge(arch.id, arch.name)
