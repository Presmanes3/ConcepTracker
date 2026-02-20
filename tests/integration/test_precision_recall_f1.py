"""
tests/integration/test_precision_recall_f1.py
═══════════════════════════════════════════════════════════════════════════════
CAPA 3 — Gold Standard F1 (con DB, con LLM, con ground truth)

Qué mide: F1 real del pipeline completo.
  • Precision = TP / (TP + FP)  — ¿cuántos links creados son correctos?
  • Recall    = TP / (TP + FN)  — ¿cuántos links correctos se crearon?
  • F1        = 2 * P * R / (P + R)

Gold corpus: 12 notas en 3 clusters temáticos.
Ground truth: 9 pares que DEBEN estar linkados + 5 trampas que NO deben linkarse.

Este test debe pasar con F1 ≥ 0.65 con Titan v2 y con F1 ≥ 0.80 después
de migrar a Cohere Embed v3 o tras otras mejoras al pipeline.

Cómo usarlo como comparación de modelos:
  1. Corre con Titan v2   → guarda el F1 (actualmente ~0.45-0.60)
  2. Cambia EMBEDDING_MODEL_ID en shared/config/embedding_config.py a Cohere
  3. Re-indexa los embeddings: ct reset-db && ingest all notes
  4. Corre de nuevo → el F1 debe subir

Run:
    $env:AWS_PROFILE="aws-presmanes-home"
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_precision_recall_f1.py -v -s
"""
from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from typing import Optional

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
# GOLD CORPUS
# 12 notas en 3 clusters + 3 trampas homónimas
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GoldNote:
    label: str
    cluster: str   # "pkm" | "devops" | "health" | "trap"
    content: str


GOLD_CORPUS: list[GoldNote] = [

    # ── Cluster 1: PKM ────────────────────────────────────────────────────────
    GoldNote(
        label="zettelkasten",
        cluster="pkm",
        content=(
            "Zettelkasten is a personal knowledge management system where every note "
            "contains exactly one idea and is linked explicitly to related notes using "
            "unique identifiers. The network of links creates emergent insights that "
            "no single note could contain alone. Niklas Luhmann used it to write "
            "70 books and 400 academic articles."
        ),
    ),
    GoldNote(
        label="evergreen_notes",
        cluster="pkm",
        content=(
            "Evergreen notes are written to evolve over time. Unlike fleeting notes, "
            "they are written in full sentences, refined through use, and connected to "
            "other notes. Andy Matuschak argues that most notes are 'write-once archives' "
            "and that evergreen notes are a practice to build a 'growing' knowledge base."
        ),
    ),
    GoldNote(
        label="progressive_summarisation",
        cluster="pkm",
        content=(
            "Progressive summarisation is a method by Tiago Forte where you layer "
            "highlights: first bold the most important passages, then highlight the "
            "bold, then write a summary. The goal is to create notes that require "
            "minimal effort to re-read in the future."
        ),
    ),
    GoldNote(
        label="atomic_notes",
        cluster="pkm",
        content=(
            "Atomic notes are the basic unit of a Zettelkasten. Each note captures "
            "exactly one idea in a way that can be understood without context. This "
            "atomicity makes notes reusable and combinable in unexpected ways, enabling "
            "non-linear thinking through explicit links."
        ),
    ),

    # ── Cluster 2: DevOps ─────────────────────────────────────────────────────
    GoldNote(
        label="docker",
        cluster="devops",
        content=(
            "Docker packages an application and all its dependencies inside a container. "
            "Containers run identically on any machine with Docker installed, eliminating "
            "the 'works on my machine' problem. Images are built from a Dockerfile and "
            "can be pushed to a registry for distribution."
        ),
    ),
    GoldNote(
        label="kubernetes",
        cluster="devops",
        content=(
            "Kubernetes is a container orchestration platform that automates deployment, "
            "scaling and self-healing of containerised applications. A cluster consists "
            "of a control plane and worker nodes. Pods are the smallest deployable unit "
            "and typically contain one container."
        ),
    ),
    GoldNote(
        label="ci_cd",
        cluster="devops",
        content=(
            "CI/CD stands for Continuous Integration and Continuous Delivery. A CI/CD "
            "pipeline automatically builds, tests and deploys code every time a developer "
            "commits to version control. This practice reduces integration conflicts and "
            "makes releases predictable and low-risk."
        ),
    ),
    GoldNote(
        label="infrastructure_as_code",
        cluster="devops",
        content=(
            "Infrastructure as Code (IaC) means managing servers, networks and cloud "
            "resources through machine-readable configuration files instead of manual "
            "processes. Tools like Terraform and Pulumi allow version control, "
            "review and reproducibility of infrastructure changes."
        ),
    ),

    # ── Cluster 3: Nutrition / Health ─────────────────────────────────────────
    GoldNote(
        label="intermittent_fasting",
        cluster="health",
        content=(
            "Intermittent fasting (IF) is a nutritional strategy that cycles between "
            "periods of eating and fasting. Common protocols include 16:8 (16 hours "
            "fasting, 8 hours eating) and 5:2 (two non-consecutive days of very low "
            "calorie intake per week)."
        ),
    ),
    GoldNote(
        label="gut_microbiome",
        cluster="health",
        content=(
            "The gut microbiome is the community of trillions of microorganisms living "
            "in the human digestive tract. Its composition influences immunity, mental "
            "health and metabolic function. It is shaped by diet, especially fibre intake, "
            "meal timing, and whether the person practices fasting."
        ),
    ),
    GoldNote(
        label="ketogenic_diet",
        cluster="health",
        content=(
            "The ketogenic diet is a high-fat, very-low-carbohydrate eating pattern "
            "that puts the body into a metabolic state called ketosis. In ketosis, "
            "the liver converts fat into ketone bodies, which the brain and muscles "
            "use as fuel instead of glucose."
        ),
    ),
    GoldNote(
        label="insulin_resistance",
        cluster="health",
        content=(
            "Insulin resistance occurs when cells in the body stop responding normally "
            "to insulin, forcing the pancreas to produce more. It is a precursor to "
            "type 2 diabetes and is associated with visceral fat accumulation, sleep "
            "deprivation and highly processed diets."
        ),
    ),

    # ── Homonym Traps (must NOT link to the clusters above) ───────────────────
    GoldNote(
        label="atomic_habits",        # shares 'atomic' with atomic_notes but different domain
        cluster="trap",
        content=(
            "Atomic habits are small one-percent improvements that compound over time "
            "into remarkable behaviour change. James Clear argues that the system of "
            "habits matters more than goal-setting, and that identity-based habits "
            "(who you want to become) are more durable than outcome-based ones."
        ),
    ),
    GoldNote(
        label="kubernetes_networking",  # within devops but a different, narrow topic
        cluster="devops",               # belongs to devops cluster — true link to kubernetes
        content=(
            "Kubernetes networking assigns each Pod its own IP address and uses "
            "Services to expose stable DNS names and IPs. NetworkPolicies restrict "
            "traffic between Pods. Ingress controllers manage external HTTP/S access "
            "to services running in the cluster."
        ),
    ),
    GoldNote(
        label="flow_programming",       # shares 'flow' with nothing — pure distractor
        cluster="trap",
        content=(
            "Flow-based programming (FBP) is a paradigm where applications are defined "
            "as networks of processes communicating over connections by passing data "
            "packets called Information Packets. Each process runs independently, "
            "making the system highly parallel and composable."
        ),
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# GROUND TRUTH
#
# Format: (label_a, label_b, should_link, category)
#   should_link = True  → this link MUST be created (recall)
#   should_link = False → this link MUST NOT be created (precision)
#
# These are the EXPECTED links after all 15 notes are ingested.
# They are directional — (a, b) is the same as (b, a) for evaluation.
# ═══════════════════════════════════════════════════════════════════════════════

GROUND_TRUTH: list[tuple[str, str, bool, str]] = [

    # ── Must link (TP for recall) ─────────────────────────────────────────────
    # PKM cluster
    ("zettelkasten",           "evergreen_notes",          True,  "pkm_internal"),
    ("zettelkasten",           "atomic_notes",             True,  "pkm_internal"),
    ("evergreen_notes",        "atomic_notes",             True,  "pkm_internal"),
    ("zettelkasten",           "progressive_summarisation",True,  "pkm_internal"),

    # DevOps cluster
    ("docker",                 "kubernetes",               True,  "devops_internal"),
    ("docker",                 "ci_cd",                    True,  "devops_internal"),
    ("kubernetes",             "ci_cd",                    True,  "devops_internal"),
    ("kubernetes",             "kubernetes_networking",    True,  "devops_internal"),
    ("docker",                 "infrastructure_as_code",   True,  "devops_internal"),

    # Health cluster
    ("intermittent_fasting",   "gut_microbiome",           True,  "health_internal"),
    ("intermittent_fasting",   "ketogenic_diet",           True,  "health_internal"),
    ("intermittent_fasting",   "insulin_resistance",       True,  "health_internal"),
    ("ketogenic_diet",         "insulin_resistance",       True,  "health_internal"),

    # ── Must NOT link (FP prevention) ────────────────────────────────────────
    ("atomic_notes",           "atomic_habits",            False, "homonym_trap"),
    ("docker",                 "intermittent_fasting",     False, "cross_cluster"),
    ("zettelkasten",           "kubernetes",               False, "cross_cluster"),
    ("gut_microbiome",         "ci_cd",                    False, "cross_cluster"),
    ("flow_programming",       "zettelkasten",             False, "noise_trap"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS (reuse the ingest helper from the battery test)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IngestResult:
    label: str
    cluster: str
    note_id: Optional[int]
    action: str
    links_created: list[dict] = field(default_factory=list)


def _ingest(note: GoldNote) -> IngestResult:
    from src.workflows.ingest_workflow import ingest_graph
    from shared.schemas.workflow.ingest import IngestState

    state = IngestState(content=note.content)
    raw = ingest_graph.invoke(state)

    def _get(key, default=None):
        if isinstance(raw, dict):
            return raw.get(key, default)
        return getattr(raw, key, default)

    raw_links = _get("links", [])
    links: list[dict] = []
    for lnk in raw_links:
        if isinstance(lnk, dict):
            links.append(lnk)
        else:
            links.append({
                "target_id":     lnk.target_id,
                "relation_type": lnk.relation_type,
                "reason":        getattr(lnk, "reason", ""),
            })

    return IngestResult(
        label=note.label,
        cluster=note.cluster,
        note_id=_get("note_id"),
        action=_get("action", "CREATE"),
        links_created=links,
    )


def _cleanup(results: list[IngestResult]) -> None:
    from src.repository.link_repository import link_repository
    from src.repository.note_repository import note_repository

    ids = [r.note_id for r in results if r.note_id is not None]
    for nid in ids:
        link_repository.delete_links_for_note(nid)
    for nid in ids:
        note_repository.delete_note(nid)


def _build_link_set(results: list[IngestResult]) -> set[tuple[str, str]]:
    """Return set of (label_a, label_b) pairs (direction-normalised, sorted)."""
    label_map: dict[int, str] = {r.note_id: r.label for r in results if r.note_id}
    links: set[tuple[str, str]] = set()
    for r in results:
        if not r.note_id:
            continue
        for lnk in r.links_created:
            tid = lnk.get("target_id")
            if tid and tid in label_map:
                pair = tuple(sorted([r.label, label_map[tid]]))
                links.add(pair)
    return links


def _compute_metrics(
    actual_links: set[tuple[str, str]],
    ground_truth: list[tuple[str, str, bool, str]],
) -> dict:
    """Compute TP/FP/FN/TN and P/R/F1 against the gold standard."""
    should_link   = {tuple(sorted([a, b])) for a, b, link, _ in ground_truth if link}
    must_not_link = {tuple(sorted([a, b])) for a, b, link, _ in ground_truth if not link}

    tp = len(actual_links & should_link)
    fp = len(actual_links & must_not_link)
    fn = len(should_link - actual_links)
    tn = len(must_not_link - actual_links)

    precision   = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall      = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1          = (2 * precision * recall / (precision + recall)
                   if (precision + recall) > 0 else 0.0)

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CORE TEST
# ═══════════════════════════════════════════════════════════════════════════════

@skip_no_creds
def test_f1_gold_standard():
    """
    Full-pipeline precision/recall/F1 against the gold standard corpus.

    Inserts 15 notes one by one (simulating real usage), then evaluates
    all links created against GROUND_TRUTH.

    Minimum thresholds (Titan v2, DISTANCE_LINKING_CUTOFF=0.95):
      - Precision ≥ 0.70  (must not hallucinate links)
      - Recall    ≥ 0.40  (must find at least the obvious intra-cluster links)
      - F1        ≥ 0.50

    After switching to Cohere Embed v3, expected targets:
      - Precision ≥ 0.80
      - Recall    ≥ 0.65
      - F1        ≥ 0.72
    """
    MIN_PRECISION = 0.70
    MIN_RECALL    = 0.40
    MIN_F1        = 0.50

    results: list[IngestResult] = []

    try:
        # ── Ingest all notes ──────────────────────────────────────────────────
        for note in GOLD_CORPUS:
            res = _ingest(note)
            results.append(res)
            # Brief progress line (visible with pytest -s)
            print(f"  [{note.label}]  id={res.note_id}  action={res.action}  "
                  f"links={len(res.links_created)}")

        # ── Build actual links ────────────────────────────────────────────────
        actual = _build_link_set(results)
        metrics = _compute_metrics(actual, GROUND_TRUTH)

        # ── Print scorecard ───────────────────────────────────────────────────
        sep = "═" * 72
        print(f"\n\n  {sep}")
        print(f"  GOLD STANDARD F1 SCORECARD")
        print(f"  {sep}")
        print(f"  TP (correct links created)   : {metrics['tp']}")
        print(f"  FP (wrong links created)     : {metrics['fp']}")
        print(f"  FN (correct links MISSED)    : {metrics['fn']}")
        print(f"  TN (wrong links correctly absent): {metrics['tn']}")
        print(f"  {'─' * 48}")
        print(f"  Precision : {metrics['precision']:.2%}  (min {MIN_PRECISION:.0%})")
        print(f"  Recall    : {metrics['recall']:.2%}  (min {MIN_RECALL:.0%})")
        print(f"  F1        : {metrics['f1']:.2%}  (min {MIN_F1:.0%})")
        print(f"  {sep}")

        # ── Breakdown by category ─────────────────────────────────────────────
        print(f"\n  Detailed ground truth evaluation:")

        label_map: dict[str, int] = {r.label: r.note_id for r in results if r.note_id}
        from shared.config.embedding_config import EMBEDDING_MODEL_ID
        print(f"  Model: {EMBEDDING_MODEL_ID}\n")

        for a_label, b_label, expected, category in GROUND_TRUTH:
            pair = tuple(sorted([a_label, b_label]))
            linked = pair in actual
            correct = linked == expected
            expected_str = "LINK  " if expected else "NO LINK"
            actual_str   = "LINK  " if linked  else "NO LINK"
            marker = "✓" if correct else "✗"
            print(f"    {marker}  [{category:20}]  {a_label:30} ↔ {b_label:30}  "
                  f"expected={expected_str}  actual={actual_str}")

        print()

        # ── Assertions ────────────────────────────────────────────────────────
        assert metrics["precision"] >= MIN_PRECISION, (
            f"Precision {metrics['precision']:.2%} below minimum {MIN_PRECISION:.0%}. "
            f"FP links: {[p for p in actual if p in {tuple(sorted([a,b])) for a,b,lnk,_ in GROUND_TRUTH if not lnk}]}"
        )
        assert metrics["recall"] >= MIN_RECALL, (
            f"Recall {metrics['recall']:.2%} below minimum {MIN_RECALL:.0%}. "
            f"Missed links: {[p for p in {tuple(sorted([a,b])) for a,b,lnk,_ in GROUND_TRUTH if lnk} if p not in actual]}"
        )
        assert metrics["f1"] >= MIN_F1, (
            f"F1 {metrics['f1']:.2%} below minimum {MIN_F1:.0%}."
        )

    finally:
        _cleanup(results)


@skip_no_creds
def test_precision_only_no_false_positives():
    """
    Faster precision check: insert ONLY the homonym trap pairs and assert
    that no false positive links are created between any of them.
    Much cheaper (4 notes, ~2-3 Bedrock calls) — useful for pre-commit.
    """
    trap_notes = [n for n in GOLD_CORPUS if n.cluster == "trap"]
    # Also include their homonym counterparts to make the trap meaningful
    homonym_counterparts = {"atomic_habits": "atomic_notes", "flow_programming": "zettelkasten"}
    counterpart_labels = set(homonym_counterparts.values())
    extra = [n for n in GOLD_CORPUS if n.label in counterpart_labels]

    corpus = trap_notes + extra
    results: list[IngestResult] = []

    try:
        for note in corpus:
            res = _ingest(note)
            results.append(res)

        actual = _build_link_set(results)
        trap_labels = {n.label for n in trap_notes}

        fp_pairs = [
            pair for pair in actual
            if any(label in trap_labels for label in pair)
            and all(  # both notes exist in THIS run
                label in {r.label for r in results}
                for label in pair
            )
        ]

        print(f"\n  Trap corpus links: {actual}")
        print(f"  False positives  : {fp_pairs}")

        assert len(fp_pairs) == 0, (
            f"Homonym traps produced false positive links: {fp_pairs}. "
            f"The embedding model or LLM cannot distinguish different uses of the same word."
        )

    finally:
        _cleanup(results)
