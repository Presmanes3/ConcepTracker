"""
src/cli/ui.py — REMOVED.

All rendering logic lives in src/cli/views/ and src/cli/screens/.
This file is intentionally empty. Import directly from those packages.
"""
from src.cli.views.arch_views import archipelago_badge  # noqa: F401 – re-export for back-compat
from src.cli.views.note_views import note_card_view, note_header_view, note_detail_view  # noqa: F401
