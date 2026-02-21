import typer
from rich.console import Console
from rich.panel import Panel

from src.workflows.ingest_workflow import ingest_graph
from shared.schemas.workflow.ingest import IngestState
from src.repository.note_repository import note_repository
from src.repository.archipelago_repository import archipelago_repository
from src.cli.registry import registry
from src.services.cost_service import cost_service

console = Console()

@registry.register(
    name="add",
    description="Capture a note with auto-linking.",
    example='ct add "DeepSeek-R1 uses RL" --tag "AI"'
)
def add(content: str, tag: str = None):
    """Capture a new concept atômically and link it to the past."""
    with console.status("[cyan]Processing concept... (Gatekeeping & Linking)[/cyan]"):
        state = IngestState(content=content, tags=tag)
        result = ingest_graph.invoke(state)
        
        # Calculate session cost with I/O breakdown
        s = cost_service.get_last_session_cost()
        cost_str = f"[dim italic]Inference: {s['total']:,} tokens (I:{s['input']:,} | O:{s['output']:,})"
        if cost_service.is_configured:
            cost_str += f" | ${s['cost']}"
        cost_str += "[/dim italic]"
        
        action = result.get("action", "CREATE")
        note_id = result.get("note_id")
        summary = result.get("summary")
        reasoning = result.get("reasoning")
        links = result.get("links", [])
        
        if action == "SKIP":
            console.print(Panel(
                f"[yellow]This concept is already in your brain (ID: {note_id})[/yellow]\n"
                f"{cost_str}\n\n"
                f"[dim]Reason: {reasoning}[/dim]", 
                title="Duplicate Ignored", 
                border_style="yellow"
            ))
            return

        if action == "MERGE":
            console.print(Panel(
                f"[blue]Existing concept updated (ID: {note_id})[/blue]\n"
                f"[bold cyan]Refined Summary:[/bold cyan] {summary}\n"
                f"{cost_str}\n\n"
                f"[dim]Logic: {reasoning}[/dim]", 
                title="Concept Refined", 
                border_style="blue"
            ))
            return

        # Legacy/Normal CREATE flow
        console.print(Panel(
            f"[bold white]{summary}[/bold white]\n"
            f"[dim]ID: {note_id} | {cost_str}[/dim]", 
            title="New Note Saved", 
            border_style="green"
        ))
        
        if links:
            console.print(f"[bold cyan]Auto-Linked with {len(links)} past references:[/bold cyan]")
            for link in links:
                # Handle both dict and Pydantic model formats
                target_id = link.target_id if hasattr(link, 'target_id') else link["target_id"]
                relation_type = link.relation_type if hasattr(link, 'relation_type') else link["relation_type"]
                reason = link.reason if hasattr(link, 'reason') else link["reason"]
                
                target = note_repository.get_note_by_id(target_id)
                t_summary = target.summary if target else f"Note {target_id}"
                console.print(f" 🔗 [blue]{relation_type}[/blue] -> {t_summary} (Reason: {reason})")
        else:
            console.print("[italic yellow]No direct relations found in the past. New atomic island created.[/italic yellow]")
        # --- Geography ---
        arch_action = result.get("archipelago_action", "NONE")
        arch_name = result.get("archipelago_name")
        arch_id = result.get("archipelago_id")
        arch_summary = result.get("archipelago_summary")

        if arch_action == "NONE" or not arch_action:
            console.print("[dim]\U0001f3dd\ufe0f  Lone Island \u2014 no archipelago yet.[/dim]")
        elif arch_action == "JOIN" and arch_name:
            # Show how many notes are now in the archipelago
            count = archipelago_repository.count_notes_in_archipelago(arch_id) if arch_id else "?"
            console.print(
                f"[cyan]\U0001f91d Joined Archipelago:[/cyan] [bold]{arch_name}[/bold] "
                f"[dim]({count} islands)[/dim]"
            )
        elif arch_action == "CREATE_ARCHIPELAGO" and arch_name:
            count = archipelago_repository.count_notes_in_archipelago(arch_id) if arch_id else "?"
            console.print(Panel(
                f"{arch_summary or ''}",
                title=f"\U0001f5fa\ufe0f  New Archipelago: [bold cyan]{arch_name}[/bold cyan] ({count} islands)",
                border_style="cyan"
            ))
        elif arch_action == "CREATE_CONTINENT" and arch_name:
            console.print(Panel(
                f"{arch_summary or ''}",
                title=f"\U0001f30d New Continent: [bold magenta]{arch_name}[/bold magenta]",
                border_style="magenta"
            ))