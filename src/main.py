from langgraph.graph import StateGraph, START, END
from shared.schemas.workflow import WorkflowState
from shared.schemas.normalizer_agent import NormalizerAgentInput
from shared.schemas.chunk_embed_agent import ChunkEmbedAgentInput
from src.agents.normalizer_agent import NormalizerAgent
from src.agents.chunk_embed_agent import ChunkEmbedAgent

from pprint import pprint

# Node 1: Normalizer
def run_normalizer(state: WorkflowState):
    """Bridge for the NormalizerAgent: Global State -> Agent Data -> Update."""
    # Only pass fields that the NormalizerAgentInput expects
    allowed_keys = NormalizerAgentInput.model_fields.keys()
    agent_data = {k: v for k, v in state.model_dump().items() if k in allowed_keys}
    
    agent_input = NormalizerAgentInput(**agent_data)
    agent = NormalizerAgent(input_data=agent_input)
    result = agent.run()
    return result

# Node 2: Chunk & Embed
def run_chunker(state: WorkflowState):
    """Bridge for the ChunkEmbedAgent: Global State -> Agent Data -> Update."""
    # Check if normalization succeeded
    if not state.is_normalized or not state.clean_message:
        return {"pipeline_errors": state.pipeline_errors + ["Skipping ChunkEmbedAgent: No clean content available."]}

    # Only pass fields that the ChunkEmbedAgentInput expects
    allowed_keys = ChunkEmbedAgentInput.model_fields.keys()
    agent_data = {k: v for k, v in state.model_dump().items() if k in allowed_keys}
    
    agent_input = ChunkEmbedAgentInput(**agent_data)
    agent = ChunkEmbedAgent(input_data=agent_input)
    result = agent.run()
    return result

# Graph Setup with SSoT WorkflowState
workflow = StateGraph(WorkflowState)

workflow.add_node("normalizer", run_normalizer)
workflow.add_node("chunker", run_chunker)

workflow.add_edge(START, "normalizer")
workflow.add_edge("normalizer", "chunker")
workflow.add_edge("chunker", END)

app = workflow.compile()

# Invoke with standardized input based on WorkflowState ingestion fields
if __name__ == "__main__":
    print("Starting ConcepTracker Pipeline...")
    user_input = {
        "raw_message": "  Hola, esto es un mensaje de prueba sobre IA...  ",
        "raw_title": "Prueba de LangGraph",
        "source_url": "https://ejemplo.com",
        "raw_tags": ["ia", "langgraph"],
        "confidence_level": 0.95,
        "source_type": "manual"
    }
    
    print("Invoking graph...")
    final_state = app.invoke(user_input)
    print("Graph invocation completed.")
    
    # Check output (LangGraph 0.2 `app.invoke` returns a dictionary or the State object)
    # Since we used StateGraph(WorkflowState), final_state should be a WorkflowState if it converged
    is_normalized = getattr(final_state, 'is_normalized', final_state.get('is_normalized') if isinstance(final_state, dict) else False)
    is_indexed = getattr(final_state, 'is_indexed', final_state.get('is_indexed') if isinstance(final_state, dict) else False)
    chunks = getattr(final_state, 'chunks', final_state.get('chunks', []) if isinstance(final_state, dict) else [])
    errors = getattr(final_state, 'pipeline_errors', final_state.get('pipeline_errors', []) if isinstance(final_state, dict) else [])

    pprint(final_state)
