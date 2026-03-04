import typer
import src.cli.commands  # noqa: F401 (Trigger registry registration via imports)
from src.cli.registry import registry

app = typer.Typer(
    help="ConcepTracker - Atomic capture and semantic traceability.",
    no_args_is_help=True
)

# Automated CLI registration from the Registry
for cmd in registry.commands:
    # Register the command by passing the name + any extra options (like no_args_is_help)
    app.command(name=cmd.name, **cmd.kwargs)(cmd.func)

if __name__ == "__main__":
    app()
