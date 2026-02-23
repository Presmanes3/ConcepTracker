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

from src.cli.screen import run_screen


class NoteFindInteractor:
    def __init__(
        self,
        query: str,
        limit: int = 10,
        page_size: int = 10,
        status_context=None,  # kept for backward compat, unused
    ) -> None:
        self.query = query
        self.limit = limit
        self.page_size = page_size

    def run(self) -> None:
        """
        Run the find flow: show search screen, which internally handles
        the pager and note opening in a single Textual session.
        """
        from src.cli.screens.search_screen import SemanticSearchScreen
        run_screen(SemanticSearchScreen(
            query=self.query,
            limit=self.limit,
            page_size=self.page_size,
        ))
