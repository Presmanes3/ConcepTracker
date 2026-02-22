"""
src/cli/interactors/note_find_interactor.py

Orchestrates the `find` command flow:
  1. Generate embedding for the query.
  2. Fetch semantic search results.
  3. Pre-resolve archipelago labels into a local cache.
  4. Open the pager screen, wiring view functions with the resolved data.
  5. On note selection, open OpenNoteInteractor and loop back.

No Rich Layout, no console.print() — only data fetching + screen/view calls.
"""
from __future__ import annotations

from typing import Callable, ContextManager
import contextlib

from src.cli.screens.pager import paginate_table
from src.cli.views import note_card_view, note_find_table_view, prefetch_arch_cache
from src.registry import repos
from src.services.embedding_service import embedding_service



class NoteFindInteractor:
    def __init__(
        self,
        query: str,
        limit: int = 10,
        page_size: int = 10,
        status_context: Callable[[str], ContextManager] | None = None,
    ) -> None:
        self.query = query
        self.limit = limit
        self.page_size = page_size
        self.status_context = status_context or (lambda msg: contextlib.nullcontext())

    def run(self) -> None:
        """
        Run the find → select → menu loop until the user quits.

        Raises
        ------
        ValueError
            With a Rich-markup message when no results are found.
        """
        while True:
            with self.status_context(f"[cyan]Searching for '{self.query}'...[/cyan]"):
                vector = embedding_service.get_embedding(self.query)
                results = repos.notes.semantic_search(vector, limit=self.limit)

            if not results:
                raise ValueError("[yellow]No similar concepts found.[/yellow]")

            # Pre-resolve archipelago badges
            # results is a list of tuples: (Note, distance)
            notes = [r[0] for r in results]
            arch_cache = prefetch_arch_cache(notes, repos.archipelagos)

            def build_table(chunk, cursor_index, start_idx, expanded_states):
                return note_find_table_view(
                    chunk, cursor_index, start_idx, expanded_states, arch_cache, self.query, len(results)
                )

            def build_preview(item):
                note, distance = item
                percentage = max(0, min(100, int((1 - distance) * 100)))
                color = "green" if percentage > 70 else "yellow"
                title = f"[{color} bold]Preview: Note #{note.id} ({percentage}% Match)[/{color} bold]"
                return note_card_view(
                    note,
                    arch_badge=arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]"),
                    title=title,
                    border_style=color,
                )

            selected_item = paginate_table(
                results,
                build_table,
                page_size=self.page_size,
                build_preview=build_preview,
            )

            if selected_item is None:
                break  # user quit the pager

            note, _ = selected_item

            from src.cli.interactors.open_note_interactor import OpenNoteInteractor
            OpenNoteInteractor(note_id=note.id).run()
