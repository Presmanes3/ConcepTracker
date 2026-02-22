import typer
from rich.console import Console
from rich.panel import Panel
from src.cli.registry import registry
from src.registry import repos
from src.services.bedrock_service import bedrock_service
from src.cli.views import render_config_list, render_config_summary, render_model_activated

console = Console()

# We can group them if needed, but for now let's keep it simple using the registry
@registry.register(
    name="config",
    description="Manage global application settings (pricing, etc).",
    example="ct config --model amazon.nova-micro-v1:0 --input 0.04 --output 0.16 --active"
)
def config_cmd(
    model: str = typer.Option(None, "--model", "-m", help="Bedrock Model ID"),
    input_price: float = typer.Option(0.0, "--input", "-i", help="Cost per 1M input tokens (USD)"),
    output_price: float = typer.Option(0.0, "--output", "-o", help="Cost per 1M output tokens (USD)"),
    active: bool = typer.Option(False, "--active", "-a", help="Set this model as the active one for inference"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all current configurations")
):
    """
    Manage system configuration without touching files manually.
    Prices are provided and listed per 1,000,000 (1M) tokens for better UX.
    Validation is performed against AWS Bedrock before adding a model.
    """

    
    settings = repos.config.get_settings()
    active_id = settings.active_model_id

    if list_all:
        console.print(render_config_list(settings, active_id))
        return

    if model:
        # 1. Validate if we want to save this model
        with console.status(f"[yellow]Validating model [bold]{model}[/bold] in Bedrock...[/yellow]"):
            is_valid = bedrock_service.validate_model_id(model)
        
        if not is_valid:
            console.print(f"[red]Error:[/red] The model ID '[bold]{model}[/bold]' was not found in your Bedrock environment.")
            console.print(f"[dim]Tip: Check your AWS profile and region ({bedrock_service.region}).[/dim]")
            raise typer.Exit(1)

        # 2. Update pricing if provided
        if input_price > 0 or output_price > 0:
            repos.config.set_model_pricing(model, input_price, output_price)
            console.print(f"[green]✔[/green] Pricing for '[bold]{model}[/bold]' updated.")

        # 3. Handle activation
        if active:
            repos.config.set_active_model(model)
            console.print(render_model_activated(model))
        elif input_price > 0 or output_price > 0:
            console.print(f"[green]✔[/green] Settings saved.")
    else:
        # Default behavior: UX Summary if no options are provided
        pricing = settings.pricing.get(active_id)
        console.print(render_config_summary(active_id, pricing))
