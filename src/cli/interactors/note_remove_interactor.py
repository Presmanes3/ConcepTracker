"""Note remove interactor — search for a note and delete it."""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.views import render_delete_confirmation, render_delete_selection_table

console = Console()


class NoteRemoveInteractor:
    """Resolve a note by ID or search query, confirm, then delete via API."""

    def __init__(
        self,
        note_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> None:
        self._note_id = note_id
        self._search = search

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Run the remove flow."""
        with ConcepTrackerClient() as client:
            note_id = self._resolve_note_id(client)
            if note_id is None:
                return

            note = self._get_note(client, note_id)
            if note is None:
                return

            console.print(render_delete_confirmation(note))

            if Confirm.ask("Are you sure?", default=False):
                client.delete_note(note_id)
                console.print(
                    f"\n✅ [bold green]Concept {note_id} has been erased from your brain.[/bold green]"
                )
            else:
                console.print("[dim]Deletion aborted. Your memory remains intact.[/dim]")

    # ── Private helpers ────────────────────────────────────────────────────────

    def _resolve_note_id(self, client: ConcepTrackerClient) -> Optional[int]:
        if self._note_id is not None:
            return self._note_id

        if self._search:
            with console.status(f"[cyan]Searching for '{self._search}'…[/cyan]"):
                response = client.search(query=self._search, limit=5)
            notes_data = response.results
            if not notes_data:
                console.print("[yellow]No notes found matching your criteria.[/yellow]")
                return None
            # Adapt SearchResultItem to duck-type the view (needs .id, .summary, .created_at)
            # The view only uses .id, .summary, .created_at — SearchResultItem has id and summary
            # but no created_at. Fetch full notes for display.
            ids = [r.id for r in notes_data]
            notes = [client.get_note(nid) for nid in ids]
        else:
            notes = client.list_notes(limit=10)

        if not notes:
            console.print("[yellow]No notes found.[/yellow]")
            return None

        console.print(render_delete_selection_table(notes))

        note_id_str = Prompt.ask("\n[bold red]Enter the ID to delete[/bold red]", default="")
        if not note_id_str:
            console.print("[dim]Action cancelled.[/dim]")
            return None
        try:
            return int(note_id_str)
        except ValueError:
            console.print("[red]Invalid ID format.[/red]")
            return None

    def _get_note(self, client: ConcepTrackerClient, note_id: int):
        try:
            return client.get_note(note_id)
        except Exception:
            console.print(f"[red]Note with ID {note_id} not found.[/red]")
            return None
