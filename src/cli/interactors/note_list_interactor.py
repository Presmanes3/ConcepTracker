"""Note list interactor — orchestrate the `ls` command flow via REST API.

Flow:
  1. Fetch notes (with optional tag / archipelago filters) via http_client.
  2. Pre-resolve archipelago labels into a local badge cache.
  3. Open the pager screen, wiring view functions with the resolved data.
  4. On note selection, open OpenNoteInteractor and loop back.
"""
from __future__ import annotations

from typing import Dict, Optional

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.screens.pager import paginate_table
from src.cli.views import note_card_view, note_list_table_view, prefetch_arch_cache


class _ArchRepoAdapter:
    """Minimal duck-type shim for prefetch_arch_cache backed by a local dict."""

    def __init__(self, arch_map: Dict) -> None:
        self._arch_map = arch_map

    def get_archipelago_by_id(self, arch_id: int):
        return self._arch_map.get(arch_id)


class NoteListInteractor:
    """Fetch notes and archipelago data via the REST API, then open the pager."""

    def __init__(
        self,
        tag: Optional[str] = None,
        limit: int = 100,
        archipelago: Optional[str] = None,
        page_size: int = 10,
    ) -> None:
        self.tag = tag
        self.fetch_limit = limit if limit > 0 else 200
        self.archipelago = archipelago
        self.page_size = page_size

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Run the note list and open the interactive pager.

        Raises:
            ValueError: When the filter matches nothing or the result set is empty.
        """
        from src.cli.interactors.open_note_interactor import OpenNoteInteractor

        # We need a shared state for the closures to update after a refresh
        class PagerData:
            current_notes = []
            current_cache = {}

        def refresh_data():
            """Fetch fresh notes and archipelagos from the server."""
            with ConcepTrackerClient() as client:
                new_notes, new_cache = self._fetch(client)
            PagerData.current_notes = new_notes
            PagerData.current_cache = new_cache
            return new_notes, new_cache

        # Initial fetch to populate PagerData before starting the pager
        notes, arch_cache = refresh_data()

        if notes is None:
            raise ValueError(
                f"[yellow]No archipelago matching '{self.archipelago}' found.[/yellow]"
            )
        if not notes:
            raise ValueError("[yellow]No notes found.[/yellow]")

        paginate_table(
            notes,
            build_table=lambda chunk, cursor, start, expanded: note_list_table_view(
                chunk, cursor, start, expanded, PagerData.current_cache, len(PagerData.current_notes)
            ),
            page_size=self.page_size,
            build_preview=lambda note: note_card_view(
                note,
                arch_badge=PagerData.current_cache.get(note.archipelago_id, "[dim]~island~[/dim]"),
            ),
            on_select=lambda note: OpenNoteInteractor(note.id).build_screen(),
            on_refresh=refresh_data,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _fetch(self, client: ConcepTrackerClient):
        """Fetch notes and build the archipelago badge cache.

        Returns:
            Tuple of (notes | None, arch_cache). notes is None when an archipelago
            name filter matches nothing (sentinel for the caller to bail out).
        """
        notes = client.list_notes(limit=self.fetch_limit, tag=self.tag)

        if self.archipelago:
            all_archs = client.list_archipelagos()
            matching = [a for a in all_archs if self.archipelago.lower() in a.name.lower()]
            if not matching:
                return None, {}
            valid_ids = {a.id for a in matching}
            notes = [n for n in notes if n.archipelago_id in valid_ids]

        all_archs = client.list_archipelagos()
        arch_map = {a.id: a for a in all_archs}
        arch_cache = prefetch_arch_cache(notes, _ArchRepoAdapter(arch_map))

        return notes, arch_cache
