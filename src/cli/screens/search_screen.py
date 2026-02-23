"""
src/cli/screens/search_screen.py

A simple screen that displays "Searching..." status while performing
semantic results fetching, then transitions to the pager.
"""
from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Tuple

from rich.align import Align
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from src.cli.screen import AppScreen, SCREEN_EXIT
from src.cli.screens.pager import _TablePagerScreen
from src.cli.views import note_card_view, note_find_table_view, prefetch_arch_cache
from src.registry import repos
from src.services.embedding_service import embedding_service


# Re-use views from interactors
def _build_preview_for_find(item, arch_cache):
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


class SemanticSearchScreen(AppScreen):
    """
    Handles the async phase of semantic search before displaying the results.
    """

    def __init__(
        self,
        query: str,
        limit: int = 10,
        page_size: int = 10,
    ) -> None:
        super().__init__()
        self._query = query
        self.limit = limit
        self.page_size = page_size
        self._results: List[Tuple[Any, float]] = []

    def compose(self) -> ComposeResult:
        yield Static(id="search_status")

    def on_mount(self) -> None:
        super().on_mount()
        # Perform the search in the background so the UI doesn't freeze
        self.run_worker(self._perform_search())

    async def _perform_search(self) -> None:
        # 1. Show status
        status = Panel(
            Align.center(
                Text.from_markup(f"[cyan]Searching for [bold]'{self._query}'[/bold]...[/cyan]"),
                vertical="middle"
            ),
            border_style="cyan"
        )
        self.query_one("#search_status", Static).update(status)

        try:
            # 2. Fetch Embedding
            vector = await asyncio.to_thread(embedding_service.get_embedding, self._query)
            
            # 3. Perform Search
            self._results = await asyncio.to_thread(
                repos.notes.semantic_search, vector, limit=self.limit
            )

            if not self._results:
                self.query_one("#search_status", Static).update(
                    Panel("[yellow]No similar concepts found.[/yellow]", border_style="yellow")
                )
                await asyncio.sleep(2)
                await self.process_signal(SCREEN_EXIT)
                return

            # 4. Resolve Cache
            notes = [r[0] for r in self._results]
            arch_cache = await asyncio.to_thread(prefetch_arch_cache, notes, repos.archipelagos)

            # 5. Transition to Pager — stays in the same Textual session.
            # on_select handles opening notes inline (no new run_screen).
            from src.cli.interactors.open_note_interactor import OpenNoteInteractor

            pager_screen = _TablePagerScreen(
                self._results,
                build_table_fn=lambda chunk, cursor, start, expanded: note_find_table_view(
                    chunk, cursor, start, expanded, arch_cache, self._query, len(self._results)
                ),
                page_size=self.page_size,
                header=None,
                build_preview=lambda item: _build_preview_for_find(item, arch_cache),
                on_select=lambda item: OpenNoteInteractor(item[0].id).build_screen(),
            )

            # When the pager is dismissed (user presses Escape), exit the whole app.
            def _on_pager_done(_: Any) -> None:
                self.app.exit(result=None)

            self.app.push_screen(pager_screen, callback=_on_pager_done)

        except Exception as exc:
            self.query_one("#search_status", Static).update(
                Panel(f"[red]Search error: {exc}[/red]", border_style="red")
            )
            await asyncio.sleep(3)
            await self.process_signal(SCREEN_EXIT)

    def handle_action(self, key: str) -> None:
        """Escape exits during search."""
        if key == "escape":
            return SCREEN_EXIT
        return None
