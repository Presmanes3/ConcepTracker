from src.services.service_registry import service_registry
from src.utils.db import init_db, health_check as db_health_check
from src.services.embedding_service import embedding_service
from src.services.transcribe_service import transcribe_service
import contextlib
import io

def bedrock_health_check():
    f = io.StringIO()
    try:
        with contextlib.redirect_stderr(f):
            embedding_service.get_embedding("ping")
        return True
    except Exception:
        return False

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
