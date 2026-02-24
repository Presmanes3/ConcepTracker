"""
PauseTranscriptionInteractor — orchestrates the pause overlay UX.

Per CLI_ARCHITECTURE.MD: the Interactor owns use-case logic; the Screen only
owns pure UI state and emitting signals.

Responsibilities:
  - Build and provide a ready-to-push PauseTranscriptionScreen.
  - Process the screen's dismiss result:
      "resume"  → pass through (continue recording).
      "save"    → pass through (caller exits transcription loop and saves).
      "discard" → pass through (caller discards).
      "enhance" → suspend the Textual app, run the AI workflow (with Rich
                  panels + questionary confirm), resume the app, then return
                  ("save", enhanced_text | original_text).
  - Expose `applied_enhancements` so the transcription layer can persist it.

Usage (from RecordingScreen._pause):
    interactor = PauseTranscriptionInteractor(
        full_transcript=list(self.full_transcript),
        elapsed_seconds=self.elapsed_seconds,
    )
    screen = interactor.build_screen()
    self.app.push_screen(screen, callback=lambda r: self._on_pause_done(interactor, r))

Usage (from RecordingScreen._on_pause_done):
    action, edited_text = interactor.process_result(self.app, raw_result)
"""
from __future__ import annotations

import json
import time
from typing import List, Optional, Tuple

from rich.console import Console

_console = Console()


class PauseTranscriptionInteractor:
    """
    Orchestrates all use-case logic for a pause session:
      - Building the UI screen with the correct data.
      - Processing the result (including AI enhancement).
    """

    def __init__(
        self,
        full_transcript: List[str],
        elapsed_seconds: float,
    ) -> None:
        self._full_transcript   = list(full_transcript)
        self._elapsed_seconds   = elapsed_seconds
        self._applied_enhancements: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def build_screen(self):
        """Return a PauseTranscriptionScreen pre-loaded with the current data."""
        from src.cli.screens.pause_transcription_screen import PauseTranscriptionScreen

        full_text = " ".join(self._full_transcript)
        mins, secs = divmod(int(self._elapsed_seconds), 60)
        time_str   = f"{mins:02d}:{secs:02d}"
        return PauseTranscriptionScreen(full_text=full_text, time_str=time_str)

    def process_result(
        self,
        app,                    # Textual App instance (for app.suspend())
        raw_result: object,
    ) -> Tuple[str, Optional[str]]:
        """
        Translate the raw dismiss value from PauseTranscriptionScreen into a
        clean (action, text | None) that the RecordingScreen understands.

        "enhance" is the only action handled here; the rest pass through.
        """
        if raw_result is None:
            return ("resume", None)

        if isinstance(raw_result, tuple) and len(raw_result) == 2:
            action, edited_text = raw_result
        else:
            action, edited_text = str(raw_result), None

        action = str(action)
        edited_text = str(edited_text) if edited_text is not None else None

        if action == "enhance":
            source_text = edited_text or " ".join(self._full_transcript)
            with app.suspend():
                final_text = self._run_enhance(source_text)
            return ("save", final_text)

        # "enhance_prompt" is handled entirely inside PauseTranscriptionScreen;
        # the screen dismisses with ("save", enhanced_text) directly.

        return (action, edited_text)

    @property
    def applied_enhancements(self) -> Optional[str]:
        """JSON-encoded list of applied AI layers, set after _run_enhance()."""
        return self._applied_enhancements

    # ── Private helpers ───────────────────────────────────────────────────────

    def _run_enhance(self, text: str, user_prompt: str | None = None) -> str:
        """
        Blocking enhancement flow — runs OUTSIDE Textual (via app.suspend()).

        Shows Rich panels for the original / enhanced text and a questionary
        prompt to let the user accept or reject.

        If user_prompt is provided it is prepended to current_text so the LLM
        agents see the instruction and adapt their output accordingly.

        Returns the text the user chose (enhanced or original).
        """
        try:
            import questionary
            from rich.panel import Panel

            from src.workflows.transcription_workflow import transcription_workflow
            from shared.schemas.workflow.transcription import (
                TranscriptionEnhancementState,
            )
        except ImportError as exc:
            _console.print(f"[red]Enhancement unavailable: {exc}[/red]")
            time.sleep(2)
            return text

        with _console.status("[bold cyan]Enhancing with AI…[/bold cyan]"):
            # If the user provided a custom instruction, prepend it so every
            # agent in the workflow can see and follow it.
            context_text = (
                f"[USER INSTRUCTION: {user_prompt}]\n\n{text}"
                if user_prompt
                else text
            )
            initial = TranscriptionEnhancementState(
                raw_text=text,
                current_text=context_text,
                applied_layers=[],
                action_items=None,
                error=None,
                user_prompt=user_prompt,
            )
            try:
                final = transcription_workflow.invoke(initial)
            except Exception as exc:
                _console.print(f"[red]Enhancement failed: {exc}[/red]")
                time.sleep(2)
                return text

        if final.get("error"):
            _console.print(f"[red]Enhancement error: {final['error']}[/red]")
            time.sleep(2)
            return text

        enhanced_text: str = final["current_text"]

        _console.clear()
        _console.print(
            Panel(text, title="[dim]Original[/dim]", border_style="dim")
        )
        _console.print(
            Panel(
                enhanced_text,
                title="[bold green]✨ Enhanced[/bold green]",
                border_style="green",
            )
        )

        try:
            choice = questionary.select(
                "Keep which version?",
                choices=[
                    questionary.Choice("  ✨ Keep Enhanced", "enhanced"),
                    questionary.Choice("  📝 Keep Original", "original"),
                ],
                instruction=" ",
            ).ask()
        except KeyboardInterrupt:
            choice = "original"

        if choice == "enhanced":
            self._applied_enhancements = json.dumps(
                final.get("applied_layers", [])
            )
            _console.print("[green]✨ Enhanced version applied.[/green]")
            time.sleep(1)
            return enhanced_text

        _console.print("[yellow]Original version kept.[/yellow]")
        time.sleep(1)
        return text
