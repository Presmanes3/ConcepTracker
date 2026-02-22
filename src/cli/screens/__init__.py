"""
src/cli/screens/ — Interactive TUI screens (AppScreen subclasses).

A screen owns: Layout structure, input event loop, keypress → ScreenSignal mapping.
Screens do NOT touch the database, call agents, or contain business logic.

Public API
----------
paginate_table, paginate_panels
build_tag_selector_ui, select_tags_ui, TagSelectorUI, TagPanel
select_audio_device_ui
OpenNoteScreen
"""

from src.cli.screens.device_selector import select_audio_device_ui
from src.cli.screens.pager import paginate_panels, paginate_table
from src.cli.screens.tag_selector import (
    TagPanel,
    TagSelectorUI,
    build_tag_selector_ui,
    select_tags_ui,
)
from src.cli.screens.open_note_screen import OpenNoteScreen
from src.cli.screens.device_list_screen import DeviceListScreen, run_device_list_ui

__all__ = [
    # pager
    "paginate_table",
    "paginate_panels",
    # tag_selector
    "build_tag_selector_ui",
    "select_tags_ui",
    "TagSelectorUI",
    "TagPanel",
    # device_selector
    "select_audio_device_ui",
    # open_note_screen
    "OpenNoteScreen",
    # device_list_screen
    "DeviceListScreen",
    "run_device_list_ui",
]
