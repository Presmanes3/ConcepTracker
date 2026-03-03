"""
src/utils/link_confidence.py
══════════════════════════════════════════════════════════════════════════════
Multi-signal link confidence scorer.

Pure Python — no LLM, no DB. Consumes fields already present on each
candidate dict produced by `search_related_for_linking`.

## Score composition (weights sum to 1.0)

  Vector similarity   0.35   → 1 - distance/CUTOFF, clamped [0, 1]
  Lexical (BM25)      0.25   → min(lexical_score / LEXICAL_SCALE, 1.0)
  RRF top-5 bonus     0.15   → bool: candidate in top-5 of fused pool
  Domain family       0.15   → exact match new_family == cand_family
  Temporal recency    0.10   → is_recent flag set by search_related_for_linking

## Special cases
  • `is_component_of` (parent concept): score forced to 1.0 → auto-link, no LLM.
  • Missing `distance` (BM25-only hit): treated as moderate vector signal (0.60).
  • `domain_family` is None on either side: family component scores 0.

## Confidence zones (used by BidirectionalLinkerAgent)

  AUTO_LINK_THRESHOLD  = 0.90   → link without LLM call (very high confidence)
  SEND_TO_LLM_LOW      = 0.15   → candidates below this are dropped pre-LLM

The scores and individual signal breakdown are injected into the LLM prompt
so the model can treat them as calibrated evidence rather than relying on its
own raw intuition about embedding cosine distances.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# ── Tuneable constants ────────────────────────────────────────────────────────

DISTANCE_CUTOFF: float = 0.95       # same as DISTANCE_LINKING_CUTOFF in embeddings.py
LEXICAL_SCALE: float = 0.40         # ts_rank_cd value considered "perfect" BM25 hit
RRF_TOP_N: int = 5                  # top-N fused pool treated as RRF bonus

WEIGHT_VECTOR: float = 0.35
WEIGHT_LEXICAL: float = 0.20
WEIGHT_RRF_TOP: float = 0.15
WEIGHT_FAMILY: float = 0.15   # exact domain_family match
WEIGHT_DOMAIN: float = 0.08   # same broad domain (even if different family)
WEIGHT_TEMPORAL: float = 0.07

AUTO_LINK_THRESHOLD: float = 0.90
SEND_TO_LLM_LOW: float = 0.25


# ── Main entry point ──────────────────────────────────────────────────────────

def compute_link_confidence(
    candidate: Dict[str, Any],
    new_taxonomy,                       # Optional[ConceptTaxonomy] — avoid circular import
    fused_top_ids: Optional[set] = None,
) -> Dict[str, Any]:
    """Compute a composite confidence score for a linking candidate.

    Args:
        candidate: Dict with keys: id, distance (optional), lexical_score
            (optional), domain_family (optional), is_recent (bool).
        new_taxonomy: ``ConceptTaxonomy`` instance from the IngestState, or
            ``None`` if classification failed.
        fused_top_ids: Set of note IDs that sit in the top-``RRF_TOP_N``
            positions of the RRF-fused pool. Pass ``None`` to skip this signal.

    Returns:
        Dict with keys:
          ``score``   — float ∈ [0, 1] composite confidence
          ``auto``    — bool: True if score >= AUTO_LINK_THRESHOLD
          ``signals`` — dict breakdown for prompt injection
    """
    cand_id: int = candidate["id"]
    is_recent: bool = bool(candidate.get("is_recent", False))
    distance: float = candidate.get("distance", 0.60)   # default = moderate
    lexical: float = float(candidate.get("lexical_score") or 0.0)
    cand_family: Optional[str] = candidate.get("domain_family") or None

    new_family: Optional[str] = (
        new_taxonomy.domain_family if new_taxonomy else None
    )
    new_domain: Optional[str] = (
        new_taxonomy.domain if new_taxonomy else None
    )
    is_component_of: Optional[str] = (
        new_taxonomy.is_component_of if new_taxonomy else None
    )
    summary: str = candidate.get("summary", "")

    # ── Parent concept override ───────────────────────────────────────────────
    is_parent = bool(
        is_component_of and is_component_of.lower() in summary.lower()
    )
    if is_parent:
        return {
            "score": 1.0,
            "auto": True,
            "signals": {
                "vector": "PARENT",
                "lexical": "PARENT",
                "rrf_top": True,
                "same_family": True,
                "recent": is_recent,
                "parent": True,
            },
        }

    # ── Individual signals ────────────────────────────────────────────────────

    # Vector: convert cosine distance → similarity, normalise to [0, 1]
    vector_sim = max(0.0, 1.0 - distance / DISTANCE_CUTOFF)
    vector_contrib = vector_sim * WEIGHT_VECTOR

    # Lexical: BM25 ts_rank_cd, normalised
    lexical_norm = min(lexical / LEXICAL_SCALE, 1.0)
    lexical_contrib = lexical_norm * WEIGHT_LEXICAL

    # RRF top-N
    in_rrf_top = bool(fused_top_ids and cand_id in fused_top_ids)
    rrf_contrib = WEIGHT_RRF_TOP if in_rrf_top else 0.0

    # Domain family (exact match)
    same_family = bool(
        new_family and cand_family and new_family == cand_family
    )
    family_contrib = WEIGHT_FAMILY if same_family else 0.0

    # Domain (broad category — partial credit when family differs)
    cand_domain: Optional[str] = candidate.get("domain") or None
    same_domain = bool(
        new_domain and cand_domain and new_domain == cand_domain
    )
    # Only award domain credit when families differ (same-family already gets family credit)
    domain_contrib = WEIGHT_DOMAIN if (same_domain and not same_family) else 0.0

    # Temporal
    temporal_contrib = WEIGHT_TEMPORAL if is_recent else 0.0

    score = vector_contrib + lexical_contrib + rrf_contrib + family_contrib + domain_contrib + temporal_contrib
    score = min(max(score, 0.0), 1.0)

    # Human-readable signal labels for the LLM prompt
    if vector_sim >= 0.58:
        vec_label = "High"
    elif vector_sim >= 0.21:
        vec_label = "Moderate"
    else:
        vec_label = "Low"

    if lexical_norm >= 0.5:
        lex_label = "High"
    elif lexical_norm >= 0.1:
        lex_label = "Moderate"
    else:
        lex_label = "None"

    return {
        "score": round(score, 3),
        "auto": score >= AUTO_LINK_THRESHOLD,
        "signals": {
            "vector": vec_label,
            "lexical": lex_label,
            "rrf_top": in_rrf_top,
            "same_family": same_family,
            "same_domain": same_domain,
            "recent": is_recent,
            "parent": False,
        },
    }


def format_confidence_line(candidate: Dict[str, Any]) -> str:
    """Format a candidate's confidence data as a single-line string for the LLM prompt.

    Example output::

        confidence=0.74 | vector=High | lexical=Moderate | family=Yes | rrf_top=Yes | recent=No

    Expects the candidate dict to already carry a ``link_confidence`` key
    (populated by ``compute_link_confidence``).
    """
    lc = candidate.get("link_confidence", {})
    score = lc.get("score", 0.0)
    s = lc.get("signals", {})

    parts = [
        f"confidence={score:.2f}",
        f"vector={s.get('vector', '?')}",
        f"lexical={s.get('lexical', '?')}",
        f"family={'Yes' if s.get('same_family') else ('SameDomain' if s.get('same_domain') else 'No')}",
        f"rrf_top={'Yes' if s.get('rrf_top') else 'No'}",
        f"recent={'Yes' if s.get('recent') else 'No'}",
    ]
    if s.get("parent"):
        parts.insert(0, "PARENT_CONCEPT")

    return " | ".join(parts)
