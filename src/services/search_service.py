"""Stateless BM25 + vector retrieval primitives consumed by the search workflow."""
from typing import Any, Dict, List, Optional

from sqlmodel import text
from src.utils.db import get_session


class SearchService:
    """Exposes bm25_search and vector_search as the SSoT retrieval layer.

    All higher-level consumers (search workflow, trace command) call these
    methods instead of writing their own SQL.
    """

    _instance = None

    def __new__(cls) -> "SearchService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── Vector branch ──────────────────────────────────────────────────────────

    def vector_search(
        self,
        embedding: List[float],
        limit: int = 30,
        exclude_id: Optional[int] = None,
        threshold: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Return notes ordered by cosine distance to *embedding*.

        Args:
            embedding: Query vector (1024 dimensions, Titan v2).
            limit: Maximum number of rows to return.
            exclude_id: Note ID to omit (used during ingest to skip self).
            threshold: Cosine distance ceiling; results above this are dropped.

        Returns:
            List of dicts with keys: id, content, summary, distance,
            domain, domain_family.
        """
        with get_session() as session:
            sql = text("""
                SELECT id, content, summary,
                       (embedding <=> CAST(:vec AS vector)) AS distance,
                       domain, domain_family
                FROM notes
                WHERE (:exclude_id IS NULL OR id != :exclude_id)
                  AND (embedding <=> CAST(:vec AS vector)) < :threshold
                ORDER BY distance ASC
                LIMIT :limit
            """)
            rows = session.execute(
                sql,
                {
                    "vec": str(embedding),
                    "exclude_id": exclude_id,
                    "threshold": threshold,
                    "limit": limit,
                },
            ).fetchall()

        return [
            {
                "id": r[0],
                "content": r[1],
                "summary": r[2],
                "distance": float(r[3]),
                "domain": r[4],
                "domain_family": r[5],
            }
            for r in rows
        ]

    # ── BM25 branch ────────────────────────────────────────────────────────────

    def bm25_search(
        self,
        query_text: str,
        limit: int = 30,
        exclude_id: Optional[int] = None,
        language: str = "simple",
    ) -> List[Dict[str, Any]]:
        """Return notes matching *query_text* via full-text search (GIN index).

        Args:
            query_text: User search phrase.
            limit: Maximum number of rows to return.
            exclude_id: Note ID to omit.
            language: PostgreSQL FTS dictionary (default ``"simple"`` for
                language-agnostic matching).

        Returns:
            List of dicts with keys: id, content, summary, lexical_score,
            domain, domain_family.
        """
        with get_session() as session:
            sql = text(f"""
                SELECT id, content, summary,
                       ts_rank_cd(
                           to_tsvector('{language}', coalesce(content,'') || ' ' || coalesce(summary,'')),
                           plainto_tsquery('{language}', :query_text)
                       ) AS lexical_score,
                       domain, domain_family
                FROM notes
                WHERE (:exclude_id IS NULL OR id != :exclude_id)
                  AND to_tsvector('{language}', coalesce(content,'') || ' ' || coalesce(summary,''))
                      @@ plainto_tsquery('{language}', :query_text)
                ORDER BY lexical_score DESC
                LIMIT :limit
            """)
            rows = session.execute(
                sql,
                {
                    "query_text": query_text,
                    "exclude_id": exclude_id,
                    "limit": limit,
                },
            ).fetchall()

        return [
            {
                "id": r[0],
                "content": r[1],
                "summary": r[2],
                "lexical_score": float(r[3]),
                "domain": r[4],
                "domain_family": r[5],
            }
            for r in rows
        ]


search_service = SearchService()
