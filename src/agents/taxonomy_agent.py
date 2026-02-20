"""
src/agents/taxonomy_agent.py
──────────────────────────────
ConceptTaxonomyAgent: pre-processing node that extracts a semantic fingerprint
from a note before any vector retrieval happens.

Output (ConceptTaxonomy) is stored in IngestState.taxonomy and used as
hard signals by the Gatekeeper and Linker:
  • Different domains → Gatekeeper always CREATEs, Linker adds domain guard
  • is_component_of set → Gatekeeper always CREATEs (sub-concept stays separate)
"""
from typing import Dict, Any
from shared.schemas.workflow.ingest import IngestState
from shared.schemas.agents.taxonomy import ConceptTaxonomy
from shared.prompts.taxonomy_agent import TAXONOMY_PROMPT
from src.agents.base_agent import BaseAgent


class ConceptTaxonomyAgent(BaseAgent[IngestState, ConceptTaxonomy]):
    """
    Classifies a note into a semantic taxonomy before retrieval.

    One fast structured-output LLM call on Nova Micro (~50ms, negligible cost).
    Falls back gracefully: if the call fails, taxonomy is None and downstream
    agents operate without the taxonomy guard (same behaviour as before).
    """

    def __init__(self):
        super().__init__(task_name="taxonomy_classification")

    def run(self, state: IngestState) -> Dict[str, Any]:
        try:
            messages = TAXONOMY_PROMPT.format_messages(content=state.content)
            result: ConceptTaxonomy = self._call_llm(
                messages, output_schema=ConceptTaxonomy
            )
            return {"taxonomy": result}
        except Exception:
            # Non-fatal: downstream agents check for None taxonomy
            return {"taxonomy": None}
