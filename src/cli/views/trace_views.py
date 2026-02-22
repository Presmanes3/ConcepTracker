from rich.console import Group, RenderableType
from rich.text import Text


def render_trace_timeline(concept, notes, note_ids, get_links_func) -> RenderableType:
    """Return a Rich Group renderable for the trace timeline."""
    items: list = [Text.from_markup(f"[bold magenta]Tracing: {concept}[/bold magenta]")]

    if not notes:
        items.append(Text("[red]No records found for this concept.[/red]", style="red"))
        return Group(*items)

    items.append(Text.from_markup("\n[bold cyan]Timeline Flow[/bold cyan]\n"))
    for i, n in enumerate(notes):
        date_str = n.created_at.strftime("%Y-%m-%d %H:%M")
        prefix = " - " if i < len(notes) - 1 else " + "
        items.append(Text.from_markup(f"[dim]{date_str}[/dim]"))
        items.append(Text.from_markup(f"{prefix}[bold white]{n.summary}[/bold white]"))
        links = get_links_func(n.id)
        for ln in links:
            if ln.target_id in note_ids:
                items.append(Text.from_markup(
                    f"   [dim]... links to note {ln.target_id} ({ln.relation_type})[/dim]"
                ))
        items.append(Text(" | "))

    items.append(Text.from_markup("\n[dim]Ready for more inputs. Keep tracking.[/dim]"))
    return Group(*items)