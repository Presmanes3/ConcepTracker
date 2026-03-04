"""Add note interactor — orchestrates ingest + optional near-miss link review."""
from __future__ import annotations

from typing import List, Optional

import questionary
from rich.console import Console
from rich.table import Table

from shared.schemas.api.links import LinkConfirmRequest
from shared.schemas.api.notes import NoteIngestResponse
from src.cli.client.http_client import ConcepTrackerClient
from src.cli.views import render_ingest_result

console = Console()


class AddInteractor:
    """Ingest a note and optionally run interactive near-miss link review."""

    def __init__(
        self,
        content: str,
        tag: Optional[str] = None,
        review: bool = False,
    ) -> None:
        self._content = content
        self._tag = tag
        self._review = review

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        """Ingest the note and optionally review near-miss link candidates."""
        with ConcepTrackerClient() as client:
            with console.status("[cyan]Processing concept… (Gatekeeping & Linking)[/cyan]"):
                result: NoteIngestResponse = client.ingest_note(
                    content=self._content,
                    source_type="manual" if not self._tag else "manual",
                )
                stats = client.get_stats()

            cost_str = (
                f"[dim italic]Inference: {stats.total_tokens:,} tokens"
                f" (I:{stats.prompt_tokens:,} | O:{stats.completion_tokens:,})[/dim italic]"
            )

            # Build helpers that need the client in scope
            def _get_note_summary(note_id: int) -> Optional[str]:
                try:
                    return client.get_note(note_id).summary
                except Exception:
                    return None

            def _count_arch_notes(arch_id: int) -> int:
                # Approximate: count notes in the archipelago from the list endpoint
                try:
                    notes = client.list_notes(limit=200)
                    return sum(1 for n in notes if n.archipelago_id == arch_id)
                except Exception:
                    return 0

            result_dict = result.model_dump()

            console.print(render_ingest_result(
                result_dict,
                cost_str,
                get_note_summary_func=_get_note_summary,
                count_archipelago_func=_count_arch_notes,
            ))

            if self._review and result.note_id:
                confirmed = self._interactive_link_review(result, client)
                if confirmed:
                    client.confirm_links(result.note_id, confirmed)

    # ── Private helpers ────────────────────────────────────────────────────────

    def _interactive_link_review(
        self,
        result: NoteIngestResponse,
        client: ConcepTrackerClient,
    ) -> List[LinkConfirmRequest]:
        """Present near-miss candidates and return confirmed link requests."""
        near_misses = result.near_miss_candidates
        if not near_misses:
            console.print("[dim]No near-miss candidates to review.[/dim]")
            return []

        table = Table(
            title="[bold cyan]Near-miss Link Candidates[/bold cyan]",
            show_header=True,
            header_style="bold",
            border_style="dim",
            show_lines=True,
        )
        table.add_column("ID", style="cyan", width=6, justify="right")
        table.add_column("Summary", min_width=40, max_width=58)
        table.add_column("Score", width=7, justify="right")

        for nm in near_misses:
            table.add_row(
                str(nm.note_id),
                (nm.summary or f"Note {nm.note_id}")[:58],
                f"{nm.score:.2f}",
            )

        console.print(table)

        choices = [
            questionary.Choice(
                title=f"[{nm.score:.2f}] Note {nm.note_id}: {(nm.summary or '')[:52]}",
                value=nm.note_id,
            )
            for nm in near_misses
        ]
        selected_ids = questionary.checkbox(
            "Select notes to manually link  (Space=toggle, Enter=confirm, Ctrl+C=skip):",
            choices=choices,
        ).ask()

        if not selected_ids:
            console.print("[dim]No links added.[/dim]")
            return []

        confirmed: List[LinkConfirmRequest] = []
        for selected_id in selected_ids:
            nm_summary = next(
                (nm.summary or f"Note {nm.note_id}" for nm in near_misses if nm.note_id == selected_id),
                f"Note {selected_id}",
            )
            rel = questionary.select(
                f'Relation type for Note {selected_id} — "{nm_summary[:60]}":',
                choices=["RELATES", "REINFORCES", "CONTRADICTS"],
                default="RELATES",
            ).ask()
            if rel:
                confirmed.append(
                    LinkConfirmRequest(
                        target_id=selected_id,
                        relation_type=rel,
                        reason="Manually confirmed via --review.",
                    )
                )
                console.print(
                    f"[green]✓[/green] Note {result.note_id} [blue]{rel}[/blue] Note {selected_id}"
                )

        if confirmed:
            console.print(f"[bold green]{len(confirmed)} link(s) saved.[/bold green]")
        return confirmed
