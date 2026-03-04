"""
src/cli/views/ingest_views.py

Pure rendering functions for the ingest command output.
Data in, Rich renderable out — no console.print(), no DB calls.
"""
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text


def _format_confidence_badge(confidence: dict) -> str:
    """Return a compact dim signal badge for display under a link line."""
    if not confidence:
        return ""
    score = confidence.get("score", 0.0)
    s = confidence.get("signals", {})
    parts = [f"score={score:.2f}"]
    if s.get("vector"):
        parts.append(f"vec={s['vector']}")
    if s.get("lexical") and s["lexical"] != "None":
        parts.append(f"lex={s['lexical']}")
    if s.get("same_family"):
        parts.append("family=✓")
    elif s.get("same_domain"):
        parts.append("domain=✓")
    if s.get("rrf_top"):
        parts.append("rrf=✓")
    if s.get("recent"):
        parts.append("recent=✓")
    if s.get("parent"):
        parts.insert(0, "PARENT")
    return " · ".join(parts)


def render_ingest_result(
    result: dict,
    cost_str: str,
    get_note_summary_func=None,
    count_archipelago_func=None,
) -> RenderableType:
    """
    Return a Rich renderable summarising the ingestion outcome.
    Pure function: data in, renderable out -- no console.print() calls.
    """
    action = result.get("action", "CREATE")
    note_id = result.get("note_id")
    summary = result.get("summary")
    reasoning = result.get("reasoning")
    links = result.get("links", [])

    if action == "SKIP":
        return Panel(
            f"[yellow]This concept is already in your brain (ID: {note_id})[/yellow]\n"
            f"{cost_str}\n\n"
            f"[dim]Reason: {reasoning}[/dim]",
            title="[bold]Duplicate Ignored[/bold]",
            border_style="yellow",
        )

    if action == "MERGE":
        return Panel(
            f"[blue]Existing concept updated (ID: {note_id})[/blue]\n"
            f"[bold cyan]Refined Summary:[/bold cyan] {summary}\n"
            f"{cost_str}\n\n"
            f"[dim]Logic: {reasoning}[/dim]",
            title="[bold]Concept Refined[/bold]",
            border_style="blue",
        )

    # Normal CREATE flow
    items: list = [
        Panel(
            f"[bold white]{summary}[/bold white]\n"
            f"[dim]ID: {note_id} | {cost_str}[/dim]",
            title="[bold]New Note Saved[/bold]",
            border_style="green",
        )
    ]

    if links:
        items.append(Text.from_markup(
            f"[bold cyan]Auto-Linked with {len(links)} past references:[/bold cyan]"
        ))
        for link in links:
            target_id = link.target_id if hasattr(link, "target_id") else link["target_id"]
            relation_type = link.relation_type if hasattr(link, "relation_type") else link["relation_type"]
            reason = link.reason if hasattr(link, "reason") else link["reason"]
            confidence = (
                link.confidence if hasattr(link, "confidence") else
                (link.get("confidence") if isinstance(link, dict) else None)
            )
            t_summary = f"Note {target_id}"
            if get_note_summary_func:
                t_summary = get_note_summary_func(target_id) or t_summary
            items.append(Text.from_markup(
                f" [blue]{relation_type}[/blue] -> {t_summary}\n"
                f"   [dim italic]Reason: {reason}[/dim italic]"
                + (f"\n   [dim]{_format_confidence_badge(confidence)}[/dim]" if confidence else "")
            ))
    else:
        items.append(Text.from_markup(
            "[italic yellow]No direct relations found in the past. New atomic island created.[/italic yellow]"
        ))

    # Near-miss candidates hint (shown without --review)
    near_misses = result.get("near_miss_candidates", [])
    if near_misses:
        miss_parts = []
        for nm in near_misses[:4]:   # cap at 4 to keep output tidy
            lc = nm.get("link_confidence", {})
            score = lc.get("score", 0.0)
            s = lc.get("signals", {})
            label = "SameDomain" if s.get("same_domain") else ("SameFamily" if s.get("same_family") else "")
            nm_summary = (nm.get("summary") or f"Note {nm['id']}")[:45]
            miss_parts.append(f"• [{score:.2f}] {nm_summary}" + (f" ({label})" if label else ""))
        overflow = f" +{len(near_misses) - 4} more" if len(near_misses) > 4 else ""
        items.append(Text.from_markup(
            f"[dim]Considered but not linked{overflow}:\n" +
            "\n".join(f"  {p}" for p in miss_parts) +
            "\n  Run with [bold]--review[/bold] to manually connect these.[/dim]"
        ))

    # Geography
    arch_action = result.get("archipelago_action", "NONE")
    arch_name = result.get("archipelago_name")
    arch_id = result.get("archipelago_id")
    arch_summary = result.get("archipelago_summary")

    if not arch_action or arch_action == "NONE":
        items.append(Text.from_markup("[dim]Lone Island -- no archipelago yet.[/dim]"))
    elif arch_action == "JOIN" and arch_name:
        count = count_archipelago_func(arch_id) if arch_id and count_archipelago_func else "?"
        items.append(Text.from_markup(
            f"[cyan]Joined Archipelago:[/cyan] [bold]{arch_name}[/bold] [dim]({count} islands)[/dim]"
        ))
    elif arch_action == "CREATE_ARCHIPELAGO" and arch_name:
        count = count_archipelago_func(arch_id) if arch_id and count_archipelago_func else "?"
        items.append(Panel(
            f"{arch_summary or ''}",
            title=f"New Archipelago: [bold cyan]{arch_name}[/bold cyan] ({count} islands)",
            border_style="cyan",
        ))
    elif arch_action == "CREATE_CONTINENT" and arch_name:
        items.append(Panel(
            f"{arch_summary or ''}",
            title=f"New Continent: [bold magenta]{arch_name}[/bold magenta]",
            border_style="magenta",
        ))

    return Group(*items)