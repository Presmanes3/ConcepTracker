"""POST /search — hybrid semantic search (expand → embed → BM25+vector → RRF → rerank)."""
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter

from shared.schemas.api.search import SearchRequest, SearchResponse, SearchResultItem
from src.workflows.search_workflow import run_search

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(body: SearchRequest):
    # run_search is synchronous (LangGraph) — run in a thread pool.
    reranked: List[Dict[str, Any]] = await asyncio.to_thread(run_search, body.query)

    items = [
        SearchResultItem(
            id=r["id"],
            content=r.get("content", ""),
            summary=r.get("summary", ""),
            tags=r.get("tags"),
            score=r.get("rerank_score") or r.get("rrf_score"),
            domain=r.get("domain"),
            archipelago_id=r.get("archipelago_id"),
        )
        for r in reranked[: body.limit]
    ]

    return SearchResponse(query=body.query, results=items)
