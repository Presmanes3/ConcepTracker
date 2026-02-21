from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns

console = Console()

def render_stats_dashboard(results, is_configured, days, hours):
    if not is_configured:
        console.print(Panel(
            "[yellow]Cost calculation is currently disabled.[/yellow]\n\n"
            "To enable financial tracking, run the config command (prices per 1M tokens):\n"
            "[bold cyan]ct config --model 'amazon.nova-micro-v1:0' --input 0.035 --output 0.14[/bold cyan]\n\n"
            "Tip: You can get your model ID from AWS Bedrock console or docs.",
            title="Configuration Missing",
            border_style="yellow"
        ))
        
        p1 = Panel(
            f"[bold cyan]{results['total_tokens']:,}[/bold cyan]\n"
            f"[dim]I: {results['prompt_tokens']:,}[/dim] | [dim]O: {results['completion_tokens']:,}[/dim]",
            title="Load (I/O Tokens)", border_style="cyan"
        )
        p3 = Panel(f"[bold magenta]{results['total_requests']}[/bold magenta]\n[dim]API Calls[/dim]", title="Efficiency", border_style="magenta")
        console.print(Columns([p1, p3]))
        return

    title = f"Usage Statistics (Last {days} days)" if days > 0 else "All-Time Statistics"
    if hours > 0:
        title = f"Usage Statistics (Last {hours} hours)"

    p1 = Panel(
        f"[bold cyan]{results['total_tokens']:,}[/bold cyan]\n"
        f"[dim]I: {results['prompt_tokens']:,}[/dim] | [dim]O: {results['completion_tokens']:,}[/dim]",
        title="Load (I/O Tokens)", border_style="cyan"
    )
    p2 = Panel(f"[bold green]${results['total_cost']}[/bold green]\n[dim]Estimated Cost[/dim]", title="Spend", border_style="green")
    p3 = Panel(f"[bold magenta]{results['total_requests']}[/bold magenta]\n[dim]API Calls[/dim]", title="Efficiency", border_style="magenta")

    console.print(Panel.fit(f"[bold white]{title}[/bold white]", border_style="blue"))
    console.print(Columns([p1, p2, p3]))

    if int(results['total_requests']) > 0:
        avg = float(results['total_cost']) / results['total_requests']
        console.print(f"\n[dim italic]Avg. cost per request: ${avg:.6f}[/dim italic]")
    else:
        console.print("[yellow]No data found for this period.[/yellow]")
