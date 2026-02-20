"""
test_geo_router.py
──────────────────
Unit tests for the geo_router node in geo_workflow.py.

All repository calls are mocked so no DB or AWS calls are made.

Scenarios:
  1. No links → NONE
  2. All linked notes unassigned, count < MIN_ISLANDS → NONE
  3. All linked notes unassigned, count >= MIN_ISLANDS → CREATE
  4. One linked note in an archipelago → JOIN (that archipelago)
  5. Multiple archs tied by frequency → JOIN most-recently-created
  6. Mixed: some assigned, some not — JOIN wins (accumulative rule)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from shared.schemas.workflow.geo import GeoState
from shared.schemas.models.archipelago import Archipelago


# ── Helpers ───────────────────────────────────────────────────────────────────

def _link(target_id: int) -> dict:
    return {"target_id": target_id, "relation_type": "RELATES", "reason": "test"}


def _arch(arch_id: int, created_delta_seconds: int = 0) -> Archipelago:
    """Build an in-memory Archipelago (not persisted)."""
    return Archipelago(
        id=arch_id,
        name=f"Arch {arch_id}",
        summary="test",
        type="archipelago",
        created_at=datetime(2024, 1, 1) + timedelta(seconds=created_delta_seconds),
    )


def _run_router(links: list[dict], arch_for_note: dict[int, Archipelago | None]) -> dict:
    """
    Call geo_router with the given links.
    `arch_for_note` maps note_id → Archipelago (or None if unassigned).
    """
    state = GeoState(note_id=999, note_summary="test note", links=links)

    def _mock_get_arch_for_note(note_id: int):
        return arch_for_note.get(note_id, None)

    with patch(
        "src.workflows.geo_workflow.archipelago_repository.get_archipelago_for_note",
        side_effect=_mock_get_arch_for_note,
    ), patch(
        "src.workflows.geo_workflow.archipelago_repository.get_archipelago_by_id",
        side_effect=lambda aid: next(
            (a for a in arch_for_note.values() if a and a.id == aid), None
        ),
    ):
        from src.workflows.geo_workflow import geo_router
        return geo_router(state)


# ── Test cases ───────────────────────────────────────────────────────────────

class TestGeoRouterNone:

    def test_no_links_returns_none(self):
        result = _run_router(links=[], arch_for_note={})
        assert result["geo_decision"] == "NONE"

    def test_single_unassigned_link_returns_none(self):
        """One unassigned island is below MIN_ISLANDS=2; nothing to cluster."""
        result = _run_router(
            links=[_link(1)],
            arch_for_note={1: None},
        )
        assert result["geo_decision"] == "NONE"


class TestGeoRouterCreate:

    def test_two_unassigned_links_triggers_create(self):
        """MIN_ISLANDS=2: exactly two unassigned linked notes → CREATE."""
        result = _run_router(
            links=[_link(1), _link(2)],
            arch_for_note={1: None, 2: None},
        )
        assert result["geo_decision"] == "CREATE"
        assert set(result["cluster_note_ids"]) == {1, 2}

    def test_three_unassigned_links_triggers_create(self):
        result = _run_router(
            links=[_link(1), _link(2), _link(3)],
            arch_for_note={1: None, 2: None, 3: None},
        )
        assert result["geo_decision"] == "CREATE"
        assert len(result["cluster_note_ids"]) == 3


class TestGeoRouterJoin:

    def test_one_assigned_note_triggers_join(self):
        arch = _arch(arch_id=10)
        result = _run_router(
            links=[_link(1)],
            arch_for_note={1: arch},
        )
        assert result["geo_decision"] == "JOIN"
        assert result["target_archipelago_id"] == 10

    def test_join_beats_create_when_mixed(self):
        """
        Accumulative rule: even if there are unassigned islands, JOIN wins
        as long as at least one linked note is already in an archipelago.
        """
        arch = _arch(arch_id=20)
        result = _run_router(
            links=[_link(1), _link(2), _link(3)],
            arch_for_note={1: arch, 2: None, 3: None},  # only note 1 assigned
        )
        assert result["geo_decision"] == "JOIN"
        assert result["target_archipelago_id"] == 20

    def test_most_frequent_arch_wins(self):
        """When multiple archs appear, the one with more linked notes wins."""
        arch_5 = _arch(arch_id=5)
        arch_6 = _arch(arch_id=6)
        result = _run_router(
            links=[_link(1), _link(2), _link(3)],
            arch_for_note={1: arch_5, 2: arch_5, 3: arch_6},
        )
        assert result["geo_decision"] == "JOIN"
        assert result["target_archipelago_id"] == 5  # arch_5 appears twice

    def test_tie_broken_by_recency_most_recent_wins(self):
        """
        When two archs tie on frequency, the most recently created wins.
        arch_newer has a later created_at.
        """
        arch_older = _arch(arch_id=30, created_delta_seconds=0)
        arch_newer = _arch(arch_id=31, created_delta_seconds=3600)  # 1 hour later

        result = _run_router(
            links=[_link(1), _link(2)],
            arch_for_note={1: arch_older, 2: arch_newer},
        )
        assert result["geo_decision"] == "JOIN"
        assert result["target_archipelago_id"] == 31  # newer wins the tie
