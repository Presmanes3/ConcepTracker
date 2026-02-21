from typing import Dict, Any
from shared.schemas.workflow.ingest import IngestState
from shared.schemas.agents.linker import LinkerResult
from shared.prompts.linking_agent import LINKING_PROMPT
from src.agents.base_agent import BaseAgent
from src.utils.embeddings import similarity_tier


class LinkerAgent(BaseAgent[IngestState, LinkerResult]):
    """
    Finds semantic relations between the new note and existing notes.

    Candidates are formatted with similarity tier labels (High / Moderate /
    Weak topical connection) to give the LLM calibrated in-context signal.
    No retry logic — tier labelling makes the first call reliable enough.
    """

    def __init__(self):
        super().__init__(task_name="linking")

    def run(self, state: IngestState) -> Dict[str, Any]:
        if not state.similar_notes:
            return {"links": []}

        taxonomy = state.taxonomy
        is_component_of = taxonomy.is_component_of if taxonomy else None

        # Build tier-labelled candidate lines.
        # If taxonomy flags a parent concept (is_component_of), mark it explicitly
        # in the prompt so the LLM treats it as a High-priority link regardless of tier.
        past_notes_lines = []
        new_family = taxonomy.domain_family if taxonomy else None
        for n in state.similar_notes:
            is_recent = n.get("is_recent", False)
            dist = n.get("distance", 1.0)
            tier = "Temporal Context" if is_recent else similarity_tier(dist)
            
            if tier == "Distant" and not is_recent:
                continue
                
            summary = n.get("summary", "")
            cand_family = n.get("domain_family") or None

            # ── Python-level domain guard (hard filter, pre-LLM) ────────────
            # If we know both families and they differ, only pass the candidate
            # through if it is High similarity, marked as a PARENT CONCEPT, or is RECENT.
            # Weak/Moderate cross-family candidates are excluded entirely —
            # never shown to the LLM, so the model cannot override this rule.
            is_parent = bool(is_component_of and is_component_of.lower() in summary.lower())
            if (
                new_family
                and cand_family
                and new_family != cand_family
                and not is_parent
                and not is_recent
                and tier != "High similarity"
            ):
                continue  # hard drop — cross-family non-parent below High tier

            if is_parent:
                label = f"PARENT CONCEPT | family:{cand_family}"
            elif is_recent:
                label = f"RECENT NOTE | family:{cand_family or 'unknown'}"
            else:
                label = f"{tier} | family:{cand_family or 'unknown'}"
                
            past_notes_lines.append(f"[{label}] ID {n['id']}: {summary}")

        if not past_notes_lines:
            return {"links": []}

        parent_hint = (
            f"Note: this note's taxonomy flags it as a sub-concept of '{is_component_of}'. "
            f"If '{is_component_of}' appears in the candidates above, you MUST link to it."
            if is_component_of else ""
        )

        messages = LINKING_PROMPT.format_messages(
            new_note=state.content,
            past_notes="\n".join(past_notes_lines),
            domain=taxonomy.domain if taxonomy else "unknown",
            domain_family=taxonomy.domain_family if taxonomy else "other",
            concept_type=taxonomy.concept_type if taxonomy else "unknown",
            parent_hint=parent_hint,
        )

        data: LinkerResult = self._call_llm(messages, output_schema=LinkerResult)
        links_data = [lnk.model_dump() for lnk in data.links] if data.links else []
        return {"links": links_data}

