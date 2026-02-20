import os
import threading
from typing import List, Optional
from langchain_aws import BedrockEmbeddings
from dotenv import load_dotenv
from src.services.cost_service import cost_service
from shared.config.embedding_config import EMBEDDING_MODEL_ID

load_dotenv()

class EmbeddingService:
    """
    Singleton service to generate embeddings using AWS Bedrock.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingService, cls).__new__(cls)
                cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        """Initialize the Bedrock client."""
        # Preference: env variables from .env or system
        ak = os.getenv("AWS_ACCESS_KEY_ID")
        sk = os.getenv("AWS_SECRET_ACCESS_KEY")
        region = os.getenv("AWS_REGION", "eu-west-1") # defaulting to user's region
        profile = os.getenv("AWS_PROFILE")

        self.model_id = EMBEDDING_MODEL_ID
        
        self.client = BedrockEmbeddings(
            model_id=self.model_id,
            region_name=region,
            credentials_profile_name=profile,
            aws_access_key_id=ak,
            aws_secret_access_key=sk
        )

    def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding for a piece of text."""
        try:
            # Estimate tokens: 1 word ~ 1.3 tokens for Titan
            token_est = int(len(text.split()) * 1.3) + 2
            cost_service.log_inference(self.model_id, token_est, 0, "embedding")
            return self.client.embed_query(text)
        except Exception as e:
            # Handle potential connection or model identifier issues
            raise RuntimeError(f"EmbeddingService error: {str(e)}")

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        try:
            return self.client.embed_documents(texts)
        except Exception as e:
            raise RuntimeError(f"EmbeddingService batch error: {str(e)}")

# Export a singleton instance
embedding_service = EmbeddingService()
