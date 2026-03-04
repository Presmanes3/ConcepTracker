"""
src/agents/bidirectional_linker_agent.py
══════════════════════════════════════════════════════════════════════════════
Confidence-first bidirectional linker (auto-link tier only).

## Design

Links notes using pre-computed multi-signal confidence scores from `link_confidence.py`.
Only candidates with score >= AUTO_LINK_THRESHOLD (0.90) are linked; everything below
is collected as near-miss candidates for potential human review.

## Cost

  Always 0 LLM calls.

## Output

  {"links": [LinkItem, ...], "retrospective_links": [], "near_miss_candidates": [...]}

  retrospective_links is always [] for backward compatibility with the workflow state schema.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from shared.schemas.agents.linker import LinkItem
from shared.schemas.workflow.ingest import IngestState
from src.agents.base_agent import BaseAgent
from src.utils.link_confidence import AUTO_LINK_THRESHOLD, NEAR_MISS_MIN

logger = logging.getLogger(__name__)


class BidirectionalLinkerAgent(BaseAgent[IngestState, LinkItem]):
    """
    Single-call confidence-first bidirectional linker.
    Replaces both LinkerAgent and RetrospectiveLinkerAgent.
    """

    def __init__(self) -> None:
        super().__init__(task_name="bidirectional_linking")

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, state: IngestState) -> Dict[str, Any]:
        """Compute all links for the ingested note using the auto-link tier only.

        Returns:
            Dict with ``links``, ``retrospective_links`` (always []), and
            ``near_miss_candidates`` (score in [NEAR_MISS_MIN, AUTO_LINK_THRESHOLD)
            — available for future human-in-the-loop review).
        """
        if not state.similar_notes:
            logger.debug("[BidirectionalLinker] No candidates -- skipping.")
            return {"links": [], "retrospective_links": [], "near_miss_candidates": []}

        auto_links: List[Dict[str, Any]] = []
        near_miss_candidates: List[Dict[str, Any]] = []

        for candidate in state.similar_notes:
            lc = candidate.get("link_confidence", {})
            score = lc.get("score", 0.0)

            if score >= AUTO_LINK_THRESHOLD or lc.get("signals", {}).get("parent"):
                auto_links.append(candidate)
                logger.debug(
                    "[BidirectionalLinker] AUTO-LINK id=%s score=%.2f",
                    candidate["id"], score,
                )
            elif score >= NEAR_MISS_MIN:
                near_miss_candidates.append(candidate)
                logger.debug(
                    "[BidirectionalLinker] NEAR-MISS id=%s score=%.2f",
                    candidate["id"], score,
                )
            else:
                logger.debug(
                    "[BidirectionalLinker] NOISE id=%s score=%.2f (below NEAR_MISS_MIN)",
                    candidate["id"], score,
                )

        result_links: List[Dict[str, Any]] = []

        for c in auto_links:
            lc = c.get("link_confidence", {})
            result_links.append(
                LinkItem(
                    target_id=c["id"],
                    relation_type="REINFORCES",
                    reason="Auto-linked: confidence score >= 0.90 (parent concept or near-identical semantics).",
                    direction="FORWARD",
                    confidence=lc,
                ).model_dump()
            )
            # Parent concepts also receive a backward link.
            if lc.get("signals", {}).get("parent"):
                result_links.append(
                    LinkItem(
                        target_id=state.note_id,
                        source_id=c["id"],
                        relation_type="REINFORCES",
                        reason="Auto-linked (backward): existing note is parent concept of new note.",
                        direction="BACKWARD",
                        confidence=lc,
                    ).model_dump()
                )

        logger.info(
            "[BidirectionalLinker] note_id=%s  total_links=%d  (auto=%d)  near_misses=%d",
            state.note_id,
            len(result_links),
            len(auto_links),
            len(near_miss_candidates),
        )

        return {"links": result_links, "retrospective_links": [], "near_miss_candidates": near_miss_candidates}


