from abc import ABC, abstractmethod
from typing import Type, TypeVar, Generic, Any, Dict, Optional
import os
from pydantic import BaseModel
from langchain_aws import ChatBedrock
from langchain_core.runnables import Runnable
from src.services.cost_service import cost_service
from src.repository.config_repository import config_repository

# Generic types for Input (State) and Output (LLM Schema)
TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)

class BaseAgent(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for all agents.
    Centralizes LLM setup, cost tracking, and error handling.
    """
    def __init__(
        self,
        model_id: Optional[str] = None,
        temperature: float = 0.1,
        task_name: str = "agent_task"
    ):
        # Default to the active model in SSoT config if not specified
        self.model_id = model_id or config_repository.get_active_model_id()
        self.task_name = task_name
        
        # Initialize LLM
        self.llm = ChatBedrock(
            model_id=self.model_id,
            region_name=os.getenv("AWS_REGION", "eu-west-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            model_kwargs={"temperature": temperature}
        )

    @abstractmethod
    def run(self, input_data: TInput) -> Dict[str, Any]:
        """Execute the agent's logic."""
        pass

    def _call_llm(self, prompt_messages: list, output_schema: Optional[Type[TOutput]] = None) -> Any:
        """
        Calls the LLM with cost tracking. Handle both raw messages and structured output.
        - If output_schema is provided: returns the parsed Pydantic object.
        - Otherwise: returns the AIMessage.
        """
        if output_schema:
            # We use include_raw=True to capture token usage which is lost in the parsed object
            chain = self.llm.with_structured_output(output_schema, include_raw=True)
            response_bundle = chain.invoke(prompt_messages)

            raw_message = response_bundle["raw"]

            # If there's a parsing error, we have a mismatch between LLM output and the schema
            if response_bundle.get("parsing_error"):
                raise ValueError(
                    f"LLM Structured Output mismatch for {self.__class__.__name__}: {response_bundle['parsing_error']}"
                )

            parsed_output = response_bundle["parsed"]

            # Nova Micro double-tool-call hardening:
            # Nova Micro sometimes emits multiple tool_use blocks in one response —
            # an empty "thinking" block first, then the real answer.
            # with_structured_output picks the FIRST block (may be empty/wrong).
            # Fix: always use the LAST block, and also re-parse single blocks that
            # have empty list fields when the raw input contains non-empty lists.
            raw_content = getattr(raw_message, "content", None)
            if isinstance(raw_content, list):
                tool_blocks = [
                    b for b in raw_content
                    if isinstance(b, dict)
                    and b.get("type") == "tool_use"
                    and b.get("name") == output_schema.__name__
                ]
                if tool_blocks:
                    best_input = tool_blocks[-1].get("input", {})

                    def _has_empty_lists(raw_in: dict, current: Any) -> bool:
                        """True when raw_in has lists where current has empty lists."""
                        for field, val in raw_in.items():
                            if isinstance(val, list) and len(val) > 0:
                                cur = getattr(current, field, None)
                                if isinstance(cur, list) and len(cur) == 0:
                                    return True
                        return False

                    if len(tool_blocks) > 1 or _has_empty_lists(best_input, parsed_output):
                        try:
                            parsed_output = output_schema(**best_input)
                        except Exception:
                            pass  # keep original parse on failure
            # ──────────────────────────────────────────────────────────────────────

            # Log usage from the raw AIMessage
            usage = getattr(raw_message, "usage_metadata", {}) or {}
            cost_service.log_inference(
                model_id=self.model_id,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                task=self.task_name
            )
            return parsed_output
        else:
            # Native AIMessage return
            response = self.llm.invoke(prompt_messages)
            usage = getattr(response, "usage_metadata", {})
            cost_service.log_inference(
                model_id=self.model_id,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                task=self.task_name
            )
            return response
