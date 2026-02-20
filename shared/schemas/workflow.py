from typing import List

from pydantic import BaseModel, Field, ConfigDict


from shared.schemas.normalizer_agent import NormalizerAgentInput
from shared.schemas.chunk_embed_agent import ChunkEmbedAgentOutput

# Usamos herencia múltiple para "componer" el estado global
class WorkflowState(NormalizerAgentInput, ChunkEmbedAgentOutput):
    """
    SSoT que hereda automáticamente todos los campos de los agentes.
    Solo añade campos específicos de la orquestación del grafo.
    """
    model_config = ConfigDict(extra='forbid', validate_assignment=True)

    # Campos específicos del flujo que no pertenecen a ningún agente en particular
    pipeline_errors: List[str] = Field(
        default_factory=list,
        description="Registry of all non-fatal warnings or errors during processing."
    )
    current_step: str = Field(
        default="start",
        description="Identifies the current active node in the graph."
    )
