"""
test_similarity_tiers.py
────────────────────────
Unit tests for the similarity_tier() helper in src/utils/embeddings.py.

All tests are pure functions — zero LLM calls, zero DB connections.
"""

import pytest
from src.utils.embeddings import (
    similarity_tier,
    DISTANCE_TIERS,
    DISTANCE_LINKING_CUTOFF,
    DISTANCE_DEDUP_CUTOFF,
)


# ── Boundary / happy-path tests ───────────────────────────────────────────────

class TestSimilarityTierBoundaries:
    """Verify every tier label and its exact thresholds."""

    def test_zero_distance_is_high_similarity(self):
        """Identical vectors (distance=0) are 'High similarity'."""
        assert similarity_tier(0.0) == "High similarity"

    def test_just_below_high_threshold(self):
        assert similarity_tier(0.54) == "High similarity"

    def test_at_high_threshold_steps_up(self):
        """0.55 is the first value that falls into 'Moderate'."""
        assert similarity_tier(0.55) == "Moderate similarity"

    def test_moderate_range(self):
        assert similarity_tier(0.60) == "Moderate similarity"
        assert similarity_tier(0.74) == "Moderate similarity"

    def test_at_moderate_threshold_steps_up(self):
        """0.75 is the first value in 'Weak topical connection'."""
        assert similarity_tier(0.75) == "Weak topical connection"

    def test_weak_topical_range(self):
        assert similarity_tier(0.80) == "Weak topical connection"
        assert similarity_tier(0.89) == "Weak topical connection"
        assert similarity_tier(0.90) == "Weak topical connection"   # previously Distant at old cutoff 0.90
        assert similarity_tier(0.94) == "Weak topical connection"   # just below new cutoff

    def test_at_linking_cutoff_is_distant(self):
        """0.95 equals DISTANCE_LINKING_CUTOFF — should be 'Distant'."""
        assert similarity_tier(0.95) == "Distant"

    def test_above_cutoff_is_distant(self):
        assert similarity_tier(0.95) == "Distant"
        assert similarity_tier(1.50) == "Distant"
        assert similarity_tier(2.00) == "Distant"  # theoretical cosine max


class TestSimilarityTierConstants:
    """Verify the exported constants have sensible values."""

    def test_dedup_cutoff_is_stricter_than_linking(self):
        """Dedup threshold must be lower (stricter) than the linking cutoff."""
        assert DISTANCE_DEDUP_CUTOFF < DISTANCE_LINKING_CUTOFF

    def test_linking_cutoff_matches_distant_tier(self):
        """
        The linking cutoff should equal the last tier threshold so that
        'Distant' notes are excluded consistently.
        """
        last_threshold = DISTANCE_TIERS[-1][0]
        assert DISTANCE_LINKING_CUTOFF == last_threshold

    def test_tiers_are_ordered_ascending(self):
        """Tier thresholds must be strictly ascending."""
        thresholds = [t for t, _ in DISTANCE_TIERS]
        assert thresholds == sorted(thresholds)

    def test_tiers_cover_all_four_labels(self):
        """There should be exactly 3 explicit tiers (Distant is implicit fallback)."""
        labels = [label for _, label in DISTANCE_TIERS]
        assert "High similarity" in labels
        assert "Moderate similarity" in labels
        assert "Weak topical connection" in labels
        assert len(labels) == 3


class TestSimilarityTierEdgeCases:
    """Edge cases and defensive checks."""

    def test_negative_distance_treated_as_high(self):
        """Negative distances (shouldn't happen with pgvector but be safe) → High."""
        assert similarity_tier(-0.01) == "High similarity"

    def test_returns_string_always(self):
        for dist in [0.0, 0.5, 0.9, 1.1]:
            result = similarity_tier(dist)
            assert isinstance(result, str)
            assert len(result) > 0
