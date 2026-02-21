"""
src/cli/views/__init__.py

Convenience re-exports for the views package.
"""
from src.cli.views.arch_views import archipelago_badge, prefetch_arch_cache
from src.cli.views.note_views import note_card_view, note_header_view, note_detail_view
from src.cli.views.link_views import link_table_view, links_inline_text
from src.cli.views.transcription_views import LiveTranscriptionView
from src.cli.views.ingest_views import render_ingest_result
from src.cli.views.rm_views import render_delete_selection_table, render_delete_confirmation
from src.cli.views.config_views import render_config_list, render_config_summary, render_model_activated
from src.cli.views.stats_views import render_stats_dashboard
from src.cli.views.trace_views import render_trace_timeline

__all__ = [
    "archipelago_badge",
    "prefetch_arch_cache",
    "note_card_view",
    "note_header_view",
    "note_detail_view",
    "link_table_view",
    "links_inline_text",
    "LiveTranscriptionView",
    "render_ingest_result",
    "render_delete_selection_table",
    "render_delete_confirmation",
    "render_config_list",
    "render_config_summary",
    "render_model_activated",
    "render_stats_dashboard",
    "render_trace_timeline",
]
