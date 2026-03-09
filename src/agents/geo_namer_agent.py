from langchain_core.prompts import ChatPromptTemplate

from shared.schemas.agents.geo_namer import GeoNamerOutput
from src.agents.base_agent import BaseAgent
from src.registry import agent_registry


@agent_registry.register("geo_namer")
class GeoNamerAgent(BaseAgent[None, GeoNamerOutput]):
    """Minimal agent for naming geographic entities (Archipelagos or Continents).

    Invoke via ``name()``, not the standard ``run()`` interface — this agent
    does not participate in a LangGraph pipeline directly.
    """

    def __init__(self) -> None:
        super().__init__(task_name="geo_naming")

    def run(self, input_data=None):
        raise NotImplementedError("GeoNamerAgent is invoked via name(), not run().")

    def name(
        self,
        prompt_template: ChatPromptTemplate,
        **format_kwargs,
    ) -> GeoNamerOutput:
        """Format *prompt_template* with *format_kwargs*, call the LLM, and return the result.

        Args:
            prompt_template: A ``ChatPromptTemplate`` to format with *format_kwargs*.
            **format_kwargs: Variables forwarded to ``prompt_template.format_messages()``.

        Returns:
            ``GeoNamerOutput`` with ``name`` and ``summary`` fields.
        """
        messages = prompt_template.format_messages(**format_kwargs)
        return self._call_llm(messages, output_schema=GeoNamerOutput)
