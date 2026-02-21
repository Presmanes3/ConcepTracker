from rich.panel import Panel
from rich.console import Group
from rich.table import Table
from rich.text import Text
from src.repository.archipelago_repository import archipelago_repository
from src.repository.link_repository import link_repository

def get_archipelago_badge(archipelago_id: int | None, arch_cache: dict = None) -> str:
    """Helper to get a formatted archipelago badge, using a cache if provided."""
    if arch_cache is not None and archipelago_id in arch_cache:
        return arch_cache[archipelago_id]
        
    if not archipelago_id:
        return "[dim]~island~[/dim]"
        
    arch = archipelago_repository.get_archipelago_by_id(archipelago_id)
    if arch:
        icon = "\U0001f30d" if arch.type == "continent" else "\U0001f5fa\ufe0f"
        return f"{icon} [yellow]{arch.name}[/yellow]"
    return "[dim]~island~[/dim]"

def build_note_preview(
    note, 
    arch_cache: dict = None, 
    title: str = None, 
    border_style: str = "green", 
    show_links: bool = True, 
    truncate_content: int = None
) -> Panel:
    """
    Builds a standardized Rich Panel for previewing a note.
    Used across ls, find, and the note dashboard.
    """
    arch_badge = get_archipelago_badge(note.archipelago_id, arch_cache)
    date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
    tags_str = f"[magenta]{note.tags}[/magenta]" if note.tags else "[dim]No Tags[/dim]"
    
    meta_table = Table.grid(padding=(0, 4))
    meta_table.add_row(f"[bold cyan]ID:[/bold cyan] {note.id}", f"[bold cyan]Date:[/bold cyan] {date_str}")
    meta_table.add_row(f"[bold cyan]Archipelago:[/bold cyan] {arch_badge}", f"[bold cyan]Tags:[/bold cyan] {tags_str}")
    
    display_content = note.content
    if truncate_content and len(display_content) > truncate_content:
        display_content = display_content[:truncate_content] + "..."
        
    content = f"{display_content}\n\n[dim italic]Summary: {note.summary}[/dim italic]"
    
    renderables = [meta_table, "", content]
    
    if show_links:
        out_links = link_repository.get_links_by_source(note.id)
        in_links = link_repository.get_links_by_target(note.id)
        
        links_text = Text()
        if not out_links and not in_links:
            links_text.append("No links connected to this note.", style="dim")
        else:
            if out_links:
                links_text.append(f"🔗 {len(out_links)} Outgoing: ", style="bold blue")
                out_strs = [f"[{l.relation_type} -> ID {l.target_id}]" for l in out_links]
                links_text.append(", ".join(out_strs))
            
            if in_links:
                if out_links: links_text.append("\n")
                links_text.append(f"🔗 {len(in_links)} Incoming: ", style="bold yellow")
                in_strs = [f"[{l.relation_type} <- ID {l.source_id}]" for l in in_links]
                links_text.append(", ".join(in_strs))
        
        renderables.extend(["", links_text])
        
    panel_group = Group(*renderables)
    
    if title is None:
        title = f"[bold green]Preview: Note #{note.id}[/bold green]"
        
    return Panel(
        panel_group,
        title=title,
        border_style=border_style,
    )

def build_note_dashboard(note) -> Group:
    """
    Builds the full detailed view for a single note (used in the note menu).
    """
    from rich.rule import Rule
    from rich.markdown import Markdown
    from src.repository.note_repository import repository
    
    arch_badge = get_archipelago_badge(note.archipelago_id)
    date_str = note.created_at.strftime("%Y-%m-%d %H:%M")
    tags_str = f"[magenta]{note.tags}[/magenta]" if note.tags else "[dim]No Tags[/dim]"
    
    meta_table = Table.grid(padding=(0, 4))
    meta_table.add_row(f"[bold cyan]ID:[/bold cyan] {note.id}", f"[bold cyan]Date:[/bold cyan] {date_str}")
    meta_table.add_row(f"[bold cyan]Archipelago:[/bold cyan] {arch_badge}", f"[bold cyan]Tags:[/bold cyan] {tags_str}")

    # Content as Markdown
    content_md = Markdown(note.content)
    
    # Summary as a distinct panel
    summary_panel = Panel(
        f"[italic]{note.summary}[/italic]", 
        title="[dim]TL;DR / Summary[/dim]", 
        border_style="dim",
        title_align="left"
    )
    
    content_group = Group(
        meta_table,
        Rule(style="dim"),
        content_md,
        "",
        summary_panel
    )
    
    main_panel = Panel(
        content_group,
        title=f"[bold green]Note #{note.id}[/bold green]",
        border_style="green",
        expand=True
    )

    # Links section
    out_links = link_repository.get_links_by_source(note.id)
    in_links = link_repository.get_links_by_target(note.id)
    
    if not out_links and not in_links:
        links_panel = Panel("[dim]No links connected to this note.[/dim]", title="[bold blue]Connections[/bold blue]", border_style="blue", expand=True)
    else:
        link_table = Table(show_header=False, box=None, padding=(0, 2))
        link_table.add_column("Direction", style="bold")
        link_table.add_column("Type", style="cyan")
        link_table.add_column("Target ID", style="magenta")
        link_table.add_column("Summary", style="dim")
        
        if out_links:
            link_table.add_row("[blue]🔗 Outgoing[/blue]", "", "", "")
            for l in out_links:
                target = repository.get_note_by_id(l.target_id)
                t_sum = target.summary[:60] + "..." if target and len(target.summary) > 60 else (target.summary if target else "Unknown")
                link_table.add_row("  [dim]↳[/dim]", l.relation_type, f"ID {l.target_id}", t_sum)
        
        if in_links:
            if out_links:
                link_table.add_row("", "", "", "") # spacer
            link_table.add_row("[yellow]🔗 Incoming[/yellow]", "", "", "")
            for l in in_links:
                source = repository.get_note_by_id(l.source_id)
                s_sum = source.summary[:60] + "..." if source and len(source.summary) > 60 else (source.summary if source else "Unknown")
                link_table.add_row("  [dim]↳[/dim]", l.relation_type, f"ID {l.source_id}", s_sum)
                
        links_panel = Panel(link_table, title="[bold blue]Connections[/bold blue]", border_style="blue", expand=True)

    return Group(main_panel, links_panel)

