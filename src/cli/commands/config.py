import typer
from rich.console import Console
from rich.panel import Panel
from src.repository.config_repository import config_repository
from src.services.bedrock_service import bedrock_service
from src.cli.registry import registry

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
    settings = config_repository.get_settings()
    active_id = settings.active_model_id

    if list_all:
        if not settings or not settings.pricing:
            console.print(f"[yellow]No pricing configured yet. Active model: [bold]{active_id}[/bold][/yellow]")
            return
        
        console.print("[bold cyan]Current Models & Pricing (USD per 1M tokens):[/bold cyan]")
        for mid, p in settings.pricing.items():
            is_active = mid == active_id
            star = "[bold yellow]*[/bold yellow]" if is_active else " "
            color = "green" if is_active else "white"
            tag = " [bold green][ACTIVE][/bold green]" if is_active else ""
            console.print(f"{star} [bold {color}]{mid}{tag}[/bold {color}]: I:[green]${p.input:.4f}[/green] | O:[green]${p.output:.4f}[/green]")
        
        if active_id not in settings.pricing:
            console.print(f" - [yellow]{active_id} [ACTIVE, NO PRICING][/yellow]")
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
            config_repository.set_model_pricing(model, input_price, output_price)
            console.print(f"[green]✔[/green] Pricing for '[bold]{model}[/bold]' updated.")

        # 3. Handle activation
        if active:
            config_repository.set_active_model(model)
            console.print(Panel(
                f"Model ID [bold cyan]{model}[/bold cyan] is now the [bold]active[/bold] model.\n"
                f"All future ingestions will use this model unless specified otherwise.",
                title="Model Activated",
                border_style="green"
            ))
        elif input_price > 0 or output_price > 0:
            console.print(f"[green]✔[/green] Settings saved.")
    else:
        # Default behavior: UX Summary if no options are provided
        pricing = settings.pricing.get(active_id)
        price_str = f"Pricing (1M): I:[green]${pricing.input:.4f}[/green] | O:[green]${pricing.output:.4f}[/green]" if pricing else "[yellow]No pricing configured[/yellow]"
        
        console.print(Panel(
            f"Current Active Model: [bold cyan]{active_id}[/bold cyan]\n"
            f"Status: {price_str}\n\n"
            f"[yellow]Usage Options:[/yellow]\n"
            f" • Use [bold]--active[/bold] to switch default model\n"
            f" • Use [bold]--input[/bold]/[bold]--output[/bold] to set USD per 1M tokens\n"
            f" • Use [bold]--list[/bold] to see all saved models\n\n"
            f"[dim]Example:[/dim] [white]ct config -m 'amazon.nova-micro-v1:0' -i 0.04 -o 0.16 --active[/white]",
            title="Config Summary",
            border_style="blue",
            expand=False
        ))
