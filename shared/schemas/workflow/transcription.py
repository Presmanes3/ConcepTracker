from typing import TypedDict, List, Optional

class TranscriptionEnhancementState(TypedDict):
    """
    State for the transcription enhancement workflow.
    """
    raw_text: str
    current_text: str
    applied_layers: List[str]
    action_items: Optional[List[str]]
    error: Optional[str]
