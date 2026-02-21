from shared.schemas.workflow.transcription import TranscriptionEnhancementState
from src.agents.base_agent import BaseAgent
from shared.prompts.speech_cleaner import SPEECH_CLEANER_PROMPT

class SpeechCleanerAgent(BaseAgent):
    """
    Agent responsible for cleaning up raw transcriptions.
    Removes filler words, stutters, and false starts without changing the meaning.
    """
    
    def __init__(self):
        super().__init__(task_name="speech_cleaner", temperature=0.1)

    def run(self, state: TranscriptionEnhancementState) -> TranscriptionEnhancementState:
        # Not used directly in LangGraph node, but required by BaseAgent
        return self.process(state)

    def process(self, state: TranscriptionEnhancementState) -> TranscriptionEnhancementState:
        """Processes the current text in the state and returns the cleaned version."""
        text_to_clean = state["current_text"]
        
        if not text_to_clean.strip():
            return state
            
        try:
            messages = SPEECH_CLEANER_PROMPT.format_messages(text=text_to_clean)
            response = self._call_llm(messages)
            
            state["current_text"] = response.content.strip()
            state["applied_layers"].append("speech_cleaner")
            
        except Exception as e:
            state["error"] = f"SpeechCleanerAgent failed: {str(e)}"
            
        return state

speech_cleaner_agent = SpeechCleanerAgent()
