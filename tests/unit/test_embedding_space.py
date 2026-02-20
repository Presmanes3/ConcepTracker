"""
tests/unit/test_embedding_space.py
═══════════════════════════════════════════════════════════════════════════════
CAPA 1 — Geometría del embedding (sin DB, sin LLM generativo)

Qué mide: ¿el modelo de embedding separa correctamente el espacio semántico?
  • Falso positivo en el origen: ¿pares HOMÓNIMOS están suficientemente lejos?
  • Falso negativo en el origen: ¿pares RELACIONADOS están suficientemente cerca?
  • Alienación multilingüe: ¿EN y ES del mismo concepto están cerca?

Por qué importa: si el modelo falla aquí, ninguna mejora en el LLM o el pipeline
puede compensarlo. Éste es el ORACLE para elegir entre Titan v2 y Cohere v3.

Modo comparación:
  pytest tests/unit/test_embedding_space.py -v --tb=short
  # Para Cohere v3: cambiar ACTIVE_MODEL en shared/config/embedding_config.py
  # o pasar --model=cohere al ejecutar el test (ver conftest.py local abajo)

Coste estimado (Titan v2, eu-west-1): ~0.01 USD por ejecución completa (30 pares).
"""
import math
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance in [0, 2]. Equivalent to pgvector <=> operator."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - (dot / (na * nb))


def _embed(client, text: str) -> list[float]:
    return client.embed_query(text)


@pytest.fixture(scope="module")
def embedder():
    """Returns embeddings client.  Module-scoped: one init for all tests."""
    from src.utils.embeddings import get_embeddings_client
    return get_embeddings_client()


# ═══════════════════════════════════════════════════════════════════════════════
# GOLD STANDARD PAIRS
# Format: (id, text_a, text_b, expected_relation, distance_bound, assertion)
#   assertion = "below" → distance MUST be < bound (true positives, recall)
#   assertion = "above" → distance MUST be > bound (false positive traps, precision)
# ═══════════════════════════════════════════════════════════════════════════════

# ── True Related Pairs (recall — must be BELOW cutoff to reach the LLM) ───────
TRUE_RELATED = [
    (
        "same_domain_devops",
        "Docker containers package applications with their dependencies into portable units that run consistently across environments.",
        "Kubernetes orchestrates containerized workloads across clusters, handling scaling, self-healing and rolling deployments.",
        0.95,  # must be closer than the cutoff
    ),
    (
        "same_domain_pkm",
        "Zettelkasten is a note-taking method where each note contains one idea, linked explicitly to related notes by reference.",
        "Evergreen notes are written to evolve over time, connected to other notes and refined rather than archived.",
        0.90,
    ),
    (
        "cross_domain_related",
        "CI/CD pipelines automate the build, test and deploy steps every time new code is committed.",
        "Docker containers provide a consistent runtime environment that makes CI/CD pipelines reproducible.",
        0.95,
    ),
    (
        "pkm_reading_method",
        "Progressive summarisation condenses highlights layer by layer: bold, then re-highlight, then summarise.",
        "Zettelkasten turns reading notes into permanent notes by extracting one atomic idea per card.",
        0.90,
    ),
    (
        "health_related",
        "Intermittent fasting restricts calorie intake to specific time windows to improve metabolic markers.",
        "The gut microbiome composition is altered by dietary patterns including meal timing and fasting protocols.",
        0.95,
    ),
]

# ── Multilingual Pairs (EN ↔ ES — same concept, different language) ────────────
MULTILINGUAL_PAIRS = [
    (
        "flow_en_es",
        "Flow state is a psychological condition of deep focus and effortless performance described by Csikszentmihalyi.",
        "El estado de flujo es una condicion psicologica de concentracion profunda y rendimiento sin esfuerzo estudiada por Csikszentmihalyi.",
        0.55,  # same concept in two languages: should be VERY close
    ),
    (
        "zettelkasten_en_es",
        "Zettelkasten is a networked note-taking system where atomic ideas are connected by explicit links.",
        "Zettelkasten es un sistema de notas en red donde las ideas atomicas se conectan mediante enlaces explicitos.",
        0.30,
    ),
    (
        "docker_en_es",
        "Docker packages an application and its dependencies into a container that runs identically everywhere.",
        "Docker empaqueta una aplicacion y sus dependencias en un contenedor que se ejecuta igual en cualquier entorno.",
        0.30,
    ),
]

# ── Homonym Traps (precision — must be ABOVE threshold to not cause false positives) ──
HOMONYM_TRAPS = [
    (
        "atomic_trap",
        "Atomic habits are small, incremental behaviour changes that compound into remarkable results over time.",
        "Atomic notes contain exactly one idea and are the basic unit of a Zettelkasten knowledge base.",
        0.75,  # must be FARTHER than Moderate tier to avoid being sent to LLM as a strong signal
    ),
    (
        "flow_trap",
        "Flow state is a psychological condition of effortless concentration and peak performance.",
        "Flow-based programming models applications as networks of processes exchanging data over connections.",
        0.80,
    ),
    (
        "containers_trap",
        "Docker containers are lightweight, portable runtime environments for software applications.",
        "The human body contains specialised storage containers for fat, glycogen and water regulation.",
        0.90,
    ),
    (
        "network_trap",
        "A neural network is a machine learning architecture inspired by biological neurons.",
        "A computer network connects devices to share resources and communicate over protocols like TCP/IP.",
        0.80,
    ),
    (
        "graph_trap",
        "Graph theory studies networks of vertices connected by edges and their mathematical properties.",
        "A graph database stores data as nodes and relationships, optimised for traversal queries.",
        # This one is borderline: graph DB IS related to graph theory. We set a lenient bound.
        0.65,  # only assert farther than High, not farther than Moderate
    ),
]

# ── Pure Noise Pairs (completely unrelated) ────────────────────────────────────
NOISE_PAIRS = [
    (
        "noise_1",
        "Bread sourdough fermentation relies on wild yeast and lactic acid bacteria for leavening.",
        "Kubernetes orchestrates containerised workloads across clusters, handling scaling and deployments.",
        0.90,
    ),
    (
        "noise_2",
        "Italian Renaissance painting used chiaroscuro to model three-dimensional form with light and shadow.",
        "Intermittent fasting restricts caloric intake to specific time windows to improve metabolic health.",
        0.90,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecall:
    """True related pairs must fall BELOW the retrieval cutoff."""

    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", TRUE_RELATED)
    def test_true_related_within_cutoff(self, embedder, pair_id, text_a, text_b, bound):
        """
        Distance between truly related notes must be < bound.
        Failure here means the embedding model will cut this pair BEFORE the LLM.
        """
        vec_a = _embed(embedder, text_a)
        vec_b = _embed(embedder, text_b)
        dist = _cosine_distance(vec_a, vec_b)
        print(f"\n  [{pair_id}]  distance = {dist:.4f}  (max allowed: {bound})")
        assert dist < bound, (
            f"[{pair_id}] Recall failure: distance {dist:.4f} >= {bound}. "
            f"This pair will never reach the LLM (retrieval cutoff)."
        )


class TestMultilingual:
    """EN/ES pairs of the same concept must be close in embedding space."""

    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", MULTILINGUAL_PAIRS)
    def test_multilingual_alignment(self, embedder, pair_id, text_a, text_b, bound):
        """
        EN and ES versions of the same concept must be close.
        Failure here means the model treats the same idea as unrelated based on language alone.
        """
        vec_a = _embed(embedder, text_a)
        vec_b = _embed(embedder, text_b)
        dist = _cosine_distance(vec_a, vec_b)
        print(f"\n  [{pair_id}]  distance = {dist:.4f}  (max allowed: {bound})")
        assert dist < bound, (
            f"[{pair_id}] Multilingual alignment failure: distance {dist:.4f} >= {bound}. "
            f"Model does not align EN/ES properly."
        )


class TestPrecision:
    """Homonym traps must fall ABOVE a safe threshold."""

    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", HOMONYM_TRAPS)
    def test_homonym_separation(self, embedder, pair_id, text_a, text_b, bound):
        """
        Homonym pairs must have distance > bound to avoid false positives.
        Failure here means the model cannot distinguish different uses of the same word.
        Cohere v3 should pass more of these than Titan v2.
        """
        vec_a = _embed(embedder, text_a)
        vec_b = _embed(embedder, text_b)
        dist = _cosine_distance(vec_a, vec_b)
        print(f"\n  [{pair_id}]  distance = {dist:.4f}  (min required: {bound})")
        assert dist > bound, (
            f"[{pair_id}] Precision failure: distance {dist:.4f} <= {bound}. "
            f"Homonym pair is too close — embedding model conflates different meanings."
        )


class TestNoise:
    """Completely unrelated notes must be far — sanity check."""

    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", NOISE_PAIRS)
    def test_unrelated_are_distant(self, embedder, pair_id, text_a, text_b, bound):
        vec_a = _embed(embedder, text_a)
        vec_b = _embed(embedder, text_b)
        dist = _cosine_distance(vec_a, vec_b)
        print(f"\n  [{pair_id}]  distance = {dist:.4f}  (min required: {bound})")
        assert dist > bound, (
            f"[{pair_id}] Noise collision: unrelated notes have distance {dist:.4f} <= {bound}."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SCORECARD (run as standalone to compare models)
# python -m pytest tests/unit/test_embedding_space.py -v -s
# ═══════════════════════════════════════════════════════════════════════════════

def test_scorecard_summary(embedder):
    """
    Computes and prints a full scorecard across all pair categories.
    Does NOT assert — it's a diagnostic.  Run with -s to see output.
    """
    all_pairs = (
        [("recall",      id_, a, b, bnd, "below") for id_, a, b, bnd in TRUE_RELATED]
        + [("multilingual", id_, a, b, bnd, "below") for id_, a, b, bnd in MULTILINGUAL_PAIRS]
        + [("precision",  id_, a, b, bnd, "above") for id_, a, b, bnd in HOMONYM_TRAPS]
        + [("noise",     id_, a, b, bnd, "above") for id_, a, b, bnd in NOISE_PAIRS]
    )

    results: dict[str, dict] = {}
    for category, pair_id, text_a, text_b, bound, direction in all_pairs:
        vec_a = _embed(embedder, text_a)
        vec_b = _embed(embedder, text_b)
        dist = _cosine_distance(vec_a, vec_b)
        passed = dist < bound if direction == "below" else dist > bound
        results.setdefault(category, {"pass": 0, "fail": 0, "pairs": []})
        results[category]["pass" if passed else "fail"] += 1
        results[category]["pairs"].append((pair_id, dist, bound, direction, passed))

    categories_order = ["recall", "multilingual", "precision", "noise"]
    sep = "═" * 72
    print(f"\n\n  {sep}")

    from shared.config.embedding_config import EMBEDDING_MODEL_ID
    print(f"  EMBEDDING SPACE SCORECARD  —  {EMBEDDING_MODEL_ID}")
    print(f"  {sep}")
    print(f"  {'Category':<16} {'Pass':>6} {'Fail':>6} {'Score':>8}")
    print(f"  {'─' * 48}")

    total_pass = total_fail = 0
    for cat in categories_order:
        r = results.get(cat, {"pass": 0, "fail": 0, "pairs": []})
        total = r["pass"] + r["fail"]
        score = r["pass"] / total if total else 0.0
        marker = "✓" if r["fail"] == 0 else "✗"
        print(f"  {marker} {cat:<14} {r['pass']:>6} {r['fail']:>6}  {score:>7.0%}")
        total_pass += r["pass"]
        total_fail += r["fail"]

    grand_total = total_pass + total_fail
    grand_score = total_pass / grand_total if grand_total else 0.0
    print(f"  {'─' * 48}")
    print(f"  {'TOTAL':<16} {total_pass:>6} {total_fail:>6}  {grand_score:>7.0%}")
    print(f"  {sep}\n")
    print(f"  Detailed distances:")
    for cat in categories_order:
        for pair_id, dist, bound, direction, passed in results[cat]["pairs"]:
            sign = "<" if direction == "below" else ">"
            marker = "✓" if passed else "✗"
            print(f"    {marker}  [{cat}/{pair_id}]  {dist:.4f}  (must be {sign} {bound})")
    print()
