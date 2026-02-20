"""
test_geo_accumulative.py
─────────────────────────
Integration test: verify the accumulative clustering philosophy end-to-end.

Sequence (from tests/fixtures/ground_truth.py GEO_SEQUENCE):
  Note 1: "Atomic notes"                    → no links yet        → NONE
  Note 2: "Evergreen notes"  (links→ N1)    → 2 unassigned islands → CREATE  (PKM Arch)
  Note 3: "Zettelkasten"     (links→ N1,N2) → notes already in arch → JOIN
  Note 4: "Docker containers"               → no links              → NONE

After each note we assert the archipelago assignment state.

Test is marked `integration` — requires real AWS/Bedrock credentials.
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_geo_accumulative.py -v -m integration
"""

from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.integration


def _has_aws_credentials() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ) or bool(os.getenv("AWS_PROFILE"))


@pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="AWS credentials not available; skipping Bedrock integration test",
)
def test_geo_accumulative_sequence(clean_db, note_factory):
    """
    Ingest the 4-note GEO_SEQUENCE through the full pipeline and verify
    archipelago assignments match the expected accumulative outcomes.

    Uses the live `ingest_workflow.ingest_graph` so the full node chain runs.
    """
    from tests.fixtures.ground_truth import GEO_SEQUENCE
    from src.workflows.ingest_workflow import ingest_graph
    from src.repository.note_repository import note_repository
    from src.repository.archipelago_repository import archipelago_repository
    from shared.schemas.workflow.ingest import IngestState

    ingested_note_ids: list[int] = []

    try:
        final_states: list[dict] = []

        for geo_note in GEO_SEQUENCE:
            initial_state = IngestState(raw_content=geo_note.content)
            result = ingest_graph.invoke(initial_state)

            # result may be dict or IngestState
            if isinstance(result, dict):
                note_id      = result.get("note_id")
                arch_action  = result.get("archipelago_action", "NONE")
                arch_id      = result.get("archipelago_id")
                arch_name    = result.get("archipelago_name")
            else:
                note_id      = result.note_id
                arch_action  = result.archipelago_action
                arch_id      = result.archipelago_id
                arch_name    = result.archipelago_name

            if note_id:
                ingested_note_ids.append(note_id)

            final_states.append({
                "note_id":     note_id,
                "action":      arch_action,
                "arch_id":     arch_id,
                "arch_name":   arch_name,
            })

    finally:
        # Cleanup
        from src.repository.link_repository import link_repository as lr
        for nid in ingested_note_ids:
            lr.delete_links_for_note(nid)
        for nid in ingested_note_ids:
            note_repository.delete_note(nid)

    # ── Assertions ───────────────────────────────────────────────────────────

    note1, note2, note3, note4 = final_states

    # Note 1: first note, nothing to link to → NONE
    assert note1["action"] == "NONE", (
        f"Note 1 should be NONE; got action='{note1['action']}'"
    )
    assert note1["arch_id"] is None, "Note 1 should not be in any archipelago"

    # Note 2: 2 unassigned linked notes (Note 1 + Note 2) → CREATE
    assert note2["action"] == "CREATE", (
        f"Note 2 should trigger CREATE; got action='{note2['action']}'. "
        "This means the linker did not connect Note 2 to Note 1, or MIN_ISLANDS > actual islands."
    )
    assert note2["arch_id"] is not None, "Note 2 should be assigned to the new archipelago"

    pkm_arch_id = note2["arch_id"]

    # Note 3: linked notes are already in pkm_arch_id → JOIN that arch
    assert note3["action"] == "JOIN", (
        f"Note 3 should JOIN existing archipelago; got action='{note3['action']}'"
    )
    assert note3["arch_id"] == pkm_arch_id, (
        f"Note 3 should join arch {pkm_arch_id}; joined {note3['arch_id']} instead"
    )

    # Note 4: unrelated topic, should produce no links → NONE
    assert note4["action"] == "NONE", (
        f"Note 4 (Docker) should be NONE (no thematic links); got '{note4['action']}'"
    )
    assert note4["arch_id"] is None, "Note 4 should not be assigned to any archipelago"

    # Bonus: verify Note 1 was also assigned to pkm_arch_id during CREATE
    note1_db = note_repository.get_note_by_id(note1["note_id"])
    assert note1_db is not None
    assert note1_db.archipelago_id == pkm_arch_id, (
        f"Note 1 should have been assigned to pkm arch {pkm_arch_id} during CREATE step; "
        f"has archipelago_id={note1_db.archipelago_id}"
    )
