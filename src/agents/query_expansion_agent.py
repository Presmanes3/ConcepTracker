from typing import Any, Dict

from langchain_core.output_parsers import StrOutputParser

from shared.prompts.query_expansion import QUERY_EXPANSION_PROMPT
from shared.schemas.agents.query_expansion import QueryExpansionResult
from shared.schemas.workflow.search import SearchState
from src.agents.base_agent import BaseAgent


class QueryExpansionAgent(BaseAgent[SearchState, QueryExpansionResult]):
    """Generates alternative phrasings of the user query for multi-branch retrieval."""

    def __init__(self, expansion_count: int = 2) -> None:
        super().__init__(task_name="query_expansion")
        self.expansion_count = expansion_count

    def run(self, input_data: SearchState) -> Dict[str, Any]:
        """Expand *input_data.query* into N alternative queries.

        Args:
            input_data: Current search state; only ``query`` is consumed.

        Returns:
            Dict with ``expanded_queries`` list.
        """
        chain = QUERY_EXPANSION_PROMPT | self.llm | StrOutputParser()
        raw: str = chain.invoke(
            {"query": input_data.query, "expansion_count": self.expansion_count}
        )
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        # Keep at most expansion_count items to respect config.
        return {"expanded_queries": lines[: self.expansion_count]}
