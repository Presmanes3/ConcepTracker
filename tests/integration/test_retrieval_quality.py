"""
tests/integration/test_retrieval_quality.py
═══════════════════════════════════════════════════════════════════════════════
CAPA 2 — Calidad del retrieval (con DB, SIN llamadas al LLM generativo)

Qué mide: ¿los candidatos CORRECTOS llegan al límite del cutoff para poder ser
evaluados por el LLM?  ¿Los pares homónimos están bien ranqueados (alto) o bajo?

Lógica:
  • Para cada nota ancla, se calculan las distancias a sus vecinos conocidos.
  • Se comprueba rank: el verdadero positivo debe aparecer en top-K de similitud.
  • Los homónimos deben aparecer con rango INFERIOR a los verdaderos positivos.

Esto es la "autopsia del retrieval": si un par NUNCA llega al LLM, el linker
nunca tendrá la oportunidad de crear el link, independientemente de su calidad.

Run:
    $env:AWS_PROFILE="aws-presmanes-home"
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_retrieval_quality.py -v -s
"""
from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.integration


def _has_aws_credentials() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ) or bool(os.getenv("AWS_PROFILE"))


skip_no_creds = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="AWS credentials not available",
)


# ═══════════════════════════════════════════════════════════════════════════════
# CORPUS DEFINITION
#
# Each "anchor" has:
#   - a text to embed
#   - a list of TRUE_NEIGHBORS: notes that MUST appear in top-K retrieval
#   - a list of HOMONYM_TRAPS: notes that MUST rank LOWER than true neighbors
#     (the LLM can still reject them, but at least they should not be ranked
#      as more similar than the actual true positives)
# ═══════════════════════════════════════════════════════════════════════════════

RETRIEVAL_SCENARIOS = [
    {
        "anchor_id": "docker",
        "anchor_text": "Docker containers package applications with their dependencies into portable units that run consistently across environments.",
        "true_neighbors": [
            {
                "id": "ci_cd",
                "text": "CI/CD pipelines automate the build, test and deploy steps every time new code is committed to version control.",
            },
            {
                "id": "kubernetes",
                "text": "Kubernetes orchestrates containerised workloads across clusters, handling scaling, self-healing and rolling deployments.",
            },
        ],
        "homonym_traps": [
            {
                "id": "biology_containers",
                "text": "Human cells contain organelles such as mitochondria and the nucleus, which store the genetic material of the organism.",
            },
        ],
        "top_k": 5,
        "max_rank_for_true_neighbors": 3,  # true neighbors must appear in top-3
    },
    {
        "anchor_id": "zettelkasten",
        "anchor_text": "Zettelkasten is a note-taking method where each note contains one idea, linked explicitly to related notes by reference.",
        "true_neighbors": [
            {
                "id": "evergreen_notes",
                "text": "Evergreen notes are written to evolve over time, connected to other notes and refined rather than archived.",
            },
            {
                "id": "progressive_summarisation",
                "text": "Progressive summarisation condenses highlights layer by layer: bold, then re-highlight, then summarise.",
            },
        ],
        "homonym_traps": [
            {
                "id": "slip_box_furniture",
                "text": "A filing cabinet or slip box is a piece of furniture used in offices to organise paper documents alphabetically.",
            },
        ],
        "top_k": 5,
        "max_rank_for_true_neighbors": 3,
    },
    {
        "anchor_id": "intermittent_fasting",
        "anchor_text": "Intermittent fasting restricts caloric intake to specific time windows such as 16:8 or 5:2 to improve metabolic health.",
        "true_neighbors": [
            {
                "id": "gut_microbiome",
                "text": "The gut microbiome composition is altered by dietary patterns including meal timing, fiber intake and fasting protocols.",
            },
        ],
        "homonym_traps": [
            {
                "id": "software_fasting",
                "text": "CPU throttling reduces processor speed during low-demand periods to conserve energy and decrease heat generation.",
            },
        ],
        "top_k": 5,
        "max_rank_for_true_neighbors": 3,
    },
]


@pytest.fixture(scope="module")
def embedder():
    from src.utils.embeddings import get_embeddings_client
    return get_embeddings_client()


def _embed(client, text: str) -> list[float]:
    return client.embed_query(text)


def _cosine_distance(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 1.0 - (dot / (na * nb)) if na * nb else 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetrievalRanking:
    """
    Without touching the DB: pure embedding-space ranking tests.

    These run against live Bedrock embeddings but do NOT require a running
    database — they only measure distances in the embedding space.
    This is the diagnostic that reveals if a true pair would be CUT before
    reaching the LLM (distance >= DISTANCE_LINKING_CUTOFF).
    """

    @pytest.mark.parametrize("scenario", RETRIEVAL_SCENARIOS, ids=[s["anchor_id"] for s in RETRIEVAL_SCENARIOS])
    @skip_no_creds
    def test_true_neighbors_rank_above_traps(self, embedder, scenario):
        """
        For each anchor, true neighbors must have LOWER distance (= more similar)
        than homonym traps.  If a homonym trap ranks above the true neighbor, the
        LLM will see the trap with a "High/Moderate similarity" label while the
        true positive gets a "Weak" label or is excluded entirely.
        """
        anchor_id = scenario["anchor_id"]
        anchor_vec = _embed(embedder, scenario["anchor_text"])

        # Embed all candidates
        neighbor_distances = []
        for nb in scenario["true_neighbors"]:
            vec = _embed(embedder, nb["text"])
            dist = _cosine_distance(anchor_vec, vec)
            neighbor_distances.append((nb["id"], dist))

        trap_distances = []
        for trap in scenario["homonym_traps"]:
            vec = _embed(embedder, trap["text"])
            dist = _cosine_distance(anchor_vec, vec)
            trap_distances.append((trap["id"], dist))

        # Print diagnostic table
        print(f"\n  Anchor: [{anchor_id}]")
        print(f"    True neighbors:")
        for nid, d in sorted(neighbor_distances, key=lambda x: x[1]):
            print(f"      {d:.4f}  {nid}")
        print(f"    Homonym traps:")
        for tid, d in sorted(trap_distances, key=lambda x: x[1]):
            print(f"      {d:.4f}  {tid}")

        max_neighbor_dist = max(d for _, d in neighbor_distances)
        min_trap_dist     = min(d for _, d in trap_distances)

        assert max_neighbor_dist < min_trap_dist, (
            f"[{anchor_id}] Ranking inversion: best true neighbor distance "
            f"{max_neighbor_dist:.4f} >= worst trap distance {min_trap_dist:.4f}. "
            f"The embedding model ranks a homonym trap as more similar than the "
            f"true topical neighbor."
        )

    @pytest.mark.parametrize("scenario", RETRIEVAL_SCENARIOS, ids=[s["anchor_id"] for s in RETRIEVAL_SCENARIOS])
    @skip_no_creds
    def test_true_neighbors_within_retrieval_cutoff(self, embedder, scenario):
        """
        True neighbors must have distance < DISTANCE_LINKING_CUTOFF.
        This is the minimum condition for them to reach the LLM at all.
        """
        from src.utils.embeddings import DISTANCE_LINKING_CUTOFF

        anchor_id = scenario["anchor_id"]
        anchor_vec = _embed(embedder, scenario["anchor_text"])

        for nb in scenario["true_neighbors"]:
            vec = _embed(embedder, nb["text"])
            dist = _cosine_distance(anchor_vec, vec)
            print(f"\n  [{anchor_id}] → [{nb['id']}]  distance = {dist:.4f}  cutoff = {DISTANCE_LINKING_CUTOFF}")
            assert dist < DISTANCE_LINKING_CUTOFF, (
                f"[{anchor_id}] Retrieval miss: [{nb['id']}] has distance {dist:.4f} "
                f">= DISTANCE_LINKING_CUTOFF ({DISTANCE_LINKING_CUTOFF}). "
                f"This pair will NEVER reach the LLM.  "
                f"Either raise the cutoff or switch to a better embedding model."
            )

    @skip_no_creds
    def test_retrieval_cutoff_diagnostic(self, embedder):
        """
        Non-asserting diagnostic: prints all pair distances and flags which ones
        would be CUT by the current DISTANCE_LINKING_CUTOFF.
        Run with -s to see the full table — useful for tuning the cutoff.
        """
        from src.utils.embeddings import DISTANCE_LINKING_CUTOFF, similarity_tier

        sep = "─" * 72
        print(f"\n\n  {'═' * 72}")
        print(f"  RETRIEVAL CUTOFF DIAGNOSTIC  (cutoff = {DISTANCE_LINKING_CUTOFF})")
        print(f"  {'═' * 72}")

        for scenario in RETRIEVAL_SCENARIOS:
            anchor_id = scenario["anchor_id"]
            anchor_vec = _embed(embedder, scenario["anchor_text"])
            print(f"\n  Anchor: {anchor_id}")
            print(f"  {sep}")

            all_candidates = (
                [(nb["id"], nb["text"], "TRUE")  for nb in scenario["true_neighbors"]]
                + [(t["id"],  t["text"],  "TRAP")  for t in scenario["homonym_traps"]]
            )

            for cid, ctext, ctype in all_candidates:
                vec = _embed(embedder, ctext)
                dist = _cosine_distance(anchor_vec, vec)
                tier  = similarity_tier(dist)
                cut   = "CUT" if dist >= DISTANCE_LINKING_CUTOFF else "    "
                flag  = "⚠ " if (ctype == "TRUE" and dist >= DISTANCE_LINKING_CUTOFF) else "  "
                print(f"  {flag} {cut}  {dist:.4f}  [{tier:25}]  {ctype}  {cid}")

        print(f"\n  Legend: ⚠  = true positive that will never reach the LLM\n")
