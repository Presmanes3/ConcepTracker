from typing import Any, Dict

from shared.prompts.speech_cleaner import SPEECH_CLEANER_PROMPT
from shared.schemas.agents.speech_cleaner import SpeechCleanerOutput
from shared.schemas.workflow.ingest import IngestState
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry


@agent_registry.register("speech_cleaner")
class SpeechCleanerAgent(BaseAgent[IngestState, SpeechCleanerOutput]):
    """Remove filler words, stutters, and false starts from raw transcriptions."""

    def __init__(self) -> None:
        super().__init__(task_name="speech_cleaner", temperature=0.1)

    def run(self, state: IngestState) -> Dict[str, Any]:
        """Clean *state.content* and return the deduplicated text.

        Args:
            state: Ingest state; only ``content`` is consumed.

        Returns:
            Dict with updated ``content`` key.
        """
        if not state.content.strip():
            return {}

        messages = SPEECH_CLEANER_PROMPT.format_messages(text=state.content)
        data: SpeechCleanerOutput = self._call_llm(messages, output_schema=SpeechCleanerOutput)
        return {"content": data.cleaned_text}
