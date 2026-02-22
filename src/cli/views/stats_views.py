from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text


def render_stats_dashboard(results, is_configured: bool, days: int, hours: int) -> RenderableType:
    """Return a Rich Group renderable for the stats dashboard."""
    p1 = Panel(
        f"[bold cyan]{results['total_tokens']:,}[/bold cyan]\n"
        f"[dim]I: {results['prompt_tokens']:,}[/dim] | [dim]O: {results['completion_tokens']:,}[/dim]",
        title="Load (I/O Tokens)",
        border_style="cyan",
    )
    p3 = Panel(
        f"[bold magenta]{results['total_requests']}[/bold magenta]\n[dim]API Calls[/dim]",
        title="Efficiency",
        border_style="magenta",
    )

    if not is_configured:
        notice = Panel(
            "[yellow]Cost calculation is currently disabled.[/yellow]\n\n"
            "To enable financial tracking, run the config command (prices per 1M tokens):\n"
            "[bold cyan]ct config --model 'amazon.nova-micro-v1:0' --input 0.035 --output 0.14[/bold cyan]\n\n"
            "Tip: You can get your model ID from AWS Bedrock console or docs.",
            title="Configuration Missing",
            border_style="yellow",
        )
        return Group(notice, Columns([p1, p3]))

    title = f"Usage Statistics (Last {days} days)" if days > 0 else "All-Time Statistics"
    if hours > 0:
        title = f"Usage Statistics (Last {hours} hours)"

    p2 = Panel(
        f"[bold green]${results['total_cost']}[/bold green]\n[dim]Estimated Cost[/dim]",
        title="Spend",
        border_style="green",
    )
    header = Panel.fit(f"[bold white]{title}[/bold white]", border_style="blue")

    if int(results["total_requests"]) > 0:
        avg = float(results["total_cost"]) / results["total_requests"]
        footer = Text.from_markup(f"\n[dim italic]Avg. cost per request: ${avg:.6f}[/dim italic]")
    else:
        footer = Text.from_markup("[yellow]No data found for this period.[/yellow]")

    return Group(header, Columns([p1, p2, p3]), footer)