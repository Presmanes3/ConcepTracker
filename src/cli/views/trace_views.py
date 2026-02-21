from rich.console import Console

console = Console()

def render_trace_timeline(concept, notes, note_ids, get_links_func):
    console.print(f"[bold magenta]Tracing: {concept}[/bold magenta]")
    
    if not notes:
        console.print("[red]No records found for this concept.[/red]")
        return
        
    console.print("\n[bold cyan]Timeline Flow[/bold cyan]\n")
    for i, n in enumerate(notes):
        date_str = n.created_at.strftime("%Y-%m-%d %H:%M")
        prefix = " ┃ " if i < len(notes)-1 else " ┗ "
        console.print(f"[dim]{date_str}[/dim]")
        console.print(f"{prefix}[bold white]{n.summary}[/bold white]")
        
        links = get_links_func(n.id)
        for l in links:
            if l.target_id in note_ids:
                console.print(f"   [dim]... links to note {l.target_id} ({l.relation_type})[/dim]")
        
        console.print(" ┃ ")
        
    console.print("\n[dim]Ready for more inputs. Keep tracking.[/dim]")
