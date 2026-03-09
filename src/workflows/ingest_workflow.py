"""Full ingest pipeline: normalize → classify → search → gatekeeper → save → link → detect geography."""
from langgraph.graph import StateGraph, START, END

# Core Schemas
from shared.schemas.workflow.ingest import IngestState
from shared.schemas.models.note import Note
from shared.schemas.models.link import Link

# Registry
from src.registry import repos

# Shared Services
from src.services.embedding_service import embedding_service

# Fully decoupled Agents
from src.agents.normalizer_agent import NormalizerAgent
from src.agents.taxonomy_agent import ConceptTaxonomyAgent
from src.agents.gatekeeper_agent import GatekeeperAgent
from src.agents.bidirectional_linker_agent import BidirectionalLinkerAgent

# Utilities and services used in linking nodes
from src.utils.embeddings import DISTANCE_DEDUP_CUTOFF, DISTANCE_LINKING_CUTOFF
from src.utils.link_confidence import compute_link_confidence
from src.utils.rrf import rrf_fuse
from src.services.search_service import search_service
import logging

logger = logging.getLogger(__name__)

# ── Module-level agent singletons ─────────────────────────────────────────────────
_normalizer = NormalizerAgent()
_taxonomy = ConceptTaxonomyAgent()
_gatekeeper = GatekeeperAgent()
_linker = BidirectionalLinkerAgent()


def normalize_and_embed(state: IngestState):
    """Node 1: Ingest Agent - Clean and generate Embeddings + Summary."""
    logger.info("--- [ingest_workflow] node: normalize_and_embed ---")
    update = _normalizer.run(state)
    
    # Embedding still shared via service (Singleton)
    vector = embedding_service.get_embedding(update["content"])
    update["embedding"] = vector
    
    logger.debug(f"[normalize_and_embed] summary length: {len(update.get('summary', ''))}")
    return update

def classify_concept(state: IngestState):
    """Node 1b: Extract semantic taxonomy before retrieval (domain, concept_type, is_component_of)."""
    logger.info("--- [ingest_workflow] node: classify_concept ---")
    result = _taxonomy.run(state)
    
    if result.get("taxonomy"):
        tax = result["taxonomy"]
        logger.debug(f"[classify_concept] domain: {tax.domain}, type: {tax.concept_type}")
    
    return result


def search_before_save(state: IngestState):
    """Find similar notes before committing to DB."""
    logger.info("--- [ingest_workflow] node: search_before_save ---")
    filtered = search_service.vector_search(
        embedding=state.embedding,
        limit=5,
        threshold=DISTANCE_DEDUP_CUTOFF,
    )
    logger.debug("[search_before_save] found %d dedup candidates", len(filtered))
    return {"similar_notes": filtered}

def gatekeeper_decision(state: IngestState):
    """Decide if it is a new note, a merge, or a duplicate."""
    logger.info("--- [ingest_workflow] node: gatekeeper ---")
    result = _gatekeeper.run(state)
    logger.info(f"[gatekeeper] decision: {result.get('action')}, reasoning: {result.get('reasoning')}")
    return result

def update_existing_note(state: IngestState):
    """Updates an existing note instead of creating a new one."""
    logger.info("--- [ingest_workflow] node: update_existing_note (ID: %s) ---", state.note_id)
    repos.notes.update_note(
        note_id=state.note_id,
        summary=state.summary,
    )
    return {"note_id": state.note_id}

def save_note_to_db(state: IngestState):
    """Ingest Node: Save to Postgres."""
    logger.info("--- [ingest_workflow] node: save_note_to_db ---")
    taxonomy = state.taxonomy
    new_note = Note(
        content=state.content,
        summary=state.summary,
        embedding=state.embedding,
        tags=state.tags,
        domain=taxonomy.domain if taxonomy else None,
        domain_family=taxonomy.domain_family if taxonomy else None,
    )
    saved_note = repos.notes.save_note(new_note)
    logger.info("[save_note_to_db] saved new note ID: %s", saved_note.id)
    return {"note_id": saved_note.id}

def search_related_for_linking(state: IngestState):
    logger.info(f"--- [ingest_workflow] node: search_related_for_linking (ID: {state.note_id}) ---")
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

    # Build distance lookup so BM25-only hits can be enriched with a vector score.
    distance_by_id = {item["id"]: item.get("distance", 1.0) for item in vector_candidates}

    # Fuse; first-seen item dict carries its original fields
    fused = rrf_fuse(bm25_candidates, vector_candidates, id_key="id")

    logger.debug(f"[search_links] vector: {len(vector_candidates)}, bm25: {len(bm25_candidates)}, fused: {len(fused)}")

    # Ensure every fused item has a `distance` field.
    # BM25-only hits (no vector match) get a conservative Moderate-tier estimate.
    fused_ids: set = set()
    for item in fused:
        if "distance" not in item or item["distance"] is None:
            item["distance"] = distance_by_id.get(item["id"], 0.65)
        item.setdefault("is_recent", False)
        fused_ids.add(item["id"])

    # 2. Temporal context — domain + distance aware
    raw_recent = repos.notes.get_recent_notes(limit=3, exclude_id=state.note_id)
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
    return _linker.run(state)


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
            existing = repos.links.get_links_by_source(source_id)
            if any(e.target_id == target_id for e in existing):
                continue
        else:  # FORWARD
            source_id = state.note_id
            target_id = raw.get("target_id")
            if not target_id:
                continue

        repos.links.save_link(Link(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            reason=reason,
        ))
    return {"links": state.links}

def detect_archipelago(state: IngestState):
    """Geography clustering — deferred. No-op until geo features are re-enabled."""
    return {}

# ── Conditional router ──────────────────────────────────────────────────────────────────

def _route_after_gatekeeper(state: IngestState) -> str:
    """Return CREATE, MERGE, or SKIP based on the gatekeeper decision."""
    return state.action


# ── Graph assembly ──────────────────────────────────────────────────────────────────

_graph = StateGraph(IngestState)
_graph.add_node("normalize", normalize_and_embed)
_graph.add_node("classify_concept", classify_concept)
_graph.add_node("search_pre", search_before_save)
_graph.add_node("gatekeeper", gatekeeper_decision)
_graph.add_node("save_note", save_note_to_db)
_graph.add_node("update_note", update_existing_note)
_graph.add_node("search_links", search_related_for_linking)
_graph.add_node("match_relations", match_relations_bidirectional)
_graph.add_node("save_links", save_all_links)
_graph.add_node("detect_archipelago", detect_archipelago)

_graph.add_edge(START, "normalize")
_graph.add_edge("normalize", "classify_concept")
_graph.add_edge("classify_concept", "search_pre")
_graph.add_edge("search_pre", "gatekeeper")

_graph.add_conditional_edges(
    "gatekeeper",
    _route_after_gatekeeper,
    {
        "CREATE": "save_note",
        "MERGE": "update_note",
        "SKIP": END,
    },
)

_graph.add_edge("save_note", "search_links")
_graph.add_edge("search_links", "match_relations")
_graph.add_edge("match_relations", "save_links")
_graph.add_edge("save_links", "detect_archipelago")
_graph.add_edge("detect_archipelago", END)
_graph.add_edge("update_note", END)

ingest_graph = _graph.compile()
