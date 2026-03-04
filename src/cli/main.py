import typer
import src.cli.commands  # noqa: F401 (Trigger registry registration via imports)
from src.cli.registry import registry

def custom_help():
    """Unified professional dashboard for help."""
    # We call the help_command logic directly
    from src.cli.commands.help_cmd import help_command
    help_command()

app = typer.Typer(
    help="ConcepTracker - Atomic capture and semantic traceability.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]}
)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-v", help="Show version and exit."),
):
    """Main entry point with unified dashboard help."""
    if ctx.invoked_subcommand is None:
        custom_help()
        raise typer.Exit()

# Automated CLI registration from the Registry
for cmd in registry.commands:
    # Use the first alias as the primary name if it exists, or the original name
    # Register the command with aliases if supported by the Typer version
    # Since we want to support aliases explicitly, we can register them as separate commands 
    # that point to the same function, or use the 'rich_help_panel' or similar if grouping.
    # Typer supports multiple names for a command: app.command(\"name\", list_of_aliases)
    
    names = [cmd.name] + cmd.aliases
    primary_name = names[0]
    other_names = names[1:]
    
    # Typer's @app.command() doesn't directly take a list of names in some versions,
    # but we can call it multiple times or use the names argument if available.
    # Actually, the most robust way in Typer is to register the aliases as separate commands 
    # with 'hidden=True' so they don't clutter --help, or just use them as is.
    
    app.command(
        name=cmd.name, 
        help=f"{cmd.description}\n\n[bold white]Example:[/bold white] [cyan]{cmd.example}[/cyan]",
        rich_help_panel=cmd.group,
        **cmd.kwargs
    )(cmd.func)
    for alias in cmd.aliases:
        alias_kwargs = cmd.kwargs.copy()
        alias_kwargs["hidden"] = True  # Hide aliases from main help to keep it clean
        app.command(
            name=alias, 
            help=f"{cmd.description}\n\n[bold white]Example:[/bold white] [cyan]{cmd.example}[/cyan]",
            rich_help_panel=cmd.group,
            **alias_kwargs
        )(cmd.func)

if __name__ == "__main__":
    app()
