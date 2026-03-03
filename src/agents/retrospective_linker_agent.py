"""
src/agents/retrospective_linker_agent.py
════════════════════════════════════════════════════════════════════════════════
DEPRECATED: absorbed into BidirectionalLinkerAgent (ingest_workflow.py).
Kept only so existing integration tests continue to import it without error.
Do NOT use in new code.

RetrospectiveLinkerAgent: resuelve la unidireccionalidad estructural del pipeline.

El linker estándar (forward) solo evalúa: nueva_nota → notas_existentes.
Si la nota A fue ingested antes de que existiera B, A nunca tuvo oportunidad
de linkarse a B, aunque son conceptos relacionados.

Este agente invierte la pregunta:
  "¿Qué notas EXISTENTES (que no linkearon con la nueva en el forward pass)
   deberían ahora crear un link HACIA la nueva nota?"

Arquitectura:
  1. Toma state.similar_notes — los vecinos encontrados en search_related_for_linking
  2. Filtra los ya cubiertos por el forward pass (state.links)
  3. Fetches el contenido completo de los no cubiertos desde la DB
  4. Una sola llamada LLM con todos los candidatos no cubiertos
  5. Retorna links SOURCE=existing → TARGET=new_note para ser guardados

Coste: max 1 LLM call adicional por ingest, solo cuando hay candidatos no cubiertos.
"""
from typing import Dict, Any

from pydantic import BaseModel, Field
from typing import List, Literal

from shared.schemas.workflow.ingest import IngestState
from shared.prompts.retrospective_linker import RETROSPECTIVE_LINKING_PROMPT
from src.agents.base_agent import BaseAgent
from src.repository.note_repository import note_repository
from src.utils.embeddings import similarity_tier


class RetroLinkItem(BaseModel):
    """A link created by the retrospective pass: existing note → new note."""
    source_id: int = Field(..., description="ID of the existing note that should link to the new note.")
    relation_type: Literal["REINFORCES", "RELATES"] = Field(...)
    reason: str = Field(..., description="Justification for the retroactive link.")


class RetroLinkerResult(BaseModel):
    links: List[RetroLinkItem] = Field(default_factory=list)


class RetrospectiveLinkerAgent(BaseAgent[IngestState, RetroLinkerResult]):
    """
    Finds links that should exist FROM existing notes TO the new note,
    which the forward linker could not create (because those notes were
    ingested before the new note existed).
    """

    def __init__(self):
        super().__init__(task_name="retrospective_linking")

    def run(self, state: IngestState) -> Dict[str, Any]:
        if not state.note_id or not state.similar_notes:
            return {"retrospective_links": []}

        # IDs already covered by the forward pass (either direction)
        forward_target_ids: set[int] = set()
        for lnk in state.links:
            tid = lnk.get("target_id") if isinstance(lnk, dict) else lnk.target_id
            if tid:
                forward_target_ids.add(tid)

        # Candidates not covered by forward pass, within linking range
        uncovered = [
            n for n in state.similar_notes
            if n["id"] not in forward_target_ids
            and similarity_tier(n.get("distance", 1.0)) != "Distant"
        ]

        if not uncovered:
            return {"retrospective_links": []}

        # Fetch full content for uncovered candidates from DB
        existing_notes_lines = []
        for candidate in uncovered:
            existing = note_repository.get_note_by_id(candidate["id"])
            if not existing:
                continue
            tier = similarity_tier(candidate.get("distance", 1.0))
            existing_notes_lines.append(
                f"[{tier}] ID {existing.id}: {existing.summary or existing.content[:200]}"
            )

        if not existing_notes_lines:
            return {"retrospective_links": []}

        # Build parent hint (same as forward linker)
        taxonomy = state.taxonomy
        is_component_of = taxonomy.is_component_of if taxonomy else None
        parent_hint = (
            f"Note: the new note is a sub-concept of '{is_component_of}'. "
            f"If any existing note covers '{is_component_of}', it SHOULD link to the new note."
            if is_component_of else ""
        )

        messages = RETROSPECTIVE_LINKING_PROMPT.format_messages(
            new_note_id=state.note_id,
            new_note_content=state.summary or state.content[:400],
            domain=taxonomy.domain if taxonomy else "unknown",
            domain_family=taxonomy.domain_family if taxonomy else "other",
            parent_hint=parent_hint,
            existing_notes="\n".join(existing_notes_lines),
        )

        try:
            result: RetroLinkerResult = self._call_llm(
                messages, output_schema=RetroLinkerResult
            )
            retro_links = [lnk.model_dump() for lnk in result.links] if result.links else []
        except Exception:
            retro_links = []

        return {"retrospective_links": retro_links}
