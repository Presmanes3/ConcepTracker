from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from shared.prompts.tag_recommender import TAG_RECOMMENDER_SYSTEM_PROMPT, TAG_RECOMMENDER_USER_PROMPT
from shared.schemas.agents.tag_recommender import TagRecommendations

class TagRecommenderAgent(BaseAgent):
    """
    Agent responsible for recommending professional tags for a note.
    """
    def __init__(self):
        super().__init__(
            task_name="TagRecommender"
        )

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the tag recommendation process.
        
        Expected state:
        - content: str
        - summary: str
        
        Returns:
        - tags: List[str]
        """
        content = state.get("content", "")
        summary = state.get("summary", "")

        messages = [
            {"role": "system", "content": TAG_RECOMMENDER_SYSTEM_PROMPT},
            {"role": "user", "content": TAG_RECOMMENDER_USER_PROMPT.format(
                summary=summary,
                content=content
            )}
        ]

        try:
            result = self._call_llm(messages, output_schema=TagRecommendations)
            return {"tags": result.tags}
        except Exception as e:
            self.logger.error(f"Tag recommendation failed: {e}")
            return {"tags": []}
