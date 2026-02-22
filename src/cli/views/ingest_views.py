from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text


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
            title="Duplicate Ignored",
            border_style="yellow",
        )

    if action == "MERGE":
        return Panel(
            f"[blue]Existing concept updated (ID: {note_id})[/blue]\n"
            f"[bold cyan]Refined Summary:[/bold cyan] {summary}\n"
            f"{cost_str}\n\n"
            f"[dim]Logic: {reasoning}[/dim]",
            title="Concept Refined",
            border_style="blue",
        )

    # Normal CREATE flow
    items: list = [
        Panel(
            f"[bold white]{summary}[/bold white]\n"
            f"[dim]ID: {note_id} | {cost_str}[/dim]",
            title="New Note Saved",
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
            t_summary = f"Note {target_id}"
            if get_note_summary_func:
                t_summary = get_note_summary_func(target_id) or t_summary
            items.append(Text.from_markup(
                f" [blue]{relation_type}[/blue] -> {t_summary} (Reason: {reason})"
            ))
    else:
        items.append(Text.from_markup(
            "[italic yellow]No direct relations found in the past. New atomic island created.[/italic yellow]"
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