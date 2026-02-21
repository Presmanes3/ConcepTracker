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
from src.agents.linker_agent import LinkerAgent
from src.agents.retrospective_linker_agent import RetrospectiveLinkerAgent

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
    Re-search to find link candidates for THE NEW NOTE only.

    Returns the top-10 nearest neighbours filtered by DISTANCE_LINKING_CUTOFF,
    plus the 3 most recently created notes to capture temporal context (stream of consciousness).
    """
    from src.utils.embeddings import DISTANCE_LINKING_CUTOFF
    
    # 1. Semantic + Lexical Candidates
    candidates = note_repository.get_similar_notes(
        current_id=state.note_id,
        embedding=state.embedding,
        query_text=state.content,
        limit=10,
    )
    filtered_semantic = [n for n in candidates if n.get("distance", 1.0) < DISTANCE_LINKING_CUTOFF]
    
    # 2. Temporal Candidates (Recent Notes)
    recent_notes = note_repository.get_recent_notes(limit=3, exclude_id=state.note_id)
    
    # 3. Merge and deduplicate
    seen_ids = set()
    final_candidates = []
    
    # Add recent notes first (they get priority in the prompt)
    for n in recent_notes:
        if n["id"] not in seen_ids:
            final_candidates.append(n)
            seen_ids.add(n["id"])
            
    # Add semantic notes
    for n in filtered_semantic:
        if n["id"] not in seen_ids:
            final_candidates.append(n)
            seen_ids.add(n["id"])
            
    return {"similar_notes": final_candidates}

def match_relations(state: IngestState):
    """LLM decide relaciones para la nueva nota."""
    agent = LinkerAgent()
    return agent.run(state)

def save_links_to_db(state: IngestState):
    """Persist forward links (new note → existing notes)."""
    for lnk in state.links:
        if isinstance(lnk, dict):
            target_id = lnk["target_id"]
            relation_type = lnk["relation_type"]
            reason = lnk["reason"]
        else:
            target_id = lnk.target_id
            relation_type = lnk.relation_type
            reason = lnk.reason
        link_repository.save_link(Link(
            source_id=state.note_id,
            target_id=target_id,
            relation_type=relation_type,
            reason=reason,
        ))
    return {"links": state.links}


def check_retrospective_links(state: IngestState):
    """Find links that existing notes should create TO the new note (reverse direction)."""
    agent = RetrospectiveLinkerAgent()
    return agent.run(state)


def save_retrospective_links_to_db(state: IngestState):
    """Persist retroactive links (existing notes → new note)."""
    for lnk in state.retrospective_links:
        source_id = lnk.get("source_id")
        if not source_id:
            continue
        # Avoid duplicate: check if source already links to new note
        existing_outgoing = link_repository.get_links_by_source(source_id)
        already = any(e.target_id == state.note_id for e in existing_outgoing)
        if already:
            continue
        link_repository.save_link(Link(
            source_id=source_id,
            target_id=state.note_id,
            relation_type=lnk.get("relation_type", "RELATES"),
            reason=lnk.get("reason", ""),
        ))
    return {}

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
workflow.add_node("match_relations", match_relations)
workflow.add_node("save_links", save_links_to_db)
workflow.add_node("check_retro_links", check_retrospective_links)
workflow.add_node("save_retro_links", save_retrospective_links_to_db)
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
workflow.add_edge("save_links", "check_retro_links")
workflow.add_edge("check_retro_links", "save_retro_links")
workflow.add_edge("save_retro_links", "detect_archipelago")
workflow.add_edge("detect_archipelago", END)
workflow.add_edge("update_note", END)

ingest_graph = workflow.compile()
