import typer
from rich.console import Console
from dotenv import set_key
from src.cli.registry import registry

console = Console()

@registry.register(
    name="auth",
    description="Configure AWS credentials for Bedrock (Saves to .env).",
    example="ct auth"
)
def auth(
    access_key: str = typer.Option(..., prompt="AWS Access Key ID", hide_input=False),
    secret_key: str = typer.Option(..., prompt="AWS Secret Access Key", hide_input=True),
    region: str = typer.Option("us-east-1", prompt="AWS Region")
):
    """Configure AWS credentials for Bedrock (Saves to .env)."""
    env_path = ".env"
    set_key(env_path, "AWS_ACCESS_KEY_ID", access_key)
    set_key(env_path, "AWS_SECRET_ACCESS_KEY", secret_key)
    set_key(env_path, "AWS_REGION", region)
    console.print("[green]AWS Credentials updated successfully in .env![/green]")
