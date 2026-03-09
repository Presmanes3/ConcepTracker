"""
src/agents/bidirectional_linker_agent.py
══════════════════════════════════════════════════════════════════════════════
Confidence-first bidirectional linker.

## Design

Unlike the old two-agent approach (LinkerAgent → RetrospectiveLinkerAgent),
this agent handles BOTH forward and backward links in a single LLM call,
guided by pre-computed multi-signal confidence scores from `link_confidence.py`.

## Pipeline inside this agent

  1. Receive candidates already enriched with `link_confidence` (score + signals).
  2. AUTO-LINK: candidates with score >= AUTO_LINK_THRESHOLD (0.90) are linked
     without any LLM call — they are semantically unambiguous.
  3. SEND TO LLM: candidates in [0.25, 0.90) go to one single LLM call that
     asks for BOTH forward and backward links simultaneously.
  4. DROP: candidates below 0.25 are silently discarded before the LLM sees them.

## Cost

  0 ambiguous candidates -> 0 LLM calls (only auto-links)
  n ambiguous candidates -> 1 LLM call (both directions decided at once)

  This is strictly cheaper than the old system:
    old: 1 forward call + 1 retro call + N backward validation calls
    new: max 1 call, regardless of pool size

## Output

  {"links": [LinkItem, ...], "retrospective_links": []}

  The link items carry `direction` ("FORWARD" or "BACKWARD") and `source_id`
  (set only for BACKWARD links).  `ingest_workflow.save_all_links` uses these
  fields to route each link to the correct DB row.

  retrospective_links is always [] -- it exists only for backward compatibility
  with the workflow state schema; the old RetrospectiveLinkerAgent is no longer called.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from shared.prompts.bidirectional_linker import BIDIRECTIONAL_LINKING_PROMPT
from shared.schemas.agents.linker import LinkItem, LinkerResult
from shared.schemas.workflow.ingest import IngestState
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry
from src.utils.link_confidence import (
    AUTO_LINK_THRESHOLD,
    NEAR_MISS_MIN,
    SEND_TO_LLM_LOW,
    format_confidence_line,
)

logger = logging.getLogger(__name__)


@agent_registry.register("bidirectional_linker")
class BidirectionalLinkerAgent(BaseAgent[IngestState, LinkerResult]):
    """
    Single-call confidence-first bidirectional linker.
    Replaces both LinkerAgent and RetrospectiveLinkerAgent.
    """

    def __init__(self) -> None:
        super().__init__(task_name="bidirectional_linking")

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, state: IngestState) -> Dict[str, Any]:
        """Compute all links (both directions) for the ingested note.

        Returns:
            {"links": [list of link dicts], "retrospective_links": [], "near_miss_candidates": [...]}

        near_miss_candidates contains:
          - Pre-LLM drops: score in [NEAR_MISS_MIN, SEND_TO_LLM_LOW)
          - LLM-rejected: went to LLM but the model decided SKIP
        Used by the --review CLI flag for human-in-the-loop confirmation.
        """
        if not state.similar_notes:
            logger.debug("[BidirectionalLinker] No candidates -- skipping.")
            return {"links": [], "retrospective_links": [], "near_miss_candidates": []}

        # Fast lookup: candidate dict by note ID
        candidate_by_id: Dict[int, Dict[str, Any]] = {c["id"]: c for c in state.similar_notes}

        # ── Partition candidates by confidence zone ───────────────────────────
        auto_links: List[Dict[str, Any]] = []
        llm_candidates: List[Dict[str, Any]] = []
        near_miss_pre_llm: List[Dict[str, Any]] = []   # [NEAR_MISS_MIN, SEND_TO_LLM_LOW)

        for candidate in state.similar_notes:
            lc = candidate.get("link_confidence", {})
            score = lc.get("score", 0.0)

            if score >= AUTO_LINK_THRESHOLD or lc.get("signals", {}).get("parent"):
                auto_links.append(candidate)
                logger.debug(
                    "[BidirectionalLinker] AUTO-LINK id=%s score=%.2f",
                    candidate["id"], score,
                )
            elif score >= SEND_TO_LLM_LOW:
                llm_candidates.append(candidate)
            elif score >= NEAR_MISS_MIN:
                near_miss_pre_llm.append(candidate)
                logger.debug(
                    "[BidirectionalLinker] NEAR-MISS id=%s score=%.2f (pre-LLM drop)",
                    candidate["id"], score,
                )
            else:
                logger.debug(
                    "[BidirectionalLinker] NOISE id=%s score=%.2f (below NEAR_MISS_MIN)",
                    candidate["id"], score,
                )

        # ── Build auto-link results (no LLM) ─────────────────────────────────
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
            # Parent concepts also get a backward link
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

        # ── LLM call for ambiguous zone ───────────────────────────────────────
        llm_links: List[Dict[str, Any]] = []
        if llm_candidates:
            logger.debug(
                "[BidirectionalLinker] LLM call for %d ambiguous candidates",
                len(llm_candidates),
            )
            llm_links = self._run_llm_pass(state, llm_candidates)

            # Attach confidence signals to each LLM-confirmed link
            for lnk in llm_links:
                direction = lnk.get("direction", "FORWARD")
                lookup_id = lnk.get("source_id") if direction == "BACKWARD" else lnk.get("target_id")
                cand = candidate_by_id.get(lookup_id)
                if cand:
                    lnk["confidence"] = cand.get("link_confidence", {})

            result_links.extend(llm_links)

        # ── Compute near-miss candidates (for --review UX) ───────────────────
        llm_confirmed_ids: set = set()
        for lnk in llm_links:
            direction = lnk.get("direction", "FORWARD")
            confirmed_id = lnk.get("source_id") if direction == "BACKWARD" else lnk.get("target_id")
            if confirmed_id:
                llm_confirmed_ids.add(confirmed_id)

        llm_rejected = [c for c in llm_candidates if c["id"] not in llm_confirmed_ids]
        near_miss_candidates = near_miss_pre_llm + llm_rejected

        logger.info(
            "[BidirectionalLinker] note_id=%s  total_links=%d  (auto=%d  llm=%d)  near_misses=%d",
            state.note_id,
            len(result_links),
            len(auto_links),
            len(llm_links),
            len(near_miss_candidates),
        )

        return {"links": result_links, "retrospective_links": [], "near_miss_candidates": near_miss_candidates}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_llm_pass(
        self,
        state: IngestState,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build the prompt, call the LLM, return validated link dicts."""
        taxonomy = state.taxonomy

        is_component_of: Optional[str] = taxonomy.is_component_of if taxonomy else None
        parent_hint = (
            f"Note: taxonomy flags this note as a sub-concept of '{is_component_of}'. "
            f"If '{is_component_of}' appears in a candidate, you MUST create a REINFORCES link."
            if is_component_of else ""
        )

        candidate_lines: List[str] = []
        for c in candidates:
            score_line = format_confidence_line(c)
            summary = c.get("summary") or c.get("content", "")[:200]
            candidate_lines.append(
                f"[{score_line}]\nID {c['id']}: {summary}"
            )

        messages = BIDIRECTIONAL_LINKING_PROMPT.format_messages(
            new_note_id=state.note_id or "NEW",
            new_note=state.content,
            domain=taxonomy.domain if taxonomy else "unknown",
            domain_family=taxonomy.domain_family if taxonomy else "unknown",
            concept_type=taxonomy.concept_type if taxonomy else "unknown",
            parent_hint=parent_hint,
            candidates="\n\n".join(candidate_lines),
        )

        data: LinkerResult = self._call_llm(messages, output_schema=LinkerResult)
        if not data or not data.links:
            return []

        validated: List[Dict[str, Any]] = []
        for lnk in data.links:
            d = lnk.model_dump()
            if d.get("direction") == "BACKWARD" and not d.get("source_id"):
                logger.warning(
                    "[BidirectionalLinker] BACKWARD link missing source_id -- skipped. raw=%s", d
                )
                continue
            validated.append(d)

        return validated
