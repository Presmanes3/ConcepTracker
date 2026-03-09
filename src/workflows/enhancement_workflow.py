"""Professional Enhancement Workflow — RAG-based note refactoring."""
import logging

from langgraph.graph import END, START, StateGraph

from shared.schemas.workflow.enhancement import EnhancementState
from src.agents.enhancement_agent import EnhancementAgent

logger = logging.getLogger(__name__)

# ── Module-level agent singleton ──────────────────────────────────────────────

_enhancer = EnhancementAgent()


# ── Node ──────────────────────────────────────────────────────────────────────

def enhance_node(state: EnhancementState) -> dict:
    """Process the note with the enhancement agent."""
    logger.info("--- [enhancement_workflow] node: enhance_node for note %s ---", state.note_id)
    return _enhancer.run(state)


# ── Graph assembly ────────────────────────────────────────────────────────────

_graph = StateGraph(EnhancementState)
_graph.add_node("enhance", enhance_node)
_graph.add_edge(START, "enhance")
_graph.add_edge("enhance", END)

enhancement_graph = _graph.compile()
