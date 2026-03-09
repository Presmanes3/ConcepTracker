from typing import Dict, Any

from shared.schemas.workflow.ingest import IngestState
from shared.schemas.agents.normalizer import LLMNormalizerOutput
from shared.prompts.normalizer_agent import NORMALIZER_PROMPT
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry


@agent_registry.register("normalizer")
class NormalizerAgent(BaseAgent[IngestState, LLMNormalizerOutput]):
    """
    Cleans raw content and generates a summary using structured output.
    """
    def __init__(self):
        super().__init__(task_name="normalization")

    def run(self, state: IngestState) -> Dict[str, Any]:
        # Prep tags for prompt: join list if it's already a list, or use as is
        raw_tags = state.tags if state.tags else "None"
        
        # Build prompt
        messages = NORMALIZER_PROMPT.format_messages(
            source_type=state.source_type or "manual",
            source_url=str(state.source_url) if state.source_url else "N/A",
            raw_title="Not provided",
            raw_tags=raw_tags,
            raw_message=state.content
        )
        
        # Call LLM with structured output for strong typing
        data: LLMNormalizerOutput = self._call_llm(messages, output_schema=LLMNormalizerOutput)
        
        # Format tags for SQL (comma separated)
        tag_string = ", ".join(data.normalized_tags) if data.normalized_tags else ""
        
        return {
            "content": data.clean_message or state.content,  # Fallback to original if LLM omits it
            "summary": data.summary,
            "tags": tag_string,
            "language": data.detected_language,
            "original_content": state.content  # Preserve for traceability
        }

