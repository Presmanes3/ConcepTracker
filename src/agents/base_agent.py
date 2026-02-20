from abc import ABC, abstractmethod
from typing import Type, TypeVar, Generic, Any, Dict
from pydantic import BaseModel
from langchain_aws import ChatBedrock
from langchain_core.runnables import Runnable

# Generic types for Input (State) and Output (LLM Schema)
TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)

class BaseAgent(ABC, Generic[TInput, TOutput]):
    """
    Abstract base class for all agents in the ConcepTracker pipeline.
    Ensures consistent initialization of LLMs and structured error handling.
    """
    def __init__(
        self,
        input_data: TInput,
        output_schema: Type[TOutput],
        model: str = "amazon.nova-lite-v1:0",
        region: str = "us-east-1",
        temperature: float = 0,
    ):
        self.input_data = input_data
        self.output_schema = output_schema
        
        # Standardized ChatBedrock initialization with Structured Output
        self.llm: Runnable = ChatBedrock(
            model=model,
            region=region,
            temperature=temperature,
        ).with_structured_output(output_schema)

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        Main entry point for the agent's logic.
        Must return a dictionary matching the fields in WorkflowState.
        """
        pass

    def _safe_run(self, logic_func) -> Dict[str, Any]:
        """
        A standardized execution wrapper that captures errors and matches
        the pipeline_errors field in the global WorkflowState.
        """
        try:
            return logic_func()
        except Exception as e:
            return {
                "pipeline_errors": [f"Error in {self.__class__.__name__}: {str(e)}"]
            }
