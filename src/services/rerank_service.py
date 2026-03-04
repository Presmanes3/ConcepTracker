"""Cohere Rerank 3.5 via AWS Bedrock using the langchain_aws BedrockRerank compressor."""
import os
from typing import Any, Dict, List, Optional

from langchain_aws import BedrockRerank
from langchain_core.documents import Document


def _model_id_to_arn(model_id: str, region: str) -> str:
    """Convert a short Bedrock model ID to a foundation-model ARN.

    Args:
        model_id: Short model ID, e.g. ``"cohere.rerank-v3-5:0"``.
        region: AWS region, e.g. ``"eu-west-1"``.

    Returns:
        Full ARN understood by the Bedrock Rerank API.
    """
    return f"arn:aws:bedrock:{region}::foundation-model/{model_id}"


class RerankService:
    """Calls Cohere Rerank 3.5 on Bedrock via ``BedrockRerank`` from langchain_aws."""

    _instance = None

    def __new__(cls) -> "RerankService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 10,
        text_key: str = "content",
        model_id: str = "cohere.rerank-v3-5:0",
    ) -> List[Dict[str, Any]]:
        """Rerank *candidates* against *query* using Cohere Rerank 3.5.

        Args:
            query: The user search query.
            candidates: Result dicts to rerank; each must contain *text_key*.
            top_n: Number of results to return.
            text_key: Dict key whose value is the passage text for reranking.
            model_id: Short Bedrock model ID; converted to ARN internally.

        Returns:
            Top-N candidates sorted by Cohere relevance score (descending),
            with ``rerank_score`` injected.
        """
        if not candidates:
            return []

        region = os.getenv("AWS_REGION", "eu-west-1")
        model_arn = _model_id_to_arn(model_id, region)

        reranker = BedrockRerank(
            model_arn=model_arn,
            top_n=min(top_n, len(candidates)),
            region_name=region,
        )

        # BedrockRerank.rerank() accepts plain strings or Document objects.
        texts = [c.get(text_key, "") or "" for c in candidates]
        results = reranker.rerank(texts, query=query)

        # results is a list of {"index": int, "relevance_score": float}
        return [
            {**candidates[r["index"]], "rerank_score": r["relevance_score"]}
            for r in results
        ]


rerank_service = RerankService()

