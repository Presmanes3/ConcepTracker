from shared.schemas.workflow import WorkflowState
from shared.schemas.normalizer_agent import NormalizerAgentInput
from shared.schemas.chunk_embed_agent import ChunkEmbedAgentInput
from src.agents.normalizer_agent import NormalizerAgent
from src.agents.chunk_embed_agent import ChunkEmbedAgent

user_input_dict = {
    "raw_message": "  Hola, esto es un mensaje de prueba sobre IA...  ",
    "raw_title": "Prueba de LangGraph",
    "source_url": "https://ejemplo.com",
    "raw_tags": ["ia", "langgraph"],
    "confidence_level": 0.95,
    "source_type": "manual"
}

state = WorkflowState(**user_input_dict)
print("State created.")

# Test Normalizer
print("Running Normalizer...")
norm_input = NormalizerAgentInput(**state.model_dump())
norm_agent = NormalizerAgent(input_data=norm_input)
norm_result = norm_agent.run()
print(f"Normalizer result: {norm_result}")

# Update state
state = state.model_copy(update=norm_result)

# Test Chunker
print("Running Chunker...")
if state.is_normalized and state.clean_message:
    chunk_input = ChunkEmbedAgentInput(**state.model_dump(exclude={"chunks"}))
    chunk_agent = ChunkEmbedAgent(input_data=chunk_input)
    chunk_result = chunk_agent.run()
    print(f"Chunker results count: {len(chunk_result.get('chunks', []))}")
else:
    print("Skipped chunker due to normalization failure.")
