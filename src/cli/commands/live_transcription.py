"""
live_transcription.py -- thin command wrapper.
� thin command wrapper (~25 lines).

All business logic has been moved to:
  src/cli/interactors/transcription_interactor.py   (FSM / UX)
  src/cli/interactors/_transcription_async.py        (async audio pipeline)
  src/cli/views/transcription_views.py               (LiveTranscriptionView)
"""
from src.cli.registry import registry
from src.cli.interactors.transcription_interactor import TranscriptionInteractor


@registry.register(
    name="live_transcription",
    description="Start a real-time transcription session using AWS Transcribe.",
    example="ct live_transcription",
)
def live_transcription():
    """Start a real-time transcription session using AWS Transcribe."""
    TranscriptionInteractor().run()
