"""
geo_workflow.py
───────────────
Multi-agent sub-workflow for Knowledge Geography decisions.

Graph topology:
  START → geo_router (pure rules, 0 LLM)
               │
    ┌──────────┼──────────┐
  "none"    "join"     "create"
    │          │           │
   END   join_executor   arch_namer (Nova Micro)
               │               │
              END         geo_persister (0 LLM)
                               │
                     continent_check_router
                        │                  │
                      "done"          "continent"
                        │                  │
                       END          continent_namer (Nova Micro)
                                          │
                                  continent_persister (0 LLM)
                                          │
                                         END

Cost per ct add:
  NONE / JOIN     → 0 LLM calls
  CREATE          → 1 × Nova Micro
  CREATE+CONTINENT→ 2 × Nova Micro
"""

from collections import Counter
from typing import Literal

from langgraph.graph import StateGraph, START, END

from shared.schemas.workflow.geo import GeoState
from shared.prompts.geo_namer import ARCH_NAMER_PROMPT, CONTINENT_NAMER_PROMPT
from src.agents.geo_namer_agent import GeoNamerAgent
from src.repository.archipelago_repository import archipelago_repository
from src.repository.note_repository import note_repository
from shared.schemas.models.archipelago import Archipelago

# ── Constants ─────────────────────────────────────────────────────────────────
# Philosophy: JOIN always wins (accumulative). CREATE fires as soon as 2+
# unassigned linked notes exist — this gives early meaningful clusters without
# requiring long batch ingestion runs.
MIN_ISLANDS = 2          # min unassigned linked notes required to form a new archipelago
MIN_ORPHAN_ARCHS = 3     # min orphan archipelagos required to form a continent

# ── Module-level agent singletons ─────────────────────────────────────────────
_geo_namer = GeoNamerAgent()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_link_attr(link, attr: str):
    """Access a link attribute whether it's a Pydantic object or a dict."""
    return getattr(link, attr, None) if hasattr(link, attr) else link.get(attr)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def geo_router(state: GeoState) -> dict:
    """
    Pure rule-based router — zero LLM calls.

    Priority order:
      1. No links → NONE
      2. Linked notes share an existing archipelago → JOIN (most common wins)
      3. >= MIN_ISLANDS unassigned linked notes → CREATE
      4. Fallback → NONE
    """
    if not state.links:
        return {"geo_decision": "NONE"}

    linked_ids = [_get_link_attr(l, "target_id") for l in state.links]
    linked_ids = [tid for tid in linked_ids if tid is not None]

    if not linked_ids:
        return {"geo_decision": "NONE"}

    # Inspect each linked note's archipelago membership
    arch_counts: Counter = Counter()
    unassigned_ids = []

    for note_id in linked_ids:
        arch = archipelago_repository.get_archipelago_for_note(note_id)
        if arch and arch.type == "archipelago":
            arch_counts[arch.id] += 1
        else:
            unassigned_ids.append(note_id)

    # ── JOIN: at least one linked note is already in an archipelago
    if arch_counts:
        # Accumulative: JOIN always wins over CREATE.
        # Tie-break by recency — prefer the most recently created archipelago
        # so newly-formed clusters grow before older ones get diluted.
        max_count = arch_counts.most_common(1)[0][1]
        tied_ids = [aid for aid, cnt in arch_counts.items() if cnt == max_count]
        if len(tied_ids) == 1:
            target_arch_id = tied_ids[0]
        else:
            archs = [
                archipelago_repository.get_archipelago_by_id(aid)
                for aid in tied_ids
            ]
            archs = [a for a in archs if a is not None]
            target_arch_id = max(archs, key=lambda a: a.created_at).id
        return {
            "geo_decision": "JOIN",
            "target_archipelago_id": target_arch_id,
        }

    # ── CREATE: enough standalone linked notes to bootstrap a cluster
    if len(unassigned_ids) >= MIN_ISLANDS:
        return {
            "geo_decision": "CREATE",
            "cluster_note_ids": unassigned_ids,
        }

    return {"geo_decision": "NONE"}


def join_executor(state: GeoState) -> dict:
    """Assign the current note to the target archipelago. Zero LLM calls."""
    arch = archipelago_repository.get_archipelago_by_id(state.target_archipelago_id)
    if not arch:
        return {"archipelago_action": "NONE"}

    archipelago_repository.assign_note_to_archipelago(state.note_id, arch.id)

    return {
        "archipelago_id": arch.id,
        "archipelago_name": arch.name,
        "archipelago_action": "JOIN",
    }


def arch_namer(state: GeoState) -> dict:
    """
    Ask Nova Micro to name the new cluster.
    Context: anchor note summary + summaries of the unassigned linked notes.
    """
    cluster_summaries_lines = []
    for nid in state.cluster_note_ids:
        note = note_repository.get_note_by_id(nid)
        if note:
            cluster_summaries_lines.append(f"  - [Note {nid}] {note.summary}")

    cluster_summaries = (
        "\n".join(cluster_summaries_lines)
        if cluster_summaries_lines
        else "  (no additional context available)"
    )

    result = _geo_namer.name(
        ARCH_NAMER_PROMPT,
        anchor_summary=state.note_summary,
        cluster_summaries=cluster_summaries,
    )

    return {
        "proposed_arch_name": result.name,
        "proposed_arch_summary": result.summary,
    }


def geo_persister(state: GeoState) -> dict:
    """
    Persist the new archipelago, assign all cluster notes, then check for
    a continent trigger. Zero LLM calls.
    """
    arch_name = state.proposed_arch_name or f"Cluster #{state.note_id}"
    arch_summary = state.proposed_arch_summary or "Auto-formed cluster of related notes."

    new_arch = Archipelago(name=arch_name, summary=arch_summary, type="archipelago")
    saved_arch = archipelago_repository.save_archipelago(new_arch)

    # Assign the anchor note
    archipelago_repository.assign_note_to_archipelago(state.note_id, saved_arch.id)

    # Assign cluster notes that are still unassigned
    for nid in state.cluster_note_ids:
        if nid == state.note_id:
            continue
        existing = archipelago_repository.get_archipelago_for_note(nid)
        if not existing:
            archipelago_repository.assign_note_to_archipelago(nid, saved_arch.id)

    # ── Continent trigger check ────────────────────────────────────────────────
    orphan_archs = archipelago_repository.get_orphan_archipelagos()
    # Exclude the newly created arch (it doesn't have a parent yet either)
    orphan_ids = [a.id for a in orphan_archs]
    trigger_continent = len(orphan_ids) >= MIN_ORPHAN_ARCHS

    return {
        "archipelago_id": saved_arch.id,
        "archipelago_name": arch_name,
        "archipelago_action": "CREATE",
        "orphan_arch_ids": orphan_ids,
        "trigger_continent": trigger_continent,
    }


def continent_namer(state: GeoState) -> dict:
    """
    Ask Nova Micro to name the new continent.
    Context: names and summaries of the orphan archipelagos.
    """
    archipelago_lines = []
    for arch_id in state.orphan_arch_ids:
        arch = archipelago_repository.get_archipelago_by_id(arch_id)
        if arch:
            archipelago_lines.append(f"  - '{arch.name}': {arch.summary}")

    archipelago_list = (
        "\n".join(archipelago_lines)
        if archipelago_lines
        else "  (no summary available)"
    )

    result = _geo_namer.name(
        CONTINENT_NAMER_PROMPT,
        archipelago_list=archipelago_list,
    )

    return {
        "proposed_continent_name": result.name,
        "proposed_continent_summary": result.summary,
    }


def continent_persister(state: GeoState) -> dict:
    """Create the Continent and attach all orphan archipelagos to it. Zero LLM calls."""
    continent_name = state.proposed_continent_name or "Unnamed Domain"
    continent_summary = state.proposed_continent_summary or "A broad domain of related clusters."

    new_continent = Archipelago(
        name=continent_name,
        summary=continent_summary,
        type="continent",
    )
    saved_continent = archipelago_repository.save_archipelago(new_continent)

    for arch_id in state.orphan_arch_ids:
        archipelago_repository.set_continent_parent(arch_id, saved_continent.id)

    return {}   # IngestState continent data not surfaced yet; deferred to `ct refresh`


# ── Routing functions ─────────────────────────────────────────────────────────

def _route_after_geo_router(state: GeoState) -> Literal["none", "join", "create"]:
    return state.geo_decision.lower()  # type: ignore[return-value]


def _route_after_geo_persister(state: GeoState) -> Literal["continent", "done"]:
    return "continent" if state.trigger_continent else "done"


# ── Graph assembly ────────────────────────────────────────────────────────────

_graph = StateGraph(GeoState)

_graph.add_node("geo_router", geo_router)
_graph.add_node("join_executor", join_executor)
_graph.add_node("arch_namer", arch_namer)
_graph.add_node("geo_persister", geo_persister)
_graph.add_node("continent_namer", continent_namer)
_graph.add_node("continent_persister", continent_persister)

_graph.add_edge(START, "geo_router")

_graph.add_conditional_edges(
    "geo_router",
    _route_after_geo_router,
    {
        "none": END,
        "join": "join_executor",
        "create": "arch_namer",
    },
)

_graph.add_edge("join_executor", END)
_graph.add_edge("arch_namer", "geo_persister")

_graph.add_conditional_edges(
    "geo_persister",
    _route_after_geo_persister,
    {
        "done": END,
        "continent": "continent_namer",
    },
)

_graph.add_edge("continent_namer", "continent_persister")
_graph.add_edge("continent_persister", END)

geo_graph = _graph.compile()
