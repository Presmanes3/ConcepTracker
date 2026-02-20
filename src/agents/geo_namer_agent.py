from langchain_core.prompts import ChatPromptTemplate
from shared.schemas.agents.geo_namer import GeoNamerOutput
from src.agents.base_agent import BaseAgent

# GeoNamerAgent is always hardcoded to Nova Micro:
# fast, cheap, and well-suited for short structured naming tasks.
GEO_MODEL_ID = "eu.amazon.nova-micro-v1:0"


class GeoNamerAgent(BaseAgent[None, GeoNamerOutput]):
    """
    Minimal agent responsible only for naming geographic entities
    (Archipelagos or Continents) using Nova Micro.

    Usage:
        agent = GeoNamerAgent()
        result = agent.name(prompt_template, **format_kwargs)
    """

    def __init__(self):
        super().__init__(model_id=GEO_MODEL_ID, task_name="geo_naming")

    def run(self, input_data=None):
        raise NotImplementedError("Use GeoNamerAgent.name() instead.")

    def name(
        self,
        prompt_template: ChatPromptTemplate,
        **format_kwargs,
    ) -> GeoNamerOutput:
        """
        Format `prompt_template` with `format_kwargs`, call Nova Micro,
        and return a `GeoNamerOutput` with `name` and `summary`.
        """
        messages = prompt_template.format_messages(**format_kwargs)
        return self._call_llm(messages, output_schema=GeoNamerOutput)
