"""config command — view and update application model/pricing settings."""
import typer
from rich.console import Console
from rich.panel import Panel

from src.cli.interactors.config_interactor import ConfigInteractor
from src.cli.registry import registry

console = Console()


@registry.register(
    name="config",
    description="Manage global application settings (pricing, etc).",
    example="ct config --model amazon.nova-micro-v1:0 --input 0.04 --output 0.16 --active"
)
def config_cmd(
    model: str = typer.Option(None, "--model", "-m", help="Bedrock Model ID"),
    input_price: float = typer.Option(0.0, "--input", "-i", help="Cost per 1M input tokens (USD)"),
    output_price: float = typer.Option(0.0, "--output", "-o", help="Cost per 1M output tokens (USD)"),
    active: bool = typer.Option(False, "--active", "-a", help="Set this model as the active one"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all current configurations"),
):
    """Manage system configuration without touching files manually."""
    try:
        ConfigInteractor(
            model=model,
            input_price=input_price,
            output_price=output_price,
            active=active,
            list_all=list_all,
        ).run()
    except ValueError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[bold]Error[/bold]", border_style="red"))
        raise SystemExit(1)
    except Exception as e:
        console.print(Panel(f"[red]Unexpected error:[/red] {e}", border_style="red"))
        raise SystemExit(1)


# We can group commands if needed, but config_cmd is defined once above using ConfigInteractor.
