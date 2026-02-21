import asyncio
import os
import time
import sys
import questionary

# Suppress the specific InvalidStateError from concurrent.futures that AWS Transcribe SDK tends to throw on cancellation
# This is a monkey-patch or just a global handler approach if possible, but since it happens in a thread, 
# we might need to be aggressive.
def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    if "InvalidStateError" in str(msg) or "CANCELLED" in str(msg):
        return
    if "future" in context and "InvalidStateError" in str(context["future"]):
        return
    loop.default_exception_handler(context)

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from src.cli.registry import registry
from src.repository.transcription_repository import transcription_repository
from shared.schemas.models.transcription import Transcription
from src.services.audio_device_service import audio_device_service
from src.cli.interactors.device_selector import select_audio_device_ui

console = Console()

try:
    import sounddevice
    # Monkey-patch AwsCrtHttpResponse._on_body to prevent Future cancellation crash
    # We do this BEFORE importing TranscribeStreamingClient to ensure it catches the import
    import amazon_transcribe.httpsession
    from concurrent.futures import InvalidStateError as ConcurrentInvalidStateError

    # The class responsible for handling HTTP chunks in amazon-transcribe-v2 is AwsCrtHttpResponse
    target_class = getattr(amazon_transcribe.httpsession, "AwsCrtHttpResponse", None)
    
    if target_class:
        _original_on_body = target_class._on_body
        
        def _safe_on_body(self, chunk: bytes, **kwargs):
            try:
                _original_on_body(self, chunk, **kwargs)
            except ConcurrentInvalidStateError:
                # Future was cancelled, ignore the update
                pass
        
        target_class._on_body = _safe_on_body

    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent
    
    HAS_TRANSCRIBE_DEPS = True
except ImportError:
    HAS_TRANSCRIBE_DEPS = False

class LiveTranscriptionHandler(TranscriptResultStreamHandler):
    def __init__(self, stream, console, initial_transcript=None, initial_duration=0.0):
        super().__init__(stream)
        self.console = console
        self.full_transcript = initial_transcript.copy() if initial_transcript else []
        self.current_partial = ""
        self.initial_duration = initial_duration
        self.start_time = time.time()
        self.live = Live(console=self.console, refresh_per_second=10, transient=False)
        self.live.start()

    def _update_display(self):
        # Calculate stats
        elapsed = self.initial_duration + (time.time() - self.start_time)
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins:02d}:{secs:02d}"
        
        full_text = " ".join(self.full_transcript)
        words = len(full_text.split())
        tokens = int(words * 1.3) # rough estimate
        
        # Blinking recording indicator (changes every 0.5 seconds)
        is_blink_on = int(time.time() * 2) % 2 == 0
        rec_icon = "●" if is_blink_on else "○"
        rec_style = "bold red" if is_blink_on else "dim red"
        
        # Info Panel
        info_text = Text.from_markup(
            f"[{rec_style}]{rec_icon}[/{rec_style}] [bold red]RECORDING[/bold red] | "
            f"[cyan]Time:[/cyan] {time_str} | "
            f"[cyan]Words:[/cyan] {words} | "
            f"[cyan]Tokens (est):[/cyan] ~{tokens}"
        )
        info_panel = Panel(info_text, border_style="blue", title="[bold]Status[/bold]")
        
        # Transcription Panel
        trans_text = Text()
        
        # To prevent infinite vertical growth and keep the newest text visible,
        # we only display the last ~100 words of the transcription.
        display_words = full_text.split()[-100:]
        display_text = " ".join(display_words)
        
        if display_words and len(full_text.split()) > 100:
            trans_text.insert(0, "... ", style="dim") # Correction: insert at beginning if truncated
            
        if display_text:
            trans_text.append(display_text + " ", style="green")
            
        if self.current_partial:
            trans_text.append(self.current_partial, style="dim")
            
        trans_panel = Panel(
            Align.left(trans_text, vertical="top"), 
            border_style="green", 
            title="[bold]Live Transcription (Latest)[/bold]",
            height=10
        )
        
        # Footer controls - Cleaner UX
        footer_text = Text.from_markup("[dim]Press[/dim] [bold cyan]Ctrl+C[/bold cyan] [dim]to pause or stop recording[/dim]")
        footer_panel = Panel(Align.center(footer_text), border_style="dim")

        # Layout: Status -> Transciption -> Footer
        self.live.update(Group(info_panel, trans_panel, footer_panel))

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                if result.is_partial:
                    self.current_partial = alt.transcript
                else:
                    self.full_transcript.append(alt.transcript)
                    self.current_partial = ""
                self._update_display()

    def close(self):
        self.live.stop()

async def mic_stream(device_id: int):
    loop = asyncio.get_event_loop()
    input_queue = asyncio.Queue()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

    stream = sounddevice.RawInputStream(
        device=device_id,
        channels=1,
        samplerate=16000,
        callback=callback,
        blocksize=1024 * 2,
        dtype='int16',
    )
    with stream:
        while True:
            try:
                # Use a timeout so the loop can check for cancellation regularly
                indata, status = await asyncio.wait_for(input_queue.get(), timeout=1.0)
                yield indata, status
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

async def write_chunks(stream, device_id: int):
    async for chunk, status in mic_stream(device_id):
        await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()

async def start_transcription(device_id: int, state: dict):
    # Set custom exception handler for this loop to suppress AWS SDK cancellation noise
    loop = asyncio.get_running_loop()
    
    def handle_exception(loop, context):
        msg = context.get("exception", context["message"])
        if "InvalidStateError" in str(msg) or "CANCELLED" in str(msg):
            return
        if "future" in context and "InvalidStateError" in str(context.get("future", "")):
            return
        # Delegate to default handler
        loop.default_exception_handler(context)

    loop.set_exception_handler(handle_exception)

    region = os.getenv("AWS_REGION", "eu-west-1")
    client = TranscribeStreamingClient(region=region)
    
    stream = await client.start_stream_transcription(
        language_code="es-ES", 
        media_sample_rate_hz=16000,
        media_encoding="pcm"
    )
    
    # Initialize from state
    initial_transcript = state.get("transcript", [])
    initial_duration = state.get("duration", 0.0)
    
    handler = LiveTranscriptionHandler(stream.output_stream, console, initial_transcript, initial_duration)
    handler._update_display()
    
    # console.print("[yellow]Listening... Press Ctrl+C to pause/stop.[/yellow]") # Removed per user request
    
    try:
        await asyncio.gather(write_chunks(stream, device_id), handler.handle_events())
    except asyncio.CancelledError:
        pass
    except Exception as e:
        # Catch other exceptions to avoid crashing the loop
        # We check for the specific concurrent.futures error message if possible, though it's string-based
        if "InvalidStateError" not in str(e):
             # Only print unexpected errors that aren't the result of improved cancellation handling
             console.print(f"[red]Error during transcription: {e}[/red]")
    finally:
        handler.close()
        # Update state directly
        state["transcript"] = handler.full_transcript
        state["duration"] = handler.initial_duration + (time.time() - handler.start_time)

@registry.register(
    name="live_transcription",
    description="Start a real-time transcription session using AWS Transcribe.",
    example="ct live_transcription"
)
def live_transcription():
    """Start a real-time transcription session using AWS Transcribe."""
    if not HAS_TRANSCRIBE_DEPS:
        console.print("[red]Missing dependencies for live transcription.[/red]")
        console.print("Please install them by running: [bold]pip install sounddevice numpy amazon-transcribe[/bold]")
        return

    # Check audio device configuration
    configured_device_id = audio_device_service.get_configured_device_id()
    
    if configured_device_id is None or not audio_device_service.is_device_available(configured_device_id):
        if configured_device_id is not None:
            console.print(f"[yellow]Configured device (ID: {configured_device_id}) is not available.[/yellow]")
        else:
            console.print("[yellow]No audio input device configured.[/yellow]")
            
        devices = audio_device_service.get_available_input_devices()
        selected_device_id = select_audio_device_ui(devices, configured_device_id)
        
        if selected_device_id is None:
            console.print("[red]Transcription cancelled: No audio device selected.[/red]")
            return
            
        audio_device_service.set_configured_device_id(selected_device_id)
        configured_device_id = selected_device_id
        console.print(f"[green]Audio device configured successfully (ID: {configured_device_id}).[/green]")

    full_transcript = []
    total_duration = 0.0
    applied_enhancements = None
    raw_text = None

    while True:
        # Prepare state container for the async function
        state_container = {
            "transcript": full_transcript.copy(), 
            "duration": total_duration,
            "applied_enhancements": applied_enhancements,
            "raw_text": raw_text
        }
        
        try:
            # We wrap the run call to catch any stray exceptions from the event loop shutdown
            asyncio.run(start_transcription(configured_device_id, state_container))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            # If it's the specific AWS/Future error, ignore it
            if "InvalidStateError" not in str(e):
                 # Useful for debugging other errors, but suppress the known crash
                 pass

        # Update local variables from the state container
        full_transcript = state_container["transcript"]
        total_duration = state_container["duration"]
        applied_enhancements = state_container.get("applied_enhancements")
        raw_text = state_container.get("raw_text")
            
        if not full_transcript:
            console.print("[yellow]No transcription captured.[/yellow]")
            return
            
        # Interactive Menu Loop
        while True:
            console.clear()
            
            # Print current state
            mins, secs = divmod(int(total_duration), 60)
            time_str = f"{mins:02d}:{secs:02d}"
            
            full_text = " ".join(full_transcript).strip()
            words = len(full_text.split())
            tokens = int(words * 1.3)
            
            info_text = Text.from_markup(
                f"[bold yellow]⏸ PAUSED[/bold yellow] | "
                f"[cyan]Time:[/cyan] {time_str} | "
                f"[cyan]Words:[/cyan] {words} | "
                f"[cyan]Tokens (est):[/cyan] ~{tokens}"
            )
            
            trans_panel = Panel(
                full_text, 
                border_style="green", 
                title="[bold]Live Transcription (Paused)[/bold]"
            )
            
            # Show Status first, then Transcription
            console.print(Panel(info_text, border_style="yellow", title="[bold]Status[/bold]"))
            console.print(trans_panel)
            
            # Print a visual "Action Menu" header using Panel since questionary cannot be boxed
            console.print(Panel("[bold cyan]Choose an action:[/bold cyan]", style="blue", width=40))

            try:
                # Use a custom style for the questionary to look cleaner
                custom_style = questionary.Style([
                    ('qmark', 'fg:#673ab7 bold'),       # token in front of the question
                    ('question', 'bold'),               # question text
                    ('answer', 'fg:#f44336 bold'),      # submitted answer text behind the question
                    ('pointer', 'fg:#673ab7 bold'),     # pointer used in select and checkbox prompts
                    ('highlighted', 'fg:#673ab7 bold'), # pointed-at choice in select and checkbox prompts
                    ('selected', 'fg:#cc5454'),         # style for a selected checkbox of a checkbox prompt
                    ('separator', 'fg:#cc5454'),        # separator in lists
                    ('instruction', ''),                # user instructions for select, rawselect, checkbox
                ])

                action = questionary.select(
                    " ",  # Space to avoid printing anything if empty string defaults back
                    choices=[
                        questionary.Choice("  ✨ Enhance with AI", "enhance"),
                        questionary.Choice("  💾 Save Transcription", "save"),
                        questionary.Choice("  ✏️  Edit Text", "modify"),
                        questionary.Choice("  ▶️  Resume Recording", "continue"),
                        questionary.Choice("  🔄 New Session", "restart"),
                        questionary.Choice("  ❌ Discard", "discard")
                    ],
                    style=custom_style,
                    qmark="",
                    pointer="●",  # The "circulitos" requested
                    instruction=" " # Hides the instruction text
                ).ask()
            except KeyboardInterrupt:
                # If during the menu user presses Ctrl+C AGAIN, it likely means exit
                # Or we can just loop back. Let's make it exit to avoid stuck loop
                console.print("[yellow]Exiting via KeyboardInterrupt...[/yellow]")
                return

            if action == "enhance":
                from src.workflows.transcription_workflow import transcription_workflow
                from shared.schemas.workflow.transcription import TranscriptionEnhancementState
                import json
                
                with console.status("[bold cyan]Enhancing transcription with AI...[/bold cyan]"):
                    initial_state = TranscriptionEnhancementState(
                        raw_text=full_text,
                        current_text=full_text,
                        applied_layers=[],
                        action_items=None,
                        error=None
                    )
                    
                    final_state = transcription_workflow.invoke(initial_state)
                
                if final_state.get("error"):
                    console.print(f"[red]Enhancement failed: {final_state['error']}[/red]")
                    time.sleep(2)
                else:
                    enhanced_text = final_state["current_text"]
                    original_text = final_state["raw_text"]
                    
                    console.clear()
                    console.print(Panel(info_text, border_style="yellow", title="[bold]Status[/bold]"))
                    
                    # Show comparison
                    console.print(Panel(original_text, title="[dim]Original Transcription[/dim]", border_style="dim"))
                    console.print(Panel(enhanced_text, title="[bold green]✨ Enhanced Transcription[/bold green]", border_style="green"))
                    
                    console.print(Panel("[bold cyan]Review the enhancement:[/bold cyan]", style="blue", width=40))
                    
                    try:
                        choice = questionary.select(
                            " ",
                            choices=[
                                questionary.Choice("  ✨ Keep Enhanced", "enhanced"),
                                questionary.Choice("  📝 Keep Original", "original"),
                            ],
                            style=custom_style,
                            qmark="",
                            pointer="●",
                            instruction=" "
                        ).ask()
                    except KeyboardInterrupt:
                        choice = "original"
                    
                    if choice == "enhanced":
                        full_transcript = [enhanced_text]
                        state_container["transcript"] = full_transcript
                        
                        applied_enhancements = json.dumps(final_state["applied_layers"])
                        raw_text = original_text
                        state_container["applied_enhancements"] = applied_enhancements
                        state_container["raw_text"] = raw_text
                        
                        console.print("[green]✨ Enhanced version applied![/green]")
                    else:
                        console.print("[yellow]Original version kept.[/yellow]")
                        
                    time.sleep(1) # Brief pause to show success message
                
                # Loop back to the menu to let them save or edit the enhanced text
                continue

            elif action == "save":
                import json
                transcription = Transcription(
                    content=raw_text if raw_text else full_text, # Original text
                    duration_seconds=total_duration,
                    enhanced_content=full_text if applied_enhancements else None,
                    applied_enhancements=applied_enhancements
                )
                transcription_repository.save_transcription(transcription)
                console.print(f"[green]Saved transcription with ID: {transcription.id}[/green]")
                return
            elif action == "discard":
                console.print("[yellow]Transcription discarded.[/yellow]")
                return
            elif action == "continue":
                break # Break inner loop, resume transcription
            elif action == "restart":
                full_transcript = []
                total_duration = 0.0
                raw_text = None
                applied_enhancements = None
                state_container["transcript"] = []
                state_container["duration"] = 0.0
                state_container["raw_text"] = None
                state_container["applied_enhancements"] = None
                break # Break inner loop, restart transcription
            elif action == "modify":
                console.clear()
                
                # Status AT TOP
                console.print(Panel(info_text, border_style="yellow", title="[bold]Status[/bold]"))
                
                # Simulate the top border of the panel
                console.print("[green]╭─ Live Transcription (Modifying) [dim](Finish: Alt+Enter / Esc+Enter)[/dim] ─────────╮[/green]")
                
                # Use questionary with minimal styling
                try:
                    edited_text = questionary.text(
                        "", 
                        default=full_text,
                        multiline=True,
                        qmark="",
                        instruction="" 
                    ).ask()
                except KeyboardInterrupt:
                    # If user cancels modification with Ctrl+C, keep original text
                    edited_text = None
                
                # Simulate bottom border
                console.print("[green]╰────────────────────────────────────────────────────────────────────────────╯[/green]")
                
                if edited_text is not None:
                    # Show footer instruction or status if needed
                    full_transcript = [edited_text]
                    state_container["transcript"] = [edited_text]
