"""
TranscriptionInteractor — orchestrates the live transcription FSM.

Extracted from src/cli/commands/live_transcription.py.

FSM states:
  device_select → record → paused → (enhance | save | edit | continue | restart | discard)

Usage::

    from src.cli.interactors.transcription_interactor import TranscriptionInteractor
    TranscriptionInteractor().run()
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import List, Optional

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

_QUESTIONARY_STYLE = questionary.Style([
    ("qmark", "fg:#673ab7 bold"),
    ("question", "bold"),
    ("answer", "fg:#f44336 bold"),
    ("pointer", "fg:#673ab7 bold"),
    ("highlighted", "fg:#673ab7 bold"),
    ("selected", "fg:#cc5454"),
    ("separator", "fg:#cc5454"),
    ("instruction", ""),
])


class TranscriptionInteractor:
    """
    Drives the full live-transcription user journey:
    device selection → recording loop → pause menu → save/enhance/edit/discard.
    """

    def __init__(self, audio_device_service=None, transcription_repo=None):
        self._audio_svc = audio_device_service
        self._transcription_repo = transcription_repo

        self._full_transcript: List[str] = []
        self._total_duration: float = 0.0
        self._applied_enhancements: Optional[str] = None
        self._raw_text: Optional[str] = None

    # ── Lazy dependency resolution ─────────────────────────────────────────

    def _get_audio_svc(self):
        if self._audio_svc is None:
            from src.services.audio_device_service import audio_device_service
            self._audio_svc = audio_device_service
        return self._audio_svc

    def _get_transcription_repo(self):
        if self._transcription_repo is None:
            from src.registry import repos
            self._transcription_repo = repos.transcriptions
        return self._transcription_repo

    # ── Public entry point ─────────────────────────────────────────────────

    def run(self) -> None:
        """Start the full transcription session. Blocks until done."""
        try:
            from src.cli.interactors._transcription_async import (
                start_transcription,
                HAS_TRANSCRIBE_DEPS,
            )
        except ImportError:
            HAS_TRANSCRIBE_DEPS = False

        if not HAS_TRANSCRIBE_DEPS:
            console.print("[red]Missing dependencies for live transcription.[/red]")
            console.print("Install them with: [bold]pip install sounddevice numpy amazon-transcribe[/bold]")
            return

        device_id = self._ensure_device()
        if device_id is None:
            return

        while True:
            # ── Recording phase ───────────────────────────────────────────
            state = {
                "transcript": self._full_transcript.copy(),
                "duration": self._total_duration,
                "applied_enhancements": self._applied_enhancements,
                "raw_text": self._raw_text,
            }
            try:
                asyncio.run(start_transcription(device_id, state))
            except KeyboardInterrupt:
                pass
            except Exception as exc:
                if "InvalidStateError" not in str(exc):
                    console.print(f"[red]Transcription error: {exc}[/red]")

            self._full_transcript = state["transcript"]
            self._total_duration = state["duration"]
            self._applied_enhancements = state.get("applied_enhancements")
            self._raw_text = state.get("raw_text")

            if not self._full_transcript:
                console.print("[yellow]No transcription captured.[/yellow]")
                return

            # ── Pause menu phase ──────────────────────────────────────────
            action = self._pause_menu()
            if action == "continue":
                continue
            elif action == "restart":
                self._full_transcript = []
                self._total_duration = 0.0
                self._raw_text = None
                self._applied_enhancements = None
                continue
            elif action == "save":
                self._do_save()
                return
            elif action == "discard":
                console.print("[yellow]Transcription discarded.[/yellow]")
                return
            elif action == "enhance":
                self._do_enhance()
                # Loop back to menu — don't restart recording
                continue
            elif action == "modify":
                # editing was applied inside the pause screen
                continue
            else:
                return

    # ── Private helpers ────────────────────────────────────────────────────

    def _ensure_device(self) -> Optional[int]:
        audio_svc = self._get_audio_svc()
        device_id = audio_svc.get_configured_device_id()

        if device_id is None or not audio_svc.is_device_available(device_id):
            if device_id is not None:
                console.print(f"[yellow]Configured device (ID: {device_id}) is not available.[/yellow]")
            else:
                console.print("[yellow]No audio input device configured.[/yellow]")

            from src.cli.screens.device_list_screen import run_device_list_ui
            devices = audio_svc.get_available_input_devices()
            if not devices:
                console.print("[red]No audio input devices found on this system.[/red]")
                return None
            selected = run_device_list_ui(devices, device_id)
            if selected is None:
                console.print("[red]Cancelled: no audio device selected.[/red]")
                return None

            audio_svc.set_configured_device_id(selected)
            device_id = selected
            console.print(f"[green]Audio device configured (ID: {device_id}).[/green]")

        return device_id

    def _pause_menu(self) -> str:
        from src.cli.screens.pause_transcription_screen import run_pause_transcription_ui

        full_text = " ".join(self._full_transcript).strip()
        mins, secs = divmod(int(self._total_duration), 60)

        screen = run_pause_transcription_ui(
            full_text=full_text,
            time_str=f"{mins:02d}:{secs:02d}",
        )

        # Apply any inline edits the user made inside the screen
        if screen.edited_text is not None:
            self._full_transcript = [screen.edited_text]

        return screen.result

    def _do_save(self) -> None:
        from shared.schemas.models.transcription import Transcription
        full_text = " ".join(self._full_transcript).strip()
        transcription = Transcription(
            content=self._raw_text if self._raw_text else full_text,
            duration_seconds=self._total_duration,
            enhanced_content=full_text if self._applied_enhancements else None,
            applied_enhancements=self._applied_enhancements,
        )
        self._get_transcription_repo().save_transcription(transcription)
        console.print(f"[green]Saved transcription ID: {transcription.id}[/green]")

    def _do_enhance(self) -> None:
        import json
        from src.workflows.transcription_workflow import transcription_workflow
        from shared.schemas.workflow.transcription import TranscriptionEnhancementState

        full_text = " ".join(self._full_transcript).strip()
        with console.status("[bold cyan]Enhancing with AI...[/bold cyan]"):
            initial = TranscriptionEnhancementState(
                raw_text=full_text,
                current_text=full_text,
                applied_layers=[],
                action_items=None,
                error=None,
            )
            final = transcription_workflow.invoke(initial)

        if final.get("error"):
            console.print(f"[red]Enhancement failed: {final['error']}[/red]")
            time.sleep(2)
            return

        enhanced_text = final["current_text"]
        console.clear()
        console.print(Panel(full_text, title="[dim]Original[/dim]", border_style="dim"))
        console.print(Panel(enhanced_text, title="[bold green]✨ Enhanced[/bold green]", border_style="green"))
        console.print(Panel("[bold cyan]Review:[/bold cyan]", style="blue", width=40))

        try:
            choice = questionary.select(
                " ",
                choices=[
                    questionary.Choice("  ✨ Keep Enhanced", "enhanced"),
                    questionary.Choice("  📝 Keep Original", "original"),
                ],
                style=_QUESTIONARY_STYLE,
                qmark="",
                pointer="●",
                instruction=" ",
            ).ask()
        except KeyboardInterrupt:
            choice = "original"

        if choice == "enhanced":
            self._raw_text = full_text
            self._full_transcript = [enhanced_text]
            self._applied_enhancements = json.dumps(final["applied_layers"])
            console.print("[green]✨ Enhanced version applied![/green]")
        else:
            console.print("[yellow]Original version kept.[/yellow]")
        time.sleep(1)

