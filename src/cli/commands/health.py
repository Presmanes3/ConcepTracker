import contextlib
import io
from rich.console import Console
from src.utils.db import health_check
from src.services.embedding_service import embedding_service
from src.cli.registry import registry

console = Console()

@registry.register(
    name="health",
    description="Verify system health (DB connection & AI connectivity).",
    example="ct health"
)
def health():
    """Verify system health (DB connection & AI connectivity)."""
    console.print("[yellow]Verifying system health...[/yellow]")
    
    # Check Database
    if health_check():
        console.print("✅ [green]Database:[/green] Connected and operational.")
    else:
        console.print("❌ [red]Database:[/red] Connection failed. Please check if the Docker container 'concept_db' is running.")

    # Check Embeddings (AWS Bedrock)
    # We suppress stderr to avoid LangChain/Botocore noisy tracebacks during the health check
    f = io.StringIO()
    try:
        with contextlib.redirect_stderr(f):
            embedding_service.get_embedding("ping")
        console.print("✅ [green]AI (AWS Bedrock):[/green] Connectivity established.")
    except Exception:
        console.print("❌ [red]AI (AWS Bedrock):[/red] Connection failed. Check your credentials with `ct auth` and AWS_REGION.")
