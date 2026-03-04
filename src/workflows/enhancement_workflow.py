"""
Professional Enhancement Workflow — RAG-based note refactoring.
"""
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END

from shared.schemas.workflow.enhancement import EnhancementState
from shared.schemas.agents.enhancement import LLMEnhancementOutput
from src.registry import repos, service_registry
from src.agents.base_agent import BaseAgent
from src.services.search_service import search_service
from src.services.embedding_service import embedding_service

import logging

logger = logging.getLogger(__name__)

# ── Enhancement Agent ──────────────────────────────────────────────────────────

class EnhancementAgent(BaseAgent[EnhancementState, LLMEnhancementOutput]):
    """
    Refactors note content based on user instructions and existing context.
    """
    def __init__(self):
        super().__init__(task_name="enhancement")

    def run(self, state: EnhancementState) -> Dict[str, Any]:
        # Professional Utility: Get context from search service to find related concepts
        # This makes it "professional" by being context-aware
        related_notes: List[str] = []
        try:
            # Generate embedding for the current note content
            vector = embedding_service.get_embedding(state.current_content)
            # Search for related context using the vector
            search_results = search_service.vector_search(vector, limit=3, exclude_id=state.note_id)
            related_notes = [r["content"] for r in search_results]
        except Exception as e:
            logger.warning(f"Failed to fetch context for enhancement: {e}")

        context_str = "\n---\n".join(related_notes)
        
        # Build a professional prompt
        system_prompt = (
            "You are a professional knowledge management assistant. "
            "Your goal is to refactor the user's note based on their instruction. "
            "Use the provided context from related notes to ensure semantic consistency. "
            "Maintain valid Markdown formatting."
        )
        
        user_prompt = (
            f"Instruction: {state.user_instruction}\n\n"
            f"Current Note Content:\n{state.current_content}\n\n"
        )
        
        if context_str:
            user_prompt += f"Related Context for reference:\n{context_str}\n\n"
            
        user_prompt += "Produce the refactored Markdown content and suggested tags."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Call LLM with structured output
        data: LLMEnhancementOutput = self._call_llm(messages, output_schema=LLMEnhancementOutput)
        
        return {
            "enhanced_content": data.enhanced_content,
            "suggested_tags": data.suggested_tags,
            "is_complete": True
        }

# ── Workflow Definition ───────────────────────────────────────────────────────

_enhancer = EnhancementAgent()

def enhance_node(state: EnhancementState):
    """Node: Process the note with the enhancement agent."""
    logger.info(f"--- [enhancement_workflow] node: enhance_node for note {state.note_id} ---")
    result = _enhancer.run(state)
    return result

def create_enhancement_graph():
    """Create the workflow graph."""
    workflow = StateGraph(EnhancementState)
    
    workflow.add_node("enhance", enhance_node)
    
    workflow.add_edge(START, "enhance")
    workflow.add_edge("enhance", END)
    
    return workflow.compile()

enhancement_graph = create_enhancement_graph()
