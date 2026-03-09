"""Enhancement agent — RAG-aware note refactoring."""
import logging
from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent
from src.registry import agent_registry
from src.services.embedding_service import embedding_service
from src.services.search_service import search_service
from shared.prompts.enhancement import ENHANCEMENT_PROMPT
from shared.schemas.agents.enhancement import LLMEnhancementOutput
from shared.schemas.workflow.enhancement import EnhancementState

logger = logging.getLogger(__name__)


@agent_registry.register("enhancement")
class EnhancementAgent(BaseAgent[EnhancementState, LLMEnhancementOutput]):
    """Refactors note content based on user instructions and existing context."""

    def __init__(self) -> None:
        super().__init__(task_name="enhancement")

    def run(self, state: EnhancementState) -> Dict[str, Any]:
        """Enhance a note using RAG context and structured LLM output.

        Args:
            state: Current enhancement state with note ID, content, and instruction.

        Returns:
            Dict with ``enhanced_content``, ``suggested_tags``, and ``is_complete``.
        """
        related_notes: List[str] = []
        try:
            vector = embedding_service.get_embedding(state.current_content)
            results = search_service.vector_search(vector, limit=3, exclude_id=state.note_id)
            related_notes = [r["content"] for r in results]
        except Exception as exc:
            logger.warning("Failed to fetch RAG context for enhancement: %s", exc)

        context_block = ""
        if related_notes:
            context_block = (
                "Related Context for reference:\n"
                + "\n---\n".join(related_notes)
                + "\n\n"
            )

        messages = ENHANCEMENT_PROMPT.format_messages(
            user_instruction=state.user_instruction,
            current_content=state.current_content,
            context_block=context_block,
        )

        data: LLMEnhancementOutput = self._call_llm(messages, output_schema=LLMEnhancementOutput)

        return {
            "enhanced_content": data.enhanced_content,
            "suggested_tags": data.suggested_tags,
            "is_complete": True,
        }
