from langgraph.graph import StateGraph, END
from shared.schemas.workflow.transcription import TranscriptionEnhancementState
from src.agents.speech_cleaner_agent import speech_cleaner_agent
from src.agents.markdown_formatter_agent import markdown_formatter_agent
from src.repository.config_repository import config_repository

def build_transcription_workflow():
    """
    Builds a dynamic LangGraph workflow based on settings.yaml.
    """
    workflow = StateGraph(TranscriptionEnhancementState)
    
    # Read pipeline config from settings
    settings = config_repository.get_settings()
    
    pipeline_config = []
    if hasattr(settings, "transcription") and settings.transcription and hasattr(settings.transcription, "enhancement_pipeline"):
        pipeline_config = settings.transcription.enhancement_pipeline
    
    # If no pipeline is configured, just return a pass-through graph
    if not pipeline_config:
        def no_op(state: TranscriptionEnhancementState):
            return state
        workflow.add_node("no_op", no_op)
        workflow.set_entry_point("no_op")
        workflow.add_edge("no_op", END)
        return workflow.compile()

    # Map config names to agent functions
    agent_map = {
        "speech_cleaner": speech_cleaner_agent.process,
        "markdown_formatter": markdown_formatter_agent.process
    }
    
    # Add nodes for configured agents
    active_nodes = []
    for step in pipeline_config:
        if step in agent_map:
            workflow.add_node(step, agent_map[step])
            active_nodes.append(step)
            
    if not active_nodes:
        def no_op(state: TranscriptionEnhancementState):
            return state
        workflow.add_node("no_op", no_op)
        workflow.set_entry_point("no_op")
        workflow.add_edge("no_op", END)
        return workflow.compile()

    # Set entry point
    workflow.set_entry_point(active_nodes[0])
    
    # Connect nodes sequentially
    for i in range(len(active_nodes) - 1):
        workflow.add_edge(active_nodes[i], active_nodes[i+1])
        
    # Connect last node to END
    workflow.add_edge(active_nodes[-1], END)
    
    return workflow.compile()

transcription_workflow = build_transcription_workflow()
