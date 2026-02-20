"""
tests/unit/test_model_comparison.py
════════════════════════════════════════════════════════════════════════════════
EMBEDDING MODEL BENCHMARK — side-by-side comparison

Compares all candidate models on the same gold-standard pair corpus WITHOUT
touching the active model in shared/config/embedding_config.py.

Models under test:
  • amazon.titan-embed-text-v2:0        (1024-dim, eu-west-1)
  • cohere.embed-english-v3             (1024-dim, eu-west-1)
  • cohere.embed-multilingual-v3        (1024-dim, eu-west-1)

Run:
  $env:AWS_PROFILE="aws-presmanes-home"
  pytest tests/unit/test_model_comparison.py -v -s

The individual parametrized tests act as pass/fail gates per model.
`test_comparison_scorecard` prints the full side-by-side table (run with -s).

Cost estimate: ~0.03 USD per full run (3 models × 30 pairs × Bedrock rates).
"""
import math
import os
import pytest
from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings

load_dotenv()

# ── Model registry ─────────────────────────────────────────────────────────────
MODELS = [
    "amazon.titan-embed-text-v2:0",
    "cohere.embed-english-v3",
    "cohere.embed-multilingual-v3",
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - (dot / (na * nb))


def _make_client(model_id: str) -> BedrockEmbeddings:
    """
    Build a BedrockEmbeddings client for the given model.
    Cohere v3 requires input_type; Titan ignores extra kwargs gracefully.
    """
    region = os.getenv("AWS_REGION", "eu-west-1")
    profile = os.getenv("AWS_PROFILE")
    ak = os.getenv("AWS_ACCESS_KEY_ID")
    sk = os.getenv("AWS_SECRET_ACCESS_KEY")

    kwargs: dict = dict(
        model_id=model_id,
        region_name=region,
        credentials_profile_name=profile,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
    )

    # Cohere v3 requires input_type in the request body.
    # search_document is used for both sides since we measure pure geometry,
    # not asymmetric query→doc retrieval.
    if model_id.startswith("cohere.embed"):
        kwargs["model_kwargs"] = {"input_type": "search_document", "truncate": "END"}

    return BedrockEmbeddings(**kwargs)


def _dist(client: BedrockEmbeddings, text_a: str, text_b: str) -> float:
    va = client.embed_query(text_a)
    vb = client.embed_query(text_b)
    return _cosine_distance(va, vb)


# ── Fixture: one client per model, module-scoped ───────────────────────────────
@pytest.fixture(scope="module", params=MODELS)
def model_client(request):
    """Parametrized fixture — runs every test class once per model."""
    return request.param, _make_client(request.param)


# ── Gold-standard corpus (same as test_embedding_space.py) ────────────────────
TRUE_RELATED = [
    (
        "devops_docker_k8s",
        "Docker containers package applications with their dependencies into portable units.",
        "Kubernetes orchestrates containerized workloads across clusters, handling scaling and self-healing.",
        0.95,
    ),
    (
        "pkm_zettelkasten_evergreen",
        "Zettelkasten is a note-taking method where each note contains one idea, linked explicitly to related notes.",
        "Evergreen notes are written to evolve over time, connected to other notes and refined rather than archived.",
        0.90,
    ),
    (
        "devops_cicd_docker",
        "CI/CD pipelines automate the build, test and deploy steps every time new code is committed.",
        "Docker containers provide a consistent runtime environment that makes CI/CD pipelines reproducible.",
        0.95,
    ),
    (
        "pkm_progressive_zettelkasten",
        "Progressive summarisation condenses highlights layer by layer: bold, then re-highlight, then summarise.",
        "Zettelkasten turns reading notes into permanent notes by extracting one atomic idea per card.",
        0.90,
    ),
    (
        "health_fasting_microbiome",
        "Intermittent fasting restricts calorie intake to specific time windows to improve metabolic markers.",
        "The gut microbiome composition is altered by dietary patterns including meal timing and fasting protocols.",
        0.95,
    ),
]

MULTILINGUAL_PAIRS = [
    (
        "flow_en_es",
        "Flow state is a psychological condition of deep focus and effortless performance.",
        "El estado de flujo es una condicion psicologica de concentracion profunda y rendimiento sin esfuerzo.",
        0.55,
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

HOMONYM_TRAPS = [
    (
        "atomic_trap",
        "Atomic habits are small, incremental behaviour changes that compound into remarkable results over time.",
        "Atomic notes contain exactly one idea and are the basic unit of a Zettelkasten knowledge base.",
        0.75,
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
        0.65,
    ),
]

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

# ── Per-model parametrized gates ──────────────────────────────────────────────

class TestRecallByModel:
    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", TRUE_RELATED)
    def test_true_related(self, model_client, pair_id, text_a, text_b, bound):
        model_id, client = model_client
        dist = _dist(client, text_a, text_b)
        print(f"\n  [{model_id}][{pair_id}]  {dist:.4f}  (max {bound})")
        assert dist < bound, f"[{model_id}][{pair_id}] Recall failure: {dist:.4f} >= {bound}"


class TestMultilingualByModel:
    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", MULTILINGUAL_PAIRS)
    def test_multilingual(self, model_client, pair_id, text_a, text_b, bound):
        model_id, client = model_client
        dist = _dist(client, text_a, text_b)
        print(f"\n  [{model_id}][{pair_id}]  {dist:.4f}  (max {bound})")
        assert dist < bound, f"[{model_id}][{pair_id}] Multilingual failure: {dist:.4f} >= {bound}"


class TestPrecisionByModel:
    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", HOMONYM_TRAPS)
    def test_homonym_separation(self, model_client, pair_id, text_a, text_b, bound):
        model_id, client = model_client
        dist = _dist(client, text_a, text_b)
        print(f"\n  [{model_id}][{pair_id}]  {dist:.4f}  (min {bound})")
        assert dist > bound, f"[{model_id}][{pair_id}] Precision failure: {dist:.4f} <= {bound}"


class TestNoiseByModel:
    @pytest.mark.parametrize("pair_id,text_a,text_b,bound", NOISE_PAIRS)
    def test_unrelated_distant(self, model_client, pair_id, text_a, text_b, bound):
        model_id, client = model_client
        dist = _dist(client, text_a, text_b)
        print(f"\n  [{model_id}][{pair_id}]  {dist:.4f}  (min {bound})")
        assert dist > bound, f"[{model_id}][{pair_id}] Noise collision: {dist:.4f} <= {bound}"


# ── Side-by-side scorecard ─────────────────────────────────────────────────────

def test_comparison_scorecard():
    """
    Runs all models sequentially and prints a side-by-side comparison table.
    Does NOT assert — diagnostic only.  Run with -s to see output.
    """
    all_pairs = (
        [("recall",      id_, a, b, bnd, "below") for id_, a, b, bnd in TRUE_RELATED]
        + [("multi",     id_, a, b, bnd, "below") for id_, a, b, bnd in MULTILINGUAL_PAIRS]
        + [("precision", id_, a, b, bnd, "above") for id_, a, b, bnd in HOMONYM_TRAPS]
        + [("noise",     id_, a, b, bnd, "above") for id_, a, b, bnd in NOISE_PAIRS]
    )

    # Collect results per model
    model_results: dict[str, dict] = {}
    for model_id in MODELS:
        client = _make_client(model_id)
        cats: dict[str, dict] = {}
        pair_details: list = []
        for cat, pair_id, ta, tb, bnd, direction in all_pairs:
            dist = _dist(client, ta, tb)
            passed = dist < bnd if direction == "below" else dist > bnd
            cats.setdefault(cat, {"pass": 0, "fail": 0})
            cats[cat]["pass" if passed else "fail"] += 1
            pair_details.append((cat, pair_id, dist, bnd, direction, passed))
        model_results[model_id] = {"cats": cats, "pairs": pair_details}

    # Print table
    cats_order = ["recall", "multi", "precision", "noise"]
    cat_totals = {c: len([p for p in all_pairs if p[0] == c]) for c in cats_order}
    sep = "═" * 80

    print(f"\n\n  {sep}")
    print(f"  EMBEDDING MODEL COMPARISON SCORECARD")
    print(f"  {sep}")

    col_w = 26
    header = f"  {'Category':<16}" + "".join(f"{m[-22:]:>{col_w}}" for m in MODELS)
    print(header)
    print(f"  {'─' * (16 + col_w * len(MODELS))}")

    for cat in cats_order:
        row = f"  {cat:<16}"
        for model_id in MODELS:
            r = model_results[model_id]["cats"].get(cat, {"pass": 0, "fail": 0})
            total = cat_totals[cat]
            pct = r["pass"] / total if total else 0.0
            ok = "✓" if r["fail"] == 0 else "✗"
            row += f"{ok} {r['pass']}/{total} ({pct:>4.0%}){' ' * (col_w - 14)}"
        print(row)

    print(f"  {'─' * (16 + col_w * len(MODELS))}")
    row = f"  {'TOTAL':<16}"
    for model_id in MODELS:
        cats_data = model_results[model_id]["cats"]
        tp = sum(v["pass"] for v in cats_data.values())
        tf = sum(v["fail"] for v in cats_data.values())
        total = tp + tf
        pct = tp / total if total else 0.0
        ok = "✓" if tf == 0 else "✗"
        row += f"{ok} {tp}/{total} ({pct:>4.0%}){' ' * (col_w - 14)}"
    print(row)
    print(f"  {sep}")

    # Detailed per-pair breakdown
    print(f"\n  Detailed distances per pair:")
    print(f"  {'Pair':<28}" + "".join(f"{'dist':>10}" for _ in MODELS) + f"  bound  dir")
    print(f"  {'─' * (28 + 10 * len(MODELS) + 14)}")

    pair_ids = [(p[0], p[1]) for p in all_pairs]
    for cat, pair_id, *_ in all_pairs:
        row_dists = []
        markers = []
        for model_id in MODELS:
            entry = next(
                (e for e in model_results[model_id]["pairs"] if e[0] == cat and e[1] == pair_id),
                None,
            )
            if entry:
                dist, bnd, direction, passed = entry[2], entry[3], entry[4], entry[5]
                row_dists.append(f"{dist:>10.4f}")
                markers.append("✓" if passed else "✗")
            else:
                row_dists.append(f"{'N/A':>10}")
                markers.append("?")
        sign = "<" if _ [3] == "below" else ">"
        # Use bound from all_pairs entry
        bnd_val = next(p[4] for p in all_pairs if p[0] == cat and p[1] == pair_id)
        mark_str = " ".join(markers)
        print(f"  {cat}/{pair_id:<24}" + "".join(row_dists) + f"  {sign}{bnd_val}  {mark_str}")

    print()
