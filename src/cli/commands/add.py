import typer
from rich.console import Console
from rich.table import Table

from shared.schemas.workflow.ingest import IngestState
from src.cli.registry import registry

from src.workflows.ingest_workflow import ingest_graph
from src.registry import repos
from src.services.cost_service import cost_service
from src.cli.views import render_ingest_result

console = Console()


def _interactive_link_review(result: dict, note_id: int, get_note_summary_func) -> None:
    """
    Human-in-the-loop link review.

    Presents near-miss candidates in a table, lets the user select which ones
    to link, and persists the choices via link_repository.
    """
    import questionary
    from shared.schemas.models.link import Link
    from src.repository.link_repository import link_repository

    near_misses = result.get("near_miss_candidates", [])
    if not near_misses:
        console.print("[dim]No near-miss candidates to review \u2014 everything was either linked or too distant.[/dim]")
        return

    # Render near-miss table
    table = Table(
        title="[bold cyan]Near-miss Link Candidates[/bold cyan]",
        show_header=True,
        header_style="bold",
        border_style="dim",
        show_lines=True,
    )
    table.add_column("ID", style="cyan", width=5, justify="right")
    table.add_column("Summary", min_width=40, max_width=58)
    table.add_column("Score", width=7, justify="right")
    table.add_column("Signals", min_width=30)

    for nm in near_misses:
        lc = nm.get("link_confidence", {})
        score = lc.get("score", 0.0)
        s = lc.get("signals", {})
        sig_parts = []
        if s.get("vector") and s["vector"] != "Low":
            sig_parts.append(f"vec={s['vector']}")
        if s.get("same_family"):
            sig_parts.append("family=\u2713")
        elif s.get("same_domain"):
            sig_parts.append("domain=\u2713")
        if s.get("rrf_top"):
            sig_parts.append("rrf=\u2713")
        if s.get("recent"):
            sig_parts.append("recent=\u2713")
        nm_summary = nm.get("summary") or f"Note {nm['id']}"
        table.add_row(
            str(nm["id"]),
            nm_summary[:58],
            f"{score:.2f}",
            " \u00b7 ".join(sig_parts) or "\u2014",
        )

    console.print(table)

    # Checkbox selection
    choices = []
    for nm in near_misses:
        lc = nm.get("link_confidence", {})
        score = lc.get("score", 0.0)
        nm_summary = (nm.get("summary") or f"Note {nm['id']}")[:52]
        choices.append(questionary.Choice(
            title=f"[{score:.2f}] Note {nm['id']}: {nm_summary}",
            value=nm["id"],
        ))

    selected_ids = questionary.checkbox(
        "Select notes to manually link  (Space=toggle, Enter=confirm, Ctrl+C=skip):",
        choices=choices,
    ).ask()

    if not selected_ids:
        console.print("[dim]No links added.[/dim]")
        return

    # Relation type per selection
    saved = 0
    for selected_id in selected_ids:
        nm_summary = next(
            (nm.get("summary", f"Note {nm['id']}")[:60] for nm in near_misses if nm["id"] == selected_id),
            f"Note {selected_id}",
        )
        rel = questionary.select(
            f"Relation type for Note {selected_id} \u2014 \"{nm_summary}\":",
            choices=["RELATES", "REINFORCES", "CONTRADICTS"],
            default="RELATES",
        ).ask()

        if rel:
            link_repository.save_link(Link(
                source_id=note_id,
                target_id=selected_id,
                relation_type=rel,
                reason="Manually confirmed via --review.",
            ))
            console.print(f"[green]\u2713[/green] Note {note_id} [blue]{rel}[/blue] Note {selected_id}")
            saved += 1

    if saved:
        console.print(f"[bold green]{saved} link(s) saved.[/bold green]")


@registry.register(
    name="add",
    description="Capture a note with auto-linking.",
    example='ct add "DeepSeek-R1 uses RL" --tag "AI"'
)
def add(
    content: str,
    tag: str = None,
    review: bool = typer.Option(
        False,
        "--review", "-r",
        help="After saving, interactively review near-miss candidates for manual linking.",
    ),
):
    """Capture a new concept atomically and link it to the past."""

    with console.status("[cyan]Processing concept... (Gatekeeping & Linking)[/cyan]"):
        state = IngestState(content=content, tags=tag)
        result = ingest_graph.invoke(state)

        # Calculate session cost with I/O breakdown
        s = cost_service.get_last_session_cost()
        cost_str = f"[dim italic]Inference: {s['total']:,} tokens (I:{s['input']:,} | O:{s['output']:,})"
        if cost_service.is_configured:
            cost_str += f" | ${s['cost']}"
        cost_str += "[/dim italic]"

        def get_note_summary(target_id):
            target = repos.notes.get_note_by_id(target_id)
            return target.summary if target else None

        console.print(render_ingest_result(
            result,
            cost_str,
            get_note_summary_func=get_note_summary,
            count_archipelago_func=repos.archipelagos.count_notes_in_archipelago
        ))

    # Interactive review (opt-in via --review)
    if review:
        note_id = result.get("note_id")
        if note_id:
            _interactive_link_review(result, note_id, get_note_summary)
        else:
            console.print("[dim]Note was not created (duplicate/merge) \u2014 review skipped.[/dim]")
