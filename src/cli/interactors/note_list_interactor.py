"""
src/cli/interactors/note_list_interactor.py

Orchestrates the `ls` command flow:
  1. Fetch notes (with optional tag / archipelago filters).
  2. Pre-resolve archipelago labels into a local cache.
  3. Open the pager screen, wiring view functions with the resolved data.
  4. On note selection, open OpenNoteInteractor and loop back.

No Rich Layout, no console.print() — only data fetching + screen/view calls.
"""
from __future__ import annotations

from src.cli.screens.pager import paginate_table
from src.cli.views import note_card_view, note_list_table_view, prefetch_arch_cache
from src.registry import repos


class NoteListInteractor:
    def __init__(
        self,
        tag: str | None = None,
        limit: int = 100,
        archipelago: str | None = None,
        page_size: int = 10,
    ) -> None:
        self.tag = tag
        self.fetch_limit = limit if limit > 0 else 9999
        self.archipelago = archipelago
        self.page_size = page_size

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Run the note list. The pager handles note selection internally via on_select.
        Raises ValueError when filter matches nothing or result set is empty.
        """
        notes = self._fetch_notes()

        if notes is None:
            raise ValueError(
                f"[yellow]No archipelago matching '{self.archipelago}' found.[/yellow]"
            )

        if not notes:
            raise ValueError("[yellow]No notes found.[/yellow]")

        from src.cli.interactors.open_note_interactor import OpenNoteInteractor
        arch_cache = prefetch_arch_cache(notes, repos.archipelagos)

        paginate_table(
            notes,
            build_table=lambda chunk, cursor, start, expanded: note_list_table_view(
                chunk, cursor, start, expanded, arch_cache, len(notes)
            ),
            page_size=self.page_size,
            build_preview=lambda note: note_card_view(
                note,
                arch_badge=arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]"),
            ),
            on_select=lambda note: OpenNoteInteractor(note.id).build_screen(),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_notes(self) -> list | None:
        """
        Fetch notes from the repository and apply optional filters.
        Returns None when an archipelago filter matches nothing (signals
        the caller to bail out with a warning message).
        """
        notes = repos.notes.get_all_notes(limit=self.fetch_limit, tag=self.tag)

        if self.archipelago:
            all_archs = repos.archipelagos.get_all_archipelagos()
            matching = [
                a for a in all_archs
                if self.archipelago.lower() in a.name.lower()
            ]
            if not matching:
                return None  # sentinel: no matching archipelago
            valid_ids = {a.id for a in matching}
            notes = [n for n in notes if n.archipelago_id in valid_ids]

        return notes
