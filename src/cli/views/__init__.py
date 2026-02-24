"""
src/cli/views/__init__.py

Convenience re-exports for the views package.
"""
from src.cli.views.arch_views import archipelago_badge, prefetch_arch_cache
from src.cli.views.note_views import note_card_view, note_list_table_view, note_find_table_view
from src.cli.views.link_views import link_table_view, links_inline_text
from src.cli.views.transcription_views import (
    render_recording_status,
    render_transcription_panel,
    render_navigation_panel,
)
from src.cli.views.pause_transcription_views import (
    render_pause_status,
    render_pause_transcript_body,
)
from src.cli.views.ingest_views import render_ingest_result
from src.cli.views.rm_views import render_delete_selection_table, render_delete_confirmation
from src.cli.views.config_views import render_config_list, render_config_summary, render_model_activated
from src.cli.views.stats_views import render_stats_dashboard
from src.cli.views.trace_views import render_trace_timeline
from src.cli.views.open_note_views import open_note_top_panel, open_note_actions_panel
from src.cli.views.device_views import render_device_table, render_device_nav_panel

__all__ = [
    "archipelago_badge",
    "prefetch_arch_cache",
    "note_card_view",
    "note_list_table_view",
    "note_find_table_view",
    "link_table_view",
    "links_inline_text",
    "render_recording_status",
    "render_transcription_panel",
    "render_navigation_panel",
    "render_pause_status",
    "render_pause_transcript_body",
    "render_ingest_result",
    "render_delete_selection_table",
    "render_delete_confirmation",
    "render_config_list",
    "render_config_summary",
    "render_model_activated",
    "render_stats_dashboard",
    "render_trace_timeline",
    "open_note_top_panel",
    "open_note_actions_panel",
    "render_device_table",
    "render_device_nav_panel",
]
