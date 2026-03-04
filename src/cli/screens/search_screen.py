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

from src.cli.screen import AppScreen, SCREEN_EXIT, ScreenSignal
from src.cli.screens.pager import _TablePagerScreen
from src.cli.views import note_card_view, note_find_table_view
from src.cli.client.http_client import ConcepTrackerClient
from src.cli.views.arch_views import archipelago_badge


# Re-use views from interactors
def _build_preview_for_find(item, arch_cache):
    note, score = item
    # score is a relevance value in [0, 1] where 1 = most relevant.
    percentage = max(0, min(100, int(score * 100)))
    color = "green" if percentage > 70 else "yellow"
    title = f"[{color} bold]Preview: Note #{note.id} ({percentage}% Match)[/{color} bold]"
    return note_card_view(
        note,
        arch_badge=arch_cache.get(note.archipelago_id, "[dim]~island~[/dim]"),
        title=title,
        border_style="dim",
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
            border_style="dim"
        )
        self.query_one("#search_status", Static).update(status)

        try:
            # 2. Run hybrid search via API.
            client = ConcepTrackerClient()
            response = await asyncio.to_thread(client.search, self._query, self.limit)

            if not response.results:
                self.query_one("#search_status", Static).update(
                    Panel("[yellow]No similar concepts found.[/yellow]", border_style="yellow")
                )
                await asyncio.sleep(2)
                await self.process_signal(SCREEN_EXIT)
                return

            # 3. Fetch full Note objects to preserve all fields (e.g. created_at).
            result_ids = [r.id for r in response.results]
            score_by_id = {r.id: r.score or 0.0 for r in response.results}
            notes = await asyncio.gather(*[
                asyncio.to_thread(client.get_note, nid) for nid in result_ids
            ])
            notes_by_id = {n.id: n for n in notes}
            self._results = [
                (notes_by_id[nid], score_by_id[nid])
                for nid in result_ids
                if nid in notes_by_id
            ]

            if not self._results:
                self.query_one("#search_status", Static).update(
                    Panel("[yellow]No similar concepts found.[/yellow]", border_style="yellow")
                )
                await asyncio.sleep(2)
                await self.process_signal(SCREEN_EXIT)
                return

            # 4. Build arch_cache via API.
            arch_ids = {
                note.archipelago_id
                for note, _ in self._results
                if note.archipelago_id
            }
            arch_cache: Dict[int, str] = {}
            for arch_id in arch_ids:
                try:
                    arch = await asyncio.to_thread(client.get_archipelago, arch_id)
                    arch_cache[arch_id] = archipelago_badge(arch.name, arch.type)
                except Exception:
                    arch_cache[arch_id] = "[dim]~island~[/dim]"

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

    def handle_action(self, key: str) -> ScreenSignal:
        """Escape exits during search."""
        if key == "escape":
            return SCREEN_EXIT
        return None
