from rich.console import Console
from src.cli.registry import registry

from src.services import service_registry

console = Console()

@registry.register(
    name="init",
    description="Build the brain. Initialize database and pgvector extension.",
    example="ct init"
)
def init():
    """Build the brain. Initialize database and pgvector extension."""

    
    console.print("[yellow]Initializing services...[/yellow]")
    
    active_services = service_registry.get_active_services()
    
    for name, data in active_services.items():
        init_func = data.get("init")
        if init_func:
            console.print(f"[yellow]Initializing {name}...[/yellow]")
            try:
                init_func()
                console.print(f"[green]Success! {name} initialized.[/green]")
            except Exception as e:
                console.print(f"[red]Critical Error initializing {name}: {e}[/red]")
                
    console.print("[green]Initialization complete.[/green]")
