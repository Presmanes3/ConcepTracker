"""
src/cli/views/trace_views.py

Pure rendering functions for the trace command timeline.
Data in, Rich renderable out — no console.print(), no DB calls.
"""
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text


def render_trace_timeline(concept, notes, note_ids, get_links_func) -> RenderableType:
    """Return a list of Rich objects for the trace timeline."""
    if not notes:
        return [
            Text.from_markup(f"[yellow]No records found for concept: [bold]{concept}[/bold][/yellow]"),
        ]

    items: list = []
    for i, n in enumerate(notes):
        date_str = n.created_at.strftime("%Y-%m-%d %H:%M")
        is_last = (i == len(notes) - 1)
        connector = "[dim]  └─[/dim]" if is_last else "[dim]  ├─[/dim]"
        items.append(Text.from_markup(f"[dim]{date_str}[/dim]"))
        items.append(Text.from_markup(f"{connector} [bold white]{n.summary}[/bold white]"))
        links = get_links_func(n.id)
        for ln in links:
            if ln.target_id in note_ids:
                items.append(Text.from_markup(
                    f"       [dim cyan]↳ links to note {ln.target_id} ({ln.relation_type})[/dim cyan]"
                ))
        if not is_last:
            items.append(Text.from_markup("[dim]  │[/dim]"))

    items.append(Text(""))
    items.append(Text.from_markup("[dim]Ready for more inputs. Keep tracking.[/dim]"))

    return Group(*items)