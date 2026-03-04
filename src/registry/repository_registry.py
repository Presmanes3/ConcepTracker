"""
Repository Registry — SSoT for all repository singletons.

Lazy-instantiates each repository on first access to avoid circular imports at module load time.
All consumers should import `repos` and access repos.notes, repos.links, etc.

Usage::

    from src.registry import repos

    note = repos.notes.get_note_by_id(42)
    links = repos.links.get_links_by_source(42)
    arch  = repos.archipelagos.get_archipelago_by_id(note.archipelago_id)
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.repository.note_repository import NoteRepository
    from src.repository.link_repository import LinkRepository
    from src.repository.archipelago_repository import ArchipelagoRepository
    from src.repository.config_repository import ConfigRepository
    from src.repository.inference_repository import InferenceRepository
    from src.repository.transcription_repository import TranscriptionRepository
    from src.services.search_service import SearchService


class RepositoryRegistry:
    """
    Singleton container for all repository singletons.

    Each property lazily imports and returns the repository singleton on first access,
    which keeps the import graph acyclic and avoids loading DB dependencies at module parse time.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── Notes ─────────────────────────────────────────────────────────────────

    @property
    def notes(self) -> "NoteRepository":
        from src.repository.note_repository import repository
        return repository

    # ── Links ─────────────────────────────────────────────────────────────────

    @property
    def links(self) -> "LinkRepository":
        from src.repository.link_repository import link_repository
        return link_repository

    # ── Archipelagos ──────────────────────────────────────────────────────────

    @property
    def archipelagos(self) -> "ArchipelagoRepository":
        from src.repository.archipelago_repository import archipelago_repository
        return archipelago_repository

    # ── Config ────────────────────────────────────────────────────────────────

    @property
    def config(self) -> "ConfigRepository":
        from src.repository.config_repository import config_repository
        return config_repository

    # ── Inference / Cost Logs ─────────────────────────────────────────────────

    @property
    def inference(self) -> "InferenceRepository":
        from src.repository.inference_repository import inference_repository
        return inference_repository

    # ── Transcriptions ────────────────────────────────────────────────────────

    @property
    def transcriptions(self) -> "TranscriptionRepository":
        from src.repository.transcription_repository import transcription_repository
        return transcription_repository

    # ── Search ────────────────────────────────────────────────────────────────

    @property
    def search(self) -> "SearchService":
        from src.services.search_service import search_service
        return search_service


repos = RepositoryRegistry()
