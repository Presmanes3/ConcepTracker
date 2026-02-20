"""
test_linker_precision.py
─────────────────────────
Integration test: LinkerAgent precision and recall against ground-truth pairs.

Each pair is ingested (embedding + normalise + link) and we check:
  • Precision  = TP / (TP + FP)  ≥ 0.80
  • Recall     = TP / (TP + FN)  ≥ 0.70

Test is marked `integration` — requires real AWS/Bedrock credentials.
Run with:
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_linker_precision.py -v -m integration

IMPORTANT: This test mutates the database.  Run against a dev/test DB only.
It cleans up after itself (deletes all created notes and links).
"""

from __future__ import annotations

import os
import pytest
from typing import Optional

pytestmark = pytest.mark.integration


# ── Skip guard: don't run without credentials ─────────────────────────────────

def _has_aws_credentials() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ) or bool(os.getenv("AWS_PROFILE"))


# ── Test ──────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="AWS credentials not available; skipping Bedrock integration test",
)
def test_linker_precision_and_recall(clean_db, note_factory):
    """
    End-to-end precision/recall test for the LinkerAgent.

    Strategy:
      1. Persist each note in a ground-truth pair individually.
      2. After persisting note B, run an embedding similarity search against
         note A (already in the DB).
      3. Run the LinkerAgent on note B with note A as a candidate.
      4. Record whether a link was created and whether it was expected.
    """
    from tests.fixtures.ground_truth import SHOULD_LINK, SHOULD_NOT_LINK
    from src.agents.linker_agent import LinkerAgent
    from src.utils.embeddings import get_embeddings_client
    from src.repository.note_repository import note_repository
    from src.repository.link_repository import link_repository
    from shared.schemas.workflow.ingest import IngestState

    embedder = get_embeddings_client()

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    created_note_ids: list[int] = []

    try:
        all_pairs = [
            (pair, True)  for pair in SHOULD_LINK
        ] + [
            (pair, False) for pair in SHOULD_NOT_LINK
        ]

        for pair, should_link in all_pairs:
            # Embed and persist note A
            emb_a = embedder.embed_query(pair.note_a)
            note_a = note_factory(
                content=pair.note_a,
                summary=pair.summary_a,
                tags="integration-test",
            )
            # Persist embedding (update directly — factory skips embedding)
            from src.utils.db import get_session
            from shared.schemas.models.note import Note
            with get_session() as session:
                na = session.get(Note, note_a.id)
                if na:
                    na.embedding = emb_a
                    session.add(na)
                    session.commit()
            created_note_ids.append(note_a.id)

            # Embed note B and build a minimal IngestState for the linker
            emb_b = embedder.embed_query(pair.note_b)

            note_b = note_factory(
                content=pair.note_b,
                summary=pair.summary_b,
                tags="integration-test",
            )
            with get_session() as session:
                nb = session.get(Note, note_b.id)
                if nb:
                    nb.embedding = emb_b
                    session.add(nb)
                    session.commit()
            created_note_ids.append(note_b.id)

            # Simulate the search-for-linking step: find notes similar to note B
            from src.repository.note_repository import note_repository as nr
            from src.utils.embeddings import DISTANCE_LINKING_CUTOFF
            similar = nr.find_similar_notes(
                embedding=emb_b,
                top_k=5,
                exclude_id=note_b.id,
                max_distance=DISTANCE_LINKING_CUTOFF,
            )

            # Build IngestState for the linker
            from shared.schemas.workflow.ingest import IngestState
            state = IngestState(
                raw_content=pair.note_b,
                note_id=note_b.id,
                note_summary=pair.summary_b,
                similar_notes=[
                    {
                        "id": s["id"],
                        "summary": s["summary"],
                        "distance": s.get("distance", 1.0),
                    }
                    for s in similar
                ],
            )

            agent = LinkerAgent()
            result = agent.run(state)
            links_created: list = result.get("links", [])

            # Check whether note_a appears in the links
            linked_to_a = any(
                (lnk.get("target_id") if isinstance(lnk, dict) else lnk.target_id) == note_a.id
                for lnk in links_created
            )

            if should_link and linked_to_a:
                true_positives += 1
            elif not should_link and linked_to_a:
                false_positives += 1
            elif should_link and not linked_to_a:
                false_negatives += 1
            # true_negatives (not should_link and not linked) are fine, not tracked

    finally:
        # Clean up all created notes (cascade deletes links)
        from src.repository.link_repository import link_repository as lr
        for nid in set(created_note_ids):
            lr.delete_links_for_note(nid)
        for nid in set(created_note_ids):
            note_repository.delete_note(nid)

    # ── Contract assertions ───────────────────────────────────────────────────
    total_should_link = len(SHOULD_LINK)
    total_positives_predicted = true_positives + false_positives

    precision = true_positives / total_positives_predicted if total_positives_predicted > 0 else 0.0
    recall    = true_positives / total_should_link          if total_should_link > 0 else 0.0

    print(f"\n  TP={true_positives}, FP={false_positives}, FN={false_negatives}")
    print(f"  Precision={precision:.2f}  Recall={recall:.2f}")

    assert precision >= 0.80, (
        f"Precision {precision:.2f} below 0.80 contract "
        f"(TP={true_positives}, FP={false_positives})"
    )
    assert recall >= 0.70, (
        f"Recall {recall:.2f} below 0.70 contract "
        f"(TP={true_positives}, FN={false_negatives})"
    )
