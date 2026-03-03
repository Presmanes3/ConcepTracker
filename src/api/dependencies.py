"""FastAPI dependency providers — use via Depends() in route handlers."""
from src.repository.note_repository import note_repository
from src.repository.link_repository import link_repository
from src.repository.archipelago_repository import archipelago_repository
from src.repository.config_repository import config_repository
from src.repository.transcription_repository import transcription_repository
from src.services.audio_device_service import AudioDeviceService
from src.services.bedrock_service import bedrock_service
from src.services.cost_service import CostService, cost_service as _cost_service_singleton
from src.services.embedding_service import embedding_service
from src.services.search_service import search_service
from src.registry.service_registry import service_registry


# ── Repositories ──────────────────────────────────────────────────────────────

def get_note_repo():
    return note_repository


def get_link_repo():
    return link_repository


def get_arch_repo():
    return archipelago_repository


def get_config_repo():
    return config_repository


def get_transcription_repo():
    return transcription_repository


# ── Services ──────────────────────────────────────────────────────────────────



def get_cost_service() -> CostService:
    return _cost_service_singleton


def get_embedding_service():
    return embedding_service


def get_search_service():
    return search_service


def get_bedrock_service():
    return bedrock_service


def get_audio_device_service() -> AudioDeviceService:
    return AudioDeviceService()


def get_service_registry():
    return service_registry
