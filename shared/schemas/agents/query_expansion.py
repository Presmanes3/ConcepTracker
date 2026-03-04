from pydantic import BaseModel, Field
from typing import List


class QueryExpansionResult(BaseModel):
    """Alternative phrasings of a user query produced by the expansion agent."""

    queries: List[str] = Field(
        default_factory=list,
        description="Up to N reformulations of the original query.",
    )
