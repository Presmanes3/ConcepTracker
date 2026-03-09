from pydantic import BaseModel, Field


class MarkdownFormatterOutput(BaseModel):
    """Structured output from the Markdown formatter agent."""

    formatted_text: str = Field(
        ...,
        description="The input text reformatted as clean, readable Markdown.",
    )
