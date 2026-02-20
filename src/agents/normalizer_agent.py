from typing import List, Dict, Any
import re
from langchain_core.runnables import Runnable

from shared.schemas.normalizer_agent import NormalizerAgentInput, LLMNormalizerOutput
from shared.enums.source_type import SourceType
from shared.prompts.normalizer_agent import NORMALIZER_PROMPT
from src.agents.base_agent import BaseAgent

class NormalizerAgent(BaseAgent[NormalizerAgentInput, LLMNormalizerOutput]):
    """
    Agent responsible for cleaning, sanitizing, and enriching raw note content 
    using a hybrid approach of deterministic logic and LLM-driven structured output.
    """
    def __init__(self, input_data: NormalizerAgentInput):
        # Passes the agent's specific input and LLM output schema to the BaseAgent
        super().__init__(input_data, LLMNormalizerOutput)

    def run(self) -> Dict[str, Any]:
        """
        Executes the normalization pipeline: Pre-cleaning -> LLM Enrichment -> Mapping.
        Returns a dictionary for updating the WorkflowState.
        """
        def logic():
            # Step 1: Deterministic pre-processing (HTML stripping, PDF fix, etc.)
            pre_cleaned = self._pre_clean_message(self.input_data.raw_message)

            # Step 2: Single LLM call with Nova Pro (Structured Output)
            llm_output: LLMNormalizerOutput = self._call_llm(pre_cleaned)

            # Step 3: Build the update dict (merging LLM fields with pipeline flags)
            update = llm_output.model_dump()
            update.update({
                "is_normalized": True,
                "pipeline_errors": [],
            })
            return update

        return self._safe_run(logic)

    def _pre_clean_message(self, raw: str) -> str:
        """Applies basic string cleaning before sending content to the LLM."""
        cleaned = raw.strip()

        if self.input_data.source_type == SourceType.WEB_CLIP:
            cleaned = re.sub(r"<[^>]+>", "", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned)

        elif self.input_data.source_type == SourceType.PDF:
            cleaned = re.sub(r"(\w)-\n(\w)", r"\1\2", cleaned)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned

    def _call_llm(self, pre_cleaned_message: str) -> LLMNormalizerOutput:
        """Invokes the Bedrock Nova Pro model using the normalization prompt."""
        chain = NORMALIZER_PROMPT | self.llm

        return chain.invoke({
            "source_type": self.input_data.source_type.value,
            "source_url": str(self.input_data.source_url) if self.input_data.source_url else "N/A",
            "raw_title": self.input_data.raw_title or "Not provided",
            "raw_tags": ", ".join(self.input_data.raw_tags) if self.input_data.raw_tags else "None",
            "confidence_type": self.input_data.confidence_type.value,
            "confidence_level": self.input_data.confidence_level,
            "raw_message": pre_cleaned_message,
        })
