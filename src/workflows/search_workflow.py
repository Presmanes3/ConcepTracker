"""Hybrid search pipeline: expand → embed → retrieve (BM25 + vector) → RRF → rerank."""
import logging
from typing import Any, Dict, List

from langgraph.graph import END, START, StateGraph

from shared.schemas.workflow.search import SearchState
from src.agents.query_expansion_agent import QueryExpansionAgent
from src.repository.config_repository import config_repository
from src.services.embedding_service import embedding_service
from src.services.rerank_service import rerank_service
from src.services.search_service import search_service
from src.utils.rrf import rrf_fuse

logger = logging.getLogger(__name__)

# ── Module-level agent singleton ──────────────────────────────────────────────

_query_expander = QueryExpansionAgent()


# ── Node implementations ───────────────────────────────────────────────────────

def expand_query(state: SearchState) -> Dict[str, Any]:
    """Generate alternative phrasings via QueryExpansionAgent."""
    result = _query_expander.run(state)
    logger.debug(
        "[expand_query] query=%r  expansions=%r",
        state.query,
        result.get("expanded_queries"),
    )
    return result


def embed_query(state: SearchState) -> Dict[str, Any]:
    """Embed the original query with Titan v2."""
    vector = embedding_service.get_embedding(state.query)
    logger.debug("[embed_query] query=%r  dims=%d", state.query, len(vector))
    return {"query_embedding": vector}


def retrieve_vector(state: SearchState) -> Dict[str, Any]:
    """Run vector cosine-distance search for every query variant."""
    settings = config_repository.get_settings()
    limit = settings.search.top_k_before_rerank

    seen: Dict[int, Dict[str, Any]] = {}

    # Merge vector search candidates from the original query and its expansions,
    # de-duplicating by document id so each candidate is considered at most once.
    # Always search the original embedding first.
    for row in search_service.vector_search(state.query_embedding, limit=limit):
        seen[row["id"]] = row

    # Re-embed each expansion and search.
    for q in state.expanded_queries:
        vec = embedding_service.get_embedding(q)
        for row in search_service.vector_search(vec, limit=limit):
            if row["id"] not in seen:
                seen[row["id"]] = row

    result = {"vector_results": list(seen.values())}
    logger.debug(
        "[retrieve_vector] unique candidates=%d  (original+expansions=%d queries)",
        len(seen),
        len(state.expanded_queries) + 1,
    )
    return result


def retrieve_bm25(state: SearchState) -> Dict[str, Any]:
    """Run FTS search for every query variant."""
    settings = config_repository.get_settings()
    limit = settings.search.top_k_before_rerank
    language = settings.search.language

    all_queries = [state.query] + state.expanded_queries
    seen: Dict[int, Dict[str, Any]] = {}

    for q in all_queries:
        for row in search_service.bm25_search(q, limit=limit, language=language):
            if row["id"] not in seen:
                seen[row["id"]] = row

    result = {"bm25_results": list(seen.values())}
    logger.debug(
        "[retrieve_bm25] unique candidates=%d  language=%r",
        len(seen),
        language,
    )
    return result


def fuse_results(state: SearchState) -> Dict[str, Any]:
    """Merge BM25 and vector ranked lists with Reciprocal Rank Fusion."""
    settings = config_repository.get_settings()
    fused = rrf_fuse(
        state.bm25_results,
        state.vector_results,
        k=settings.search.rrf_k,
    )
    fused_top = fused[: settings.search.top_k_before_rerank]
    logger.debug(
        "[fuse_results] bm25=%d  vector=%d  fused→top=%d",
        len(state.bm25_results),
        len(state.vector_results),
        len(fused_top),
    )
    return {"fused_results": fused_top}


def rerank_results(state: SearchState) -> Dict[str, Any]:
    """Call Cohere Rerank 3.5 on the fused candidate list.

    Falls back to RRF-ordered results if reranking is unavailable (e.g. IAM
    permissions not yet granted for ``bedrock:Rerank``).
    """
    settings = config_repository.get_settings()
    try:
        reranked = rerank_service.rerank(
            query=state.query,
            candidates=state.fused_results,
            top_n=settings.search.rerank_top_n,
            model_id=settings.search.reranker_model,
        )
        logger.debug(
            "[rerank_results] reranker=cohere  top=%d  scores=%s",
            len(reranked),
            [round(r.get("rerank_score", 0), 3) for r in reranked],
        )
        return {"reranked_results": reranked}
    except Exception as exc:
        logger.warning(
            "[rerank_results] Reranking unavailable (%s); falling back to RRF order.", exc
        )
        # Inject a synthetic rerank_score from the existing rrf_score so
        # downstream consumers always see a consistent key.
        # Normalize RRF scores to [0, 1] so the display percentage is meaningful.
        top = state.fused_results[: settings.search.rerank_top_n]
        raw_scores = [r.get("rrf_score", 0.0) for r in top]
        lo, hi = (min(raw_scores), max(raw_scores)) if raw_scores else (0.0, 1.0)
        span = hi - lo or 1.0
        fallback = [
            {**r, "rerank_score": (r.get("rrf_score", 0.0) - lo) / span}
            for r in top
        ]
        logger.debug(
            "[rerank_results] fallback RRF  top=%d  scores=%s",
            len(fallback),
            [round(r["rerank_score"], 3) for r in fallback],
        )
        return {"reranked_results": fallback}


# ── Graph assembly ─────────────────────────────────────────────────────────────

_graph = StateGraph(SearchState)

_graph.add_node("expand_query", expand_query)
_graph.add_node("embed_query", embed_query)
_graph.add_node("retrieve_vector", retrieve_vector)
_graph.add_node("retrieve_bm25", retrieve_bm25)
_graph.add_node("fuse_results", fuse_results)
_graph.add_node("rerank_results", rerank_results)

_graph.add_edge(START, "expand_query")
_graph.add_edge(START, "embed_query")
_graph.add_edge("expand_query", "retrieve_bm25")
# embed_query must finish before retrieve_vector (needs the embedding).
_graph.add_edge("embed_query", "retrieve_vector")
_graph.add_edge("retrieve_bm25", "fuse_results")
_graph.add_edge("retrieve_vector", "fuse_results")
_graph.add_edge("fuse_results", "rerank_results")
_graph.add_edge("rerank_results", END)

search_graph = _graph.compile()


def run_search(query: str) -> List[Dict[str, Any]]:
    """Execute the full hybrid search pipeline and return reranked results.

    Args:
        query: The user's natural-language search query.

    Returns:
        List of result dicts ordered by Cohere relevance score, each containing
        at minimum: id, content, summary, rerank_score.
    """
    initial_state = SearchState(query=query)
    # LangGraph returns a plain dict, not the typed state object.
    result: Dict[str, Any] = search_graph.invoke(initial_state)
    results = result.get("reranked_results", [])
    logger.info(
        "[run_search] query=%r  results=%d  top_ids=%s",
        query,
        len(results),
        [r["id"] for r in results[:5]],
    )
    return results
