"""Note trace interactor — trace the chronological evolution of a concept."""
from __future__ import annotations

from rich.console import Console

from src.cli.client.http_client import ConcepTrackerClient
from src.cli.views import render_trace_timeline

console = Console()


class NoteTraceInteractor:
    """Search for concept-related notes and render a chronological timeline."""

    def __init__(self, concept: str, threshold: float = 0.85) -> None:
        self._concept = concept
        self._threshold = threshold

    def run(self) -> None:
        """Fetch related notes and their links, then render the timeline."""
        console.print(f"[bold magenta]Tracing: {self._concept}[/bold magenta]")

        with ConcepTrackerClient() as client:
            response = client.search(query=self._concept, limit=10)
            note_ids = [r.id for r in response.results]

            # Fetch full note data sorted by creation date
            notes = sorted(
                [client.get_note(nid) for nid in note_ids],
                key=lambda n: n.created_at,
            )

            # Pre-fetch all outgoing links indexed by source note ID
            links_by_source: dict = {}
            for note in notes:
                all_links = client.get_links_for_note(note.id)
                links_by_source[note.id] = [
                    lnk for lnk in all_links if lnk.source_id == note.id
                ]

        def _get_links_by_source(note_id: int):
            return links_by_source.get(note_id, [])

        console.print(
            render_trace_timeline(self._concept, notes, note_ids, _get_links_by_source)
        )
