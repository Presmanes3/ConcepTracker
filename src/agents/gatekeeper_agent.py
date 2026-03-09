from typing import Dict, Any

from shared.schemas.workflow.ingest import IngestState
from shared.schemas.agents.gatekeeper import GatekeeperResult
from shared.prompts.gatekeeper import GATEKEEPER_PROMPT
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry


@agent_registry.register("gatekeeper")
class GatekeeperAgent(BaseAgent[IngestState, GatekeeperResult]):
    """
    Decides if a note is new, a duplicate, or should be merged with an existing one.
    """
    def __init__(self):
        super().__init__(task_name="gatekeeping")

    def run(self, state: IngestState) -> Dict[str, Any]:
        if not state.similar_notes:
            return {"action": "CREATE", "summary": state.summary}
        
        similar_text = "\n".join([
            f"ID {n['id']} (Distance: {n.get('distance', 'N/A')}): {n['summary']} (Content: {n['content']})"
            for n in state.similar_notes
        ])

        taxonomy_text = (
            f"domain={state.taxonomy.domain}, concept_type={state.taxonomy.concept_type}, "
            f"concept_name='{state.taxonomy.concept_name}'"
            + (f", is_component_of='{state.taxonomy.is_component_of}'" if state.taxonomy and state.taxonomy.is_component_of else "")
            if state.taxonomy else "not available"
        )

        messages = GATEKEEPER_PROMPT.format_messages(
            content=state.content,
            concept_taxonomy=taxonomy_text,
            similar_notes=similar_text
        )
        
        # Calling LLM with structured output for strong typing
        result: GatekeeperResult = self._call_llm(messages, output_schema=GatekeeperResult)
        
        return {
            "action": result.action,
            "note_id": result.note_id,
            "reasoning": result.reasoning,
            "summary": result.updated_summary or state.summary
        }
