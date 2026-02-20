from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field


class GeoState(BaseModel):
    """State object for the geo_graph sub-workflow."""

    # ── Inputs (from ingest workflow) ─────────────────────────────────────────
    note_id: int
    note_summary: str
    links: List[Any] = Field(default_factory=list)  # LinkItem objects or dicts

    # ── Routing decision (set by geo_router) ──────────────────────────────────
    geo_decision: Literal["NONE", "JOIN", "CREATE"] = "NONE"

    # JOIN path: which existing archipelago to join
    target_archipelago_id: Optional[int] = None

    # CREATE path: which linked notes form the new cluster
    cluster_note_ids: List[int] = Field(default_factory=list)

    # ── LLM outputs (set by arch_namer) ───────────────────────────────────────
    proposed_arch_name: Optional[str] = None
    proposed_arch_summary: Optional[str] = None

    # ── Continent trigger (checked by geo_persister after CREATE) ─────────────
    orphan_arch_ids: List[int] = Field(default_factory=list)
    trigger_continent: bool = False
    proposed_continent_name: Optional[str] = None
    proposed_continent_summary: Optional[str] = None

    # ── Final outputs (mapped back to IngestState by the bridge node) ─────────
    archipelago_id: Optional[int] = None
    archipelago_name: Optional[str] = None
    archipelago_action: str = "NONE"
