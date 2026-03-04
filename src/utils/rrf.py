"""Pure-Python Reciprocal Rank Fusion utilities with no external dependencies."""
from typing import Any, Dict, Iterable, List


def rrf_fuse(
    *ranked_lists: List[Dict[str, Any]],
    id_key: str = "id",
    k: int = 60,
) -> List[Dict[str, Any]]:
    """Merge ranked result lists using Reciprocal Rank Fusion.

    Args:
        *ranked_lists: Variable number of pre-sorted result lists. Each item
            must contain the key specified by ``id_key``.
        id_key: Field used to identify the same document across lists.
        k: Rank constant. Higher values dampen the influence of top ranks.

    Returns:
        Items sorted descending by their aggregated RRF score, with the
        ``rrf_score`` key injected into each dict.
    """
    scores: Dict[Any, float] = {}
    items: Dict[Any, Dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            doc_id = item[id_key]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            if doc_id not in items:
                items[doc_id] = item

    return sorted(
        [{**items[doc_id], "rrf_score": score} for doc_id, score in scores.items()],
        key=lambda x: x["rrf_score"],
        reverse=True,
    )


def normalize_rrf(results: List[Dict[str, Any]], score_key: str = "rrf_score") -> List[Dict[str, Any]]:
    """Normalize RRF scores to [0, 1] using min-max scaling.

    Args:
        results: Sorted result list with a numeric score field.
        score_key: Name of the score field to normalize.

    Returns:
        Same list with scores replaced by their normalized values.
    """
    if not results:
        return results
    scores = [r[score_key] for r in results]
    lo, hi = min(scores), max(scores)
    span = hi - lo or 1.0
    return [{**r, score_key: (r[score_key] - lo) / span} for r in results]
