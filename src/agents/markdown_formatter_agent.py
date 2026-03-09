from typing import Any, Dict

from shared.prompts.markdown_formatter import MARKDOWN_FORMATTER_PROMPT
from shared.schemas.agents.markdown_formatter import MarkdownFormatterOutput
from shared.schemas.workflow.ingest import IngestState
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry


@agent_registry.register("markdown_formatter")
class MarkdownFormatterAgent(BaseAgent[IngestState, MarkdownFormatterOutput]):
    """Structure cleaned text into readable Markdown."""

    def __init__(self) -> None:
        super().__init__(task_name="markdown_formatter", temperature=0.2)

    def run(self, state: IngestState) -> Dict[str, Any]:
        """Format *state.content* as Markdown and return the updated content.

        Args:
            state: Ingest state; only ``content`` is consumed.

        Returns:
            Dict with updated ``content`` key.
        """
        if not state.content.strip():
            return {}

        messages = MARKDOWN_FORMATTER_PROMPT.format_messages(text=state.content)
        data: MarkdownFormatterOutput = self._call_llm(messages, output_schema=MarkdownFormatterOutput)
        return {"content": data.formatted_text}
