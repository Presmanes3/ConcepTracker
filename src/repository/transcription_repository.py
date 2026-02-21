from sqlmodel import select
from typing import List, Optional
from src.utils.db import get_session
from shared.schemas.models.transcription import Transcription

class TranscriptionRepository:
    """
    Repository for managing the lifecycle of Transcriptions.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TranscriptionRepository, cls).__new__(cls)
        return cls._instance

    def save_transcription(self, transcription: Transcription) -> Transcription:
        """Persists a new transcription to the database."""
        with get_session() as session:
            session.add(transcription)
            session.commit()
            session.refresh(transcription)
            return transcription

    def update_transcription(self, transcription: Transcription) -> Transcription:
        """Updates an existing transcription in the database."""
        with get_session() as session:
            session.add(transcription)
            session.commit()
            session.refresh(transcription)
            return transcription

    def get_transcription_by_id(self, transcription_id: int) -> Optional[Transcription]:
        """Retrieves a single transcription by its primary ID."""
        with get_session() as session:
            return session.get(Transcription, transcription_id)

    def get_all_transcriptions(self, limit: int = 20) -> List[Transcription]:
        """Lists transcriptions."""
        with get_session() as session:
            query = select(Transcription).order_by(Transcription.created_at.desc()).limit(limit)
            return session.exec(query).all()

transcription_repository = TranscriptionRepository()
