import typer
from rich.console import Console
from rich.panel import Panel

from shared.schemas.workflow.ingest import IngestState
from src.cli.registry import registry

from src.workflows.ingest_workflow import ingest_graph
from src.registry import repos
from src.services.cost_service import cost_service
from src.cli.views import render_ingest_result

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
        
        def get_note_summary(target_id):
            target = repos.notes.get_note_by_id(target_id)
            return target.summary if target else None
            
        render_ingest_result(
            result, 
            cost_str, 
            get_note_summary_func=get_note_summary,
            count_archipelago_func=repos.archipelagos.count_notes_in_archipelago
        )