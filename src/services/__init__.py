from src.services.service_registry import service_registry
from src.utils.db import init_db, health_check as db_health_check
from src.services.embedding_service import embedding_service
from src.services.transcribe_service import transcribe_service
import contextlib
import io

def bedrock_health_check():
    """Verify Bedrock connectivity by attempting a small embedding request."""
    try:
        from src.services.embedding_service import embedding_service
        embedding_service.get_embedding("ping")
        return {"status": "healthy"}
    except Exception as e:
        error_msg = str(e)
        if "MissingRegionError" in error_msg:
            hint = "AWS_REGION is missing."
        elif "NoCredentialsError" in error_msg:
            hint = "AWS credentials not found."
        elif "InvalidClientTokenId" in error_msg:
            hint = "Invalid AWS Access Key."
        elif "SignatureDoesNotMatch" in error_msg:
            hint = "Invalid AWS Secret Key."
        else:
            hint = error_msg
        return {"status": "unhealthy", "message": hint}

# Register Database
service_registry.register(
    name="database",
    init_func=init_db,
    health_func=db_health_check
)

# Register Bedrock
service_registry.register(
    name="bedrock",
    init_func=None,
    health_func=bedrock_health_check
)

# Register Transcribe
service_registry.register(
    name="transcribe",
    init_func=None,
    health_func=transcribe_service.health_check
)
