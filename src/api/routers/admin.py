"""POST /admin/reset-db — drop and recreate all database tables."""
from fastapi import APIRouter

from shared.schemas.api.common import MessageResponse
from src.utils.db import reset_db

router = APIRouter()


@router.post("/admin/reset-db", response_model=MessageResponse)
def reset_database() -> MessageResponse:
    """Drop all tables and recreate them. All data will be lost."""
    reset_db()
    return MessageResponse(message="Database reset successfully.")
