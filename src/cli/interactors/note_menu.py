"""
src/cli/interactors/note_menu.py — backward-compat shim.

Real implementation has moved to NoteMenuInteractor in note_menu_interactor.py.
This module is kept so existing imports (ls.py, find.py, live_transcription.py)
continue to work without changes.
"""
from src.cli.interactors.note_menu_interactor import NoteMenuInteractor, show_note_action_menu  # noqa: F401

__all__ = ["show_note_action_menu", "NoteMenuInteractor"]
