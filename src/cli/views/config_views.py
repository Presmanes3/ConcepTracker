from rich.console import Console
from rich.panel import Panel

console = Console()

def render_config_list(settings, active_id):
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

def render_config_summary(active_id, pricing):
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

def render_model_activated(model):
    console.print(Panel(
        f"Model ID [bold cyan]{model}[/bold cyan] is now the [bold]active[/bold] model.\n"
        f"All future ingestions will use this model unless specified otherwise.",
        title="Model Activated",
        border_style="green"
    ))
