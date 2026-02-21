from rich.console import Console
from src.cli.registry import registry

console = Console()

@registry.register(
    name="health",
    description="Verify system health (DB connection & AI connectivity).",
    example="ct health"
)
def health():
    """Verify system health (DB connection & AI connectivity)."""
    from src.services import service_registry
    
    console.print("[yellow]Verifying system health...[/yellow]")
    
    active_services = service_registry.get_active_services()
    
    for name, data in active_services.items():
        health_func = data.get("health")
        if health_func:
            try:
                is_healthy = health_func()
                if is_healthy:
                    console.print(f"✅ [green]{name.capitalize()}:[/green] Connected and operational.")
                else:
                    console.print(f"❌ [red]{name.capitalize()}:[/red] Connection failed.")
            except Exception as e:
                console.print(f"❌ [red]{name.capitalize()}:[/red] Connection failed with error: {e}")
