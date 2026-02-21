from shared.schemas.workflow.transcription import TranscriptionEnhancementState
from src.agents.base_agent import BaseAgent
from shared.prompts.markdown_formatter import MARKDOWN_FORMATTER_PROMPT

class MarkdownFormatterAgent(BaseAgent):
    """
    Agent responsible for structuring cleaned text into readable Markdown.
    """
    
    def __init__(self):
        super().__init__(task_name="markdown_formatter", temperature=0.2)

    def run(self, state: TranscriptionEnhancementState) -> TranscriptionEnhancementState:
        # Not used directly in LangGraph node, but required by BaseAgent
        return self.process(state)

    def process(self, state: TranscriptionEnhancementState) -> TranscriptionEnhancementState:
        """Processes the current text in the state and returns the formatted version."""
        text_to_format = state["current_text"]
        
        if not text_to_format.strip():
            return state
            
        try:
            messages = MARKDOWN_FORMATTER_PROMPT.format_messages(text=text_to_format)
            response = self._call_llm(messages)
            
            state["current_text"] = response.content.strip()
            state["applied_layers"].append("markdown_formatter")
            
        except Exception as e:
            state["error"] = f"MarkdownFormatterAgent failed: {str(e)}"
            
        return state

markdown_formatter_agent = MarkdownFormatterAgent()
