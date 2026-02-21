import questionary
from rich.console import Console
from src.repository.note_repository import repository
from src.repository.archipelago_repository import archipelago_repository
from src.repository.link_repository import link_repository
from shared.schemas.models.link import Link
from src.cli.ui import build_note_dashboard

console = Console()

def show_note_action_menu(note):
    """
    Interactive menu for a selected note.
    """
    from src.services.embedding_service import embedding_service
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from src.cli.ui import get_archipelago_badge
    
    inline_content = None
    
    while True:
        console.clear()
        
        # Refresh note to get latest state
        note = repository.get_note_by_id(note.id)
        if not note:
            console.print("[red]Note no longer exists.[/red]")
            break

        console.print(build_note_dashboard(note))
        
        if inline_content:
            console.print(inline_content)
            inline_content = None # Clear after showing once

        console.print(Panel("[bold cyan]Choose an action:[/bold cyan]", style="blue", width=40))

        custom_style = questionary.Style([
            ('qmark', 'fg:#673ab7 bold'),
            ('question', 'bold'),
            ('answer', 'fg:#f44336 bold'),
            ('pointer', 'fg:#673ab7 bold'),
            ('highlighted', 'fg:#673ab7 bold'),
            ('selected', 'fg:#cc5454'),
            ('separator', 'fg:#cc5454'),
            ('instruction', ''),
        ])

        action = questionary.select(
            " ",
            choices=[
                questionary.Choice("  🔍 Explore (Find similar, Trace)", "explore"),
                questionary.Choice("  🚀 Jump to Note", "jump"),
                questionary.Choice("  ✏️  Edit Note (Content, Summary)", "edit"),
                questionary.Choice("  🏷️  Manage Tags", "tags"),
                questionary.Choice("  🔗 Manage Links", "links"),
                questionary.Choice("  🗑️  Delete Note", "delete"),
                questionary.Separator(),
                questionary.Choice("  🔙 Back to list", "back"),
            ],
            style=custom_style,
            qmark="",
            pointer="●",
            instruction=" "
        ).ask()

        if action == "back" or action is None:
            break
            
        elif action == "jump":
            target_id_str = questionary.text("Enter Note ID to jump to:").ask()
            if target_id_str and target_id_str.isdigit():
                target_id = int(target_id_str)
                target_note = repository.get_note_by_id(target_id)
                if target_note:
                    show_note_action_menu(target_note)
                else:
                    inline_content = Panel(f"[red]Note with ID {target_id} not found.[/red]", border_style="red")
            
        elif action == "explore":
            console.print(Panel("[bold cyan]Explore Options:[/bold cyan]", style="blue", width=40))
            sub_action = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  Find similar concepts", "find"),
                    questionary.Choice("  Trace chronological evolution", "trace"),
                    questionary.Choice("  Back", "back")
                ],
                style=custom_style,
                qmark="",
                pointer="●",
                instruction=" "
            ).ask()
            
            if sub_action == "find":
                with console.status("[cyan]Searching for similar concepts...[/cyan]"):
                    vector = embedding_service.get_embedding(note.summary)
                    results = repository.semantic_search(vector, limit=5)
                
                if not results:
                    inline_content = Panel("[yellow]No similar concepts found.[/yellow]", border_style="yellow")
                else:
                    table = Table(box=None, show_header=True, header_style="bold magenta")
                    table.add_column("Match", justify="right", style="green")
                    table.add_column("ID", justify="right", style="cyan")
                    table.add_column("Archipelago")
                    table.add_column("Summary")
                    
                    for res_note, distance in results:
                        if res_note.id == note.id:
                            continue
                        percentage = max(0, min(100, int((1 - distance) * 100)))
                        match_color = "green" if percentage > 70 else "yellow"
                        arch_badge = get_archipelago_badge(res_note.archipelago_id)
                        summary = res_note.summary[:60] + "..." if len(res_note.summary) > 60 else res_note.summary
                        table.add_row(
                            f"[{match_color}]{percentage}%[/{match_color}]",
                            str(res_note.id),
                            arch_badge,
                            summary
                        )
                    inline_content = Panel(table, title="[bold cyan]Similar Concepts[/bold cyan]", border_style="cyan")
                    
            elif sub_action == "trace":
                with console.status("[cyan]Tracing evolution...[/cyan]"):
                    vector = embedding_service.get_embedding(note.summary)
                    results = repository.get_similar_notes(current_id=None, embedding=vector, limit=5, threshold=0.8)
                
                if not results:
                    inline_content = Panel("[yellow]No related concepts found for tracing.[/yellow]", border_style="yellow")
                else:
                    # Sort chronologically
                    results.sort(key=lambda x: x["id"])
                    
                    trace_text = Text()
                    for i, res in enumerate(results):
                        is_current = res["id"] == note.id
                        prefix = "👉 " if is_current else "   "
                        style = "bold green" if is_current else "white"
                        
                        summary = res["summary"][:60] + "..." if len(res["summary"]) > 60 else res["summary"]
                        trace_text.append(f"{prefix}[ID {res['id']}] ", style="cyan")
                        trace_text.append(f"{summary}\n", style=style)
                        
                        if i < len(results) - 1:
                            trace_text.append("   │\n", style="dim")
                            
                    inline_content = Panel(trace_text, title="[bold magenta]Chronological Trace[/bold magenta]", border_style="magenta")

        elif action == "edit":
            console.print(Panel("[bold cyan]What to edit?[/bold cyan]", style="blue", width=40))
            sub_action = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  Edit Content", "content"),
                    questionary.Choice("  Edit Summary", "summary"),
                    questionary.Choice("  Back", "back")
                ],
                style=custom_style,
                qmark="",
                pointer="●",
                instruction=" "
            ).ask()
            
            if sub_action == "content":
                console.print("[dim]Opening multiline editor. Press Esc followed by Enter to save.[/dim]")
                new_content = questionary.text("New Content:", default=note.content, multiline=True).ask()
                if new_content and new_content != note.content:
                    repository.update_note(note.id, content=new_content)
                    inline_content = Panel("[green]Content updated successfully.[/green]", border_style="green")
            elif sub_action == "summary":
                console.print("[dim]Opening multiline editor. Press Esc followed by Enter to save.[/dim]")
                new_summary = questionary.text("New Summary:", default=note.summary, multiline=True).ask()
                if new_summary and new_summary != note.summary:
                    repository.update_note(note.id, summary=new_summary)
                    inline_content = Panel("[green]Summary updated successfully.[/green]", border_style="green")

        elif action == "tags":
            from src.agents.tag_recommender_agent import TagRecommenderAgent
            from src.services.embedding_service import embedding_service
            from collections import Counter
            from src.cli.tag_selector import select_tags_ui
            
            current_tags = [t.strip() for t in note.tags.split(",")] if note.tags else []
            
            with console.status("[cyan]✨ Analyzing content for tag recommendations...[/cyan]"):
                # 1. Get AI recommendations
                ai_tags = TagRecommenderAgent().run({"content": note.content, "summary": note.summary}).get("tags", [])
                
                # 2. Get Semantic Database recommendations (Collaborative Filtering)
                vector = embedding_service.get_embedding(note.summary)
                similar_notes_results = repository.semantic_search(vector, limit=15)
                
                tag_counts = Counter()
                for similar_note, _distance in similar_notes_results:
                    if similar_note.id == note.id:
                        continue
                    if similar_note.tags:
                        for t in similar_note.tags.split(","):
                            tag = t.strip()
                            if tag and tag not in current_tags:
                                tag_counts[tag] += 1
                                
                # Format DB tags for the UI
                db_tags = [{"name": tag, "count": count} for tag, count in tag_counts.most_common(10)]
            
            # Clear screen and show dashboard so the tag selector is right below it
            console.clear()
            dashboard = build_note_dashboard(note)
            
            # Launch custom interactive UI
            selected_tags = select_tags_ui(current_tags, ai_tags, db_tags, dashboard_renderable=dashboard)
                
            if selected_tags is not None: # None means user pressed Esc/q
                final_tags_str = ",".join(selected_tags)
                if final_tags_str != note.tags:
                    repository.update_note(note.id, tags=final_tags_str)
                    inline_content = Panel(f"[green]Tags updated to: {final_tags_str}[/green]", border_style="green")

        elif action == "links":
            console.print(Panel("[bold cyan]Manage Links:[/bold cyan]", style="blue", width=40))
            sub_action = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  Add Link (This -> Other)", "add"),
                    questionary.Choice("  Remove Link", "remove"),
                    questionary.Choice("  Back", "back")
                ],
                style=custom_style,
                qmark="",
                pointer="●",
                instruction=" "
            ).ask()
            
            if sub_action == "add":
                target_id_str = questionary.text("Enter Target Note ID:").ask()
                if target_id_str and target_id_str.isdigit():
                    target_id = int(target_id_str)
                    target_note = repository.get_note_by_id(target_id)
                    if not target_note:
                        console.print(f"[red]Note with ID {target_id} not found.[/red]")
                        questionary.press_any_key_to_continue().ask()
                    else:
                        relation = questionary.text("Relation type (e.g., 'supports', 'contradicts', 'expands'):", default="relates_to").ask()
                        reason = questionary.text("Reason for link:").ask()
                        if relation:
                            new_link = Link(
                                source_id=note.id,
                                target_id=target_id,
                                relation_type=relation,
                                reason=reason or "Manual link"
                            )
                            link_repository.save_link(new_link)
                            console.print("[green]Link added successfully.[/green]")
                            questionary.press_any_key_to_continue().ask()
            
            elif sub_action == "remove":
                out_links = link_repository.get_links_by_source(note.id)
                in_links = link_repository.get_links_by_target(note.id)
                all_links = out_links + in_links
                
                if not all_links:
                    console.print("[yellow]No links to remove.[/yellow]")
                    questionary.press_any_key_to_continue().ask()
                else:
                    choices = []
                    for l in out_links:
                        choices.append(questionary.Choice(f"[{l.id}] Out: {l.relation_type} -> {l.target_id}", l.id))
                    for l in in_links:
                        choices.append(questionary.Choice(f"[{l.id}] In: {l.relation_type} <- {l.source_id}", l.id))
                    
                    console.print(Panel("[bold cyan]Select link to remove:[/bold cyan]", style="blue", width=40))
                    link_id_to_remove = questionary.select(
                        " ",
                        choices=choices,
                        style=custom_style,
                        qmark="",
                        pointer="●",
                        instruction=" "
                    ).ask()
                    if link_id_to_remove:
                        link_repository.delete_link(link_id_to_remove)
                        console.print("[green]Link removed successfully.[/green]")
                        questionary.press_any_key_to_continue().ask()

        elif action == "delete":
            confirm = questionary.confirm(f"Are you sure you want to delete note {note.id}?").ask()
            if confirm:
                repository.delete_note(note.id)
                console.print(f"[green]Note {note.id} deleted successfully.[/green]")
                questionary.press_any_key_to_continue().ask()
                break # Go back to list since note is gone
