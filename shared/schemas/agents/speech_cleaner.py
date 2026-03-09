from pydantic import BaseModel, Field


class SpeechCleanerOutput(BaseModel):
    """Structured output from the speech cleaner agent."""

    cleaned_text: str = Field(
        ...,
        description="The transcription with filler words, stutters, and false starts removed.",
    )
