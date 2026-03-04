"""Transcription enhancement pipeline: cleans and structures raw speech using the normalizer."""
from langgraph.graph import END, START, StateGraph

from shared.schemas.workflow.ingest import IngestState
from shared.schemas.workflow.transcription import TranscriptionEnhancementState
from src.agents.normalizer_agent import NormalizerAgent

_normalizer = NormalizerAgent()


def _normalize_transcription(state: TranscriptionEnhancementState) -> TranscriptionEnhancementState:
    """Node: clean and format transcription text using the normalizer."""
    ingest_input = IngestState(content=state["current_text"], source_type="transcription")  # type: ignore[call-arg]
    result = _normalizer.run(ingest_input)  # type: ignore[arg-type]
    return {
        **state,
        "current_text": result.get("content", state["current_text"]),
        "applied_layers": [*state["applied_layers"], "normalizer"],
    }


_wf = StateGraph(TranscriptionEnhancementState)
_wf.add_node("normalize", _normalize_transcription)
_wf.add_edge(START, "normalize")
_wf.add_edge("normalize", END)

transcription_workflow = _wf.compile()
