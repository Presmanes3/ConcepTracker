from langgraph.graph import StateGraph, START, END

# Core Schemas
from shared.schemas.workflow.ingest import IngestState
from shared.schemas.models.note import Note
from shared.schemas.models.link import Link

# Specialized Repositories
from src.repository.note_repository import note_repository
from src.repository.link_repository import link_repository

# Shared Services
from src.services.embedding_service import embedding_service
from src.services.cost_service import cost_service

# Fully decoupled Agents
from src.agents.normalizer_agent import NormalizerAgent
from src.agents.taxonomy_agent import ConceptTaxonomyAgent
from src.agents.gatekeeper_agent import GatekeeperAgent
from src.agents.bidirectional_linker_agent import BidirectionalLinkerAgent

# Geography sub-workflow
from src.workflows.geo_workflow import geo_graph
from shared.schemas.workflow.geo import GeoState

def normalize_and_embed(state: IngestState):
    """Nodo 1: Ingest Agent - Limpia y genera Embeddings + Summary."""
    agent = NormalizerAgent()
    update = agent.run(state)
    
    # Embedding still shared via service (Singleton)
    vector = embedding_service.get_embedding(update["content"])
    update["embedding"] = vector
    
    return update

def classify_concept(state: IngestState):
    """Node 1b: Extract semantic taxonomy before retrieval (domain, concept_type, is_component_of)."""
    agent = ConceptTaxonomyAgent()
    return agent.run(state)


def search_before_save(state: IngestState):
    """Find similar notes before committing to DB."""
    from src.utils.embeddings import DISTANCE_DEDUP_CUTOFF
    raw_similar = note_repository.get_similar_notes(
        current_id=None,
        embedding=state.embedding,
        query_text=state.content,
        limit=5
    )
    # Only near-identical concepts reach the Gatekeeper
    filtered = [n for n in raw_similar if n.get("distance", 1.0) < DISTANCE_DEDUP_CUTOFF]
    return {"similar_notes": filtered}

def gatekeeper_decision(state: IngestState):
    """Decide if it is a new note, a merge, or a duplicate."""
    agent = GatekeeperAgent()
    return agent.run(state)

def update_existing_note(state: IngestState):
    """Updates an existing note instead of creating a new one."""
    note_repository.update_note(
        note_id=state.note_id, 
        summary=state.summary 
        # Optionally merge content if needed, for now just summary
    )
    return {"note_id": state.note_id}

def save_note_to_db(state: IngestState):
    """Nodo Ingest: Guarda en Postgres."""
    taxonomy = state.taxonomy
    new_note = Note(
        content=state.content,
        summary=state.summary,
        embedding=state.embedding,
        tags=state.tags,
        domain=taxonomy.domain if taxonomy else None,
        domain_family=taxonomy.domain_family if taxonomy else None,
    )
    saved_note = note_repository.save_note(new_note)
    return {"note_id": saved_note.id}

def search_related_for_linking(state: IngestState):
    """
    Hybrid linking candidate pool: vector + BM25 + RRF fusion.

    Replaces the old vector-only get_similar_notes call with the full hybrid
    search pipeline so BM25 lexical signal boosts same-domain candidates.

    Temporal notes (recent) are only included when they are either:
      • semantically close (distance < TEMPORAL_MAX_DISTANCE), OR
      • sharing the same domain_family as the new note.
    This prevents spurious cross-domain links from the temporal heuristic.
    """
    from src.services.search_service import search_service
    from src.utils.rrf import rrf_fuse
    from src.utils.embeddings import DISTANCE_LINKING_CUTOFF

    # Recent notes beyond this cosine distance also need domain_family match
    TEMPORAL_MAX_DISTANCE = 0.70

    # 1. Hybrid candidates (vector + BM25 + RRF)
    vector_candidates = search_service.vector_search(
        embedding=state.embedding,
        limit=20,
        exclude_id=state.note_id,
        threshold=DISTANCE_LINKING_CUTOFF,
    )
    bm25_candidates = search_service.bm25_search(
        query_text=state.content,
        limit=20,
        exclude_id=state.note_id,
    )

    # Distance lookup map (used later for temporal filtering)
    distance_by_id = {n["id"]: n["distance"] for n in vector_candidates}

    # Fuse; first-seen item dict carries its original fields
    fused = rrf_fuse(bm25_candidates, vector_candidates, id_key="id")

    # Ensure every fused item has a `distance` field.
    # BM25-only hits (no vector match) get a conservative Moderate-tier estimate.
    fused_ids: set = set()
    for item in fused:
        if "distance" not in item or item["distance"] is None:
            item["distance"] = distance_by_id.get(item["id"], 0.65)
        item.setdefault("is_recent", False)
        fused_ids.add(item["id"])

    # 2. Temporal context — domain + distance aware
    raw_recent = note_repository.get_recent_notes(limit=3, exclude_id=state.note_id)
    new_family = state.taxonomy.domain_family if state.taxonomy else None

    recent_notes: list = []
    for n in raw_recent:
        if n["id"] in fused_ids:
            continue  # already represented in the fused pool with correct score
        actual_dist = distance_by_id.get(n["id"], 1.0)
        cand_family = n.get("domain_family")
        same_family = bool(new_family and cand_family and new_family == cand_family)
        close_enough = actual_dist < TEMPORAL_MAX_DISTANCE

        if close_enough or same_family:
            recent_notes.append({**n, "distance": actual_dist, "is_recent": True})
        # else: semantically distant AND different domain → skip to avoid noise

    # Recent notes go first so the LLM sees temporal context before semantic hits;
    # fused semantic candidates follow ordered by RRF score.
    all_candidates = recent_notes + fused

    # 3. Enrich every candidate with multi-signal link confidence
    from src.utils.link_confidence import compute_link_confidence, SEND_TO_LLM_LOW
    rrf_top_ids = {item["id"] for item in fused[:5]}  # top-5 RRF positions
    for candidate in all_candidates:
        candidate["link_confidence"] = compute_link_confidence(
            candidate=candidate,
            new_taxonomy=state.taxonomy,
            fused_top_ids=rrf_top_ids,
        )

    return {"similar_notes": all_candidates}

def match_relations_bidirectional(state: IngestState):
    """Confidence-first bidirectional linker: one LLM call for both directions."""
    agent = BidirectionalLinkerAgent()
    return agent.run(state)


def save_all_links(state: IngestState):
    """Persist all links produced by BidirectionalLinkerAgent.

    FORWARD links:  source=new_note, target=existing_note  (standard direction)
    BACKWARD links: source=existing_note, target=new_note  (retro direction)
    Duplicate guard runs on BACKWARD links only (FORWARD duplicates are
    impossible since the new note didn't exist before this run).
    """
    for lnk in state.links:
        raw = lnk if isinstance(lnk, dict) else lnk.model_dump()
        direction = raw.get("direction", "FORWARD")
        relation_type = raw.get("relation_type", "RELATES")
        reason = raw.get("reason", "")

        if direction == "BACKWARD":
            source_id = raw.get("source_id")
            target_id = state.note_id
            if not source_id:
                continue
            # Dedup: skip if this existing note already links to the new note
            existing = link_repository.get_links_by_source(source_id)
            if any(e.target_id == target_id for e in existing):
                continue
        else:  # FORWARD
            source_id = state.note_id
            target_id = raw.get("target_id")
            if not target_id:
                continue

        link_repository.save_link(Link(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            reason=reason,
        ))
    return {"links": state.links}

def detect_archipelago(state: IngestState):
    """
    Bridge node: delegates all geography decisions to the geo_graph sub-workflow.
    Converts IngestState → GeoState, invokes geo_graph, maps results back.
    """
    geo_input = GeoState(
        note_id=state.note_id,
        note_summary=state.summary or "",
        links=state.links or [],
    )

    geo_result: dict = geo_graph.invoke(geo_input)

    return {
        "archipelago_action": geo_result.get("archipelago_action", "NONE"),
        "archipelago_id": geo_result.get("archipelago_id"),
        "archipelago_name": geo_result.get("archipelago_name"),
        "archipelago_summary": geo_result.get("proposed_arch_summary"),
    }

# Router for the Gatekeeper
def gatekeeper_router(state: IngestState):
    return state.action

# Define the Graph
workflow = StateGraph(IngestState)
workflow.add_node("normalize", normalize_and_embed)
workflow.add_node("classify_concept", classify_concept)
workflow.add_node("search_pre", search_before_save)
workflow.add_node("gatekeeper", gatekeeper_decision)
workflow.add_node("save_note", save_note_to_db)
workflow.add_node("update_note", update_existing_note)
workflow.add_node("search_links", search_related_for_linking)
workflow.add_node("match_relations", match_relations_bidirectional)
workflow.add_node("save_links", save_all_links)
workflow.add_node("detect_archipelago", detect_archipelago)

# Wiring
workflow.add_edge(START, "normalize")
workflow.add_edge("normalize", "classify_concept")
workflow.add_edge("classify_concept", "search_pre")
workflow.add_edge("search_pre", "gatekeeper")

workflow.add_conditional_edges(
    "gatekeeper",
    gatekeeper_router,
    {
        "CREATE": "save_note",
        "MERGE": "update_note",
        "SKIP": END
    }
)

workflow.add_edge("save_note", "search_links")
workflow.add_edge("search_links", "match_relations")
workflow.add_edge("match_relations", "save_links")
workflow.add_edge("save_links", "detect_archipelago")
workflow.add_edge("detect_archipelago", END)
workflow.add_edge("update_note", END)

ingest_graph = workflow.compile()
