from typing import Any, Dict

from shared.prompts.query_expansion import QUERY_EXPANSION_PROMPT
from shared.schemas.agents.query_expansion import QueryExpansionResult
from shared.schemas.workflow.search import SearchState
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry
from src.repository.config_repository import config_repository


@agent_registry.register("query_expansion")
class QueryExpansionAgent(BaseAgent[SearchState, QueryExpansionResult]):
    """Generate alternative phrasings of the user query for multi-branch retrieval."""

    def __init__(self) -> None:
        super().__init__(task_name="query_expansion")

    def run(self, input_data: SearchState) -> Dict[str, Any]:
        """Expand *input_data.query* into N alternative queries.

        Args:
            input_data: Current search state; only ``query`` is consumed.

        Returns:
            Dict with ``expanded_queries`` list.
        """
        settings = config_repository.get_settings()
        expansion_count: int = settings.search.expansion_count

        messages = QUERY_EXPANSION_PROMPT.format_messages(
            query=input_data.query,
            expansion_count=expansion_count,
        )
        result: QueryExpansionResult = self._call_llm(messages, output_schema=QueryExpansionResult)
        return {"expanded_queries": result.queries[:expansion_count]}
