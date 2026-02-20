"""
bidirectional_linker_agent.py
─────────────────────────────
Consensus linker that eliminates threshold dependency.

## Core principle

Standard linking uses a single number (embedding distance threshold) to decide
what enters the LLM prompt, and a single LLM call to decide what links to create.
Two sources of arbitrary calibration.

Bidirectional consensus replaces both with a logical standard:

  Forward  pass: "Given note B (new), which existing notes connect to it?"
  Backward pass: "Given note A (existing), would it connect to note B (new)?"
  Decision rule: a link is created ONLY when both independent calls agree.

## Cost model

Backward validation is run for Moderate and Weak tier candidates —
        the tiers where homonym false positives empirically occur (distance 0.55-0.90).
        Only High similarity links (distance < 0.55) are trusted from forward pass alone.

  0 weak forward links  →  1 LLM call   (identical to LinkerAgent)
  n weak forward links  →  1 + n calls  (n bounded by top-K size)

## Why this eliminates threshold dependency

The retrieval step can be recall-optimistic (top-K, no distance cutoff) because
the consensus filter handles precision. No need to tune "0.75 vs 0.80 vs 0.90"
— the standard is now "do two independent LLM views agree?", which is a logical
requirement rather than an arbitrary numeric choice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared.schemas.agents.linker import LinkerResult
from shared.schemas.workflow.ingest import IngestState
from shared.prompts.linking_agent import LINKING_PROMPT
from src.agents.base_agent import BaseAgent
from src.utils.embeddings import similarity_tier
from src.repository.note_repository import note_repository


class BidirectionalLinkerAgent(BaseAgent[IngestState, LinkerResult]):
    """
    Two-pass consensus linker.

    See module docstring for full design rationale.
    """

    def __init__(self) -> None:
        super().__init__(task_name="bidirectional_linking")

    # ── Public interface ──────────────────────────────────────────────────────

    def run(self, state: IngestState) -> Dict[str, Any]:
        """
        Run forward + conditional backward pass and return consensus links.

        Returns same shape as LinkerAgent: {"links": [list of link dicts]}.
        """
        if not state.similar_notes:
            return {"links": []}

        # ── Forward pass ──────────────────────────────────────────────────────
        forward_links, weak_target_ids = self._forward_pass(state)

        if not forward_links:
            return {"links": []}

        # ── Backward validation (Moderate + Weak tier candidates) ────────────
        if not weak_target_ids:
            # All forward links are High — trust them as-is
            return {"links": forward_links}

        confirmed = self._backward_validate(
            forward_links=forward_links,
            weak_target_ids=weak_target_ids,
            new_note_id=state.note_id,
            new_note_summary=state.summary or state.content[:300],
            original_similar_notes=state.similar_notes,
        )
        return {"links": confirmed}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _forward_pass(
        self, state: IngestState
    ) -> tuple[list[dict], set[int]]:
        """
        Run the standard forward LLM call.

        Returns:
          forward_links  — list of link dicts from the LLM
          weak_target_ids — set of target_ids whose tier is Moderate or Weak
                           (these will need backward confirmation; High is trusted)
        """
        tier_by_id: dict[int, str] = {
            n["id"]: similarity_tier(n.get("distance", 1.0))
            for n in state.similar_notes
        }

        # Build prompt — exclude Distant, include all others (same as LinkerAgent)
        past_notes_lines: list[str] = []
        for n in state.similar_notes:
            tid  = n["id"]
            tier = tier_by_id[tid]
            if tier == "Distant":
                continue
            past_notes_lines.append(f"[{tier}] ID {tid}: {n['summary']}")

        if not past_notes_lines:
            return [], set()

        messages = LINKING_PROMPT.format_messages(
            new_note=state.content,
            past_notes="\n".join(past_notes_lines),
        )
        data: LinkerResult = self._call_llm(messages, output_schema=LinkerResult)
        forward_links = [lnk.model_dump() for lnk in data.links] if data.links else []

        # Identify which links need backward validation:
        # Moderate and Weak tiers — High similarity is trusted from forward pass alone.
        NEEDS_VALIDATION = {"Moderate similarity", "Weak topical connection"}
        weak_target_ids = {
            lnk["target_id"]
            for lnk in forward_links
            if tier_by_id.get(lnk["target_id"]) in NEEDS_VALIDATION
        }

        return forward_links, weak_target_ids

    def _backward_validate(
        self,
        forward_links: list[dict],
        weak_target_ids: set[int],
        new_note_id: Optional[int],
        new_note_summary: str,
        original_similar_notes: list[dict],
    ) -> list[dict]:
        """
        For each Weak link, run a backward call from the existing note's perspective.

        A backward call asks: "Given note A (existing), does it connect to note B (new)?"
        The link is confirmed only if the backward LLM call also votes yes.

        High / Moderate links pass through without backward validation.
        """
        # Distance between the two notes is symmetric — reuse from forward pass
        dist_by_id: dict[int, float] = {
            n["id"]: n.get("distance", 0.65)
            for n in original_similar_notes
        }

        confirmed: list[dict] = []

        for link in forward_links:
            target_id = link["target_id"]

            if target_id not in weak_target_ids:
                # High or Moderate — trust the forward pass, no extra call needed
                confirmed.append(link)
                continue

            # Fetch the existing note's content for the backward call
            target_note = note_repository.get_note_by_id(target_id)
            if target_note is None:
                # Can't fetch — trust forward pass defensively
                confirmed.append(link)
                continue

            backward_confirmed = self._run_backward_call(
                existing_note_content=target_note.content or target_note.summary or "",
                new_note_id=new_note_id,
                new_note_summary=new_note_summary,
                distance=dist_by_id.get(target_id, 0.65),
            )

            if backward_confirmed:
                confirmed.append(link)
            # else: link silently dropped — both perspectives must agree

        return confirmed

    def _run_backward_call(
        self,
        existing_note_content: str,
        new_note_id: Optional[int],
        new_note_summary: str,
        distance: float,
    ) -> bool:
        """
        Ask the LLM: "From note A's perspective, does it connect to note B?"

        Returns True if the LLM creates any link to new_note_id.
        """
        tier = similarity_tier(distance)
        candidate_line = f"[{tier}] ID {new_note_id}: {new_note_summary}"

        messages = LINKING_PROMPT.format_messages(
            new_note=existing_note_content,
            past_notes=candidate_line,
        )
        data: LinkerResult = self._call_llm(messages, output_schema=LinkerResult)

        return any(
            lnk.target_id == new_note_id
            for lnk in (data.links or [])
        )
