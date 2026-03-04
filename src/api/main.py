"""FastAPI application factory."""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ...existing imports...
# Ensure standard loggers produce output in uvicorn
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)

# Set our app loggers to DEBUG if requested, but keep noisy libs at INFO
if os.environ.get("DEBUG"):
    logging.getLogger("src").setLevel(logging.DEBUG)
    logging.getLogger("shared").setLevel(logging.DEBUG)
    # Silencing noisy third-party libraries
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("langchain_aws").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)

from src.api.routers import (
    admin,
    health,
    init,
    notes,
    search,
    links,
    archipelagos,
    stats,
    config,
    devices,
    transcription,
)


def create_app() -> FastAPI:
    application = FastAPI(
        title="ConcepTracker API",
        description="Backend for the ConcepTracker knowledge management system.",
        version="0.1.0",
    )

    # Restrict CORS to localhost — single-user local deployment only.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://localhost:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:8000",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(admin.router, tags=["admin"])
    application.include_router(health.router, tags=["system"])
    application.include_router(init.router, tags=["system"])
    application.include_router(notes.router, tags=["notes"])
    application.include_router(search.router, tags=["search"])
    application.include_router(links.router, tags=["links"])
    application.include_router(archipelagos.router, tags=["archipelagos"])
    application.include_router(stats.router, tags=["stats"])
    application.include_router(config.router, tags=["config"])
    application.include_router(devices.router, tags=["devices"])
    application.include_router(transcription.router, tags=["transcription"])

    return application


app = create_app()
