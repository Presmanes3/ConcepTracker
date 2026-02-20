"""
test_bidirectional_linker.py
─────────────────────────────
Comparativa entre LinkerAgent (standard) y BidirectionalLinkerAgent (consensus)
sobre los casos que la batería A-D identificó como problemáticos.

Estructura:
  Bloque 1 — Diagnóstico de distancias (no assertions, puro logging)
  Bloque 2 — False positive: atomic_habits ↔ atomic_notes
  Bloque 3 — True positive preservation: zettelkasten ↔ evergreen_notes
  Bloque 4 — Recall comparison: los 9 pares intra-cluster de Strategy B
  Bloque 5 — Precision comparison: los 4 pares trampa de Strategy C

Run:
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_bidirectional_linker.py -v -s -m integration

Run a single block:
    ... -k "test_distance_diagnostics"
    ... -k "test_bidir_drops_atomic_false_positive"
    ... -k "test_bidir_preserves_true_positive"
    ... -k "test_bidir_recall_strategy_b"
    ... -k "test_bidir_precision_strategy_c"
"""

from __future__ import annotations

import os
import textwrap
from typing import Optional
from dataclasses import dataclass

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

# ── Helpers ───────────────────────────────────────────────────────────────────

@dataclass
class NoteRecord:
    """A note saved to DB with its embedding distance to another note."""
    id: int
    label: str
    summary: str
    content: str


def _save_note_with_embedding(content: str, label: str) -> NoteRecord:
    """Save a note to DB through normalizer + embedding (real pipeline step)."""
    from src.agents.normalizer_agent import NormalizerAgent
    from src.services.embedding_service import embedding_service
    from src.repository.note_repository import note_repository
    from shared.schemas.models.note import Note
    from shared.schemas.workflow.ingest import IngestState

    # Normalise
    agent = NormalizerAgent()
    state = IngestState(content=content)
    update = agent.run(state)
    cleaned_content = update.get("content", content)
    summary = update.get("summary", content[:200])

    # Embed
    embedding = embedding_service.get_embedding(cleaned_content)

    # Persist
    note = Note(content=cleaned_content, summary=summary, embedding=embedding, tags="bidir-test")
    saved = note_repository.save_note(note)

    return NoteRecord(
        id=saved.id,
        label=label,
        summary=saved.summary,
        content=saved.content,
    )


def _measure_distance(note_a: NoteRecord, note_b: NoteRecord) -> float:
    """Compute cosine distance between two already-embedded notes."""
    from src.repository.note_repository import note_repository
    from shared.schemas.models.note import Note
    from src.utils.db import get_session

    with get_session() as session:
        na = session.get(Note, note_a.id)
        nb = session.get(Note, note_b.id)
        if na is None or nb is None or na.embedding is None or nb.embedding is None:
            return 1.0
        # pgvector cosine distance
        import numpy as np
        va = np.array(na.embedding)
        vb = np.array(nb.embedding)
        # cosine similarity → distance
        sim = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))
        return round(1.0 - sim, 4)


def _run_standard(note_a: NoteRecord, note_b: NoteRecord, distance: float) -> list[dict]:
    """Run standard LinkerAgent with note_a as candidate for note_b."""
    from src.agents.linker_agent import LinkerAgent
    from shared.schemas.workflow.ingest import IngestState

    state = IngestState(
        content=note_b.content,
        summary=note_b.summary,
        note_id=note_b.id,
        similar_notes=[{
            "id": note_a.id,
            "summary": note_a.summary,
            "distance": distance,
        }],
    )
    result = LinkerAgent().run(state)
    return result.get("links", [])


def _run_bidirectional(note_a: NoteRecord, note_b: NoteRecord, distance: float) -> list[dict]:
    """Run BidirectionalLinkerAgent with note_a as candidate for note_b."""
    from src.agents.bidirectional_linker_agent import BidirectionalLinkerAgent
    from shared.schemas.workflow.ingest import IngestState

    state = IngestState(
        content=note_b.content,
        summary=note_b.summary,
        note_id=note_b.id,
        similar_notes=[{
            "id": note_a.id,
            "summary": note_a.summary,
            "distance": distance,
        }],
    )
    result = BidirectionalLinkerAgent().run(state)
    return result.get("links", [])


def _linked(links: list[dict], target_id: int) -> bool:
    return any(l.get("target_id") == target_id for l in links)


def _cleanup(ids: list[int]) -> None:
    from src.repository.link_repository import link_repository
    from src.repository.note_repository import note_repository
    for nid in ids:
        link_repository.delete_links_for_note(nid)
    for nid in ids:
        note_repository.delete_note(nid)


def _tier(distance: float) -> str:
    from src.utils.embeddings import similarity_tier
    return similarity_tier(distance)


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 1 — DIAGNÓSTICO DE DISTANCIAS
# ─────────────────────────────────────────────────────────────────────────────

DIAGNOSTIC_PAIRS = [
    # (label_a,                 content_a,                label_b,                content_b)
    ("atomic_habits",
     "Atomic Habits by James Clear argues that 1% daily improvements compound into remarkable results. "
     "The habit loop: cue, craving, response, reward. Identity-based habits: say 'I am a runner' not 'I want to run'.",
     "atomic_notes",
     "Atomic notes are the foundational principle of PKM. Each note captures exactly one idea. "
     "Atomicity enables combinatorial linking — a single idea connects to many others without confusion."),
    ("progressive_summarisation",
     "Progressive Summarisation by Tiago Forte highlights passages in layers: bold → highlight → executive summary. "
     "Future retrieval becomes frictionless by investing effort incrementally during initial capture.",
     "zettelkasten",
     "Zettelkasten by Niklas Luhmann: each note captures one idea, connected by explicit bidirectional links. "
     "The value accumulates in the network of connections, not in individual notes."),
    ("kubernetes",
     "Kubernetes (K8s) automates deployment, scaling and management of containerised applications. "
     "Pod (smallest unit), Deployment (desired state), Service (stable endpoint). Scheduler assigns pods to nodes.",
     "docker",
     "Docker packages applications into containers — standardised units including code, runtime, libraries. "
     "Containers share the host OS kernel but run isolated. Dockerfile defines image layers."),
    ("flow_psychology",
     "Flow (Csikszentmihalyi): complete absorption in a challenging activity. Skill-challenge balance. "
     "Loss of time sense, effortless concentration, peak performance and well-being.",
     "flow_programming",
     "Flow-based programming (FBP): applications as networks of black-box processes exchanging data packets. "
     "Each process runs concurrently; coordination through data flow, not shared state. Node-RED is a popular tool."),
]


@skip_no_creds
def test_distance_diagnostics():
    """
    BLOQUE 1 — No assertions, pure measurement.

    Logs the embedding distance and tier for each key pair so we can understand
    which tier the critical cases fall into before running the consensus tests.
    """
    print("\n\n  DISTANCE DIAGNOSTICS")
    print("  " + "═" * 68)

    ids_to_cleanup = []
    try:
        for label_a, content_a, label_b, content_b in DIAGNOSTIC_PAIRS:
            na = _save_note_with_embedding(content_a, label_a)
            nb = _save_note_with_embedding(content_b, label_b)
            ids_to_cleanup.extend([na.id, nb.id])

            dist = _measure_distance(na, nb)
            tier = _tier(dist)
            print(f"\n  {label_a!r:35s} ↔  {label_b!r}")
            print(f"    distance = {dist:.4f}   tier = {tier!r}")
    finally:
        _cleanup(ids_to_cleanup)

    print("\n  " + "═" * 68 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 2 — FALSE POSITIVE: atomic_habits ↔ atomic_notes
# ─────────────────────────────────────────────────────────────────────────────

ATOMIC_HABITS_CONTENT = """\
Atomic Habits by James Clear argues that 1% daily improvements compound into
remarkable results over time. The core framework is the habit loop: cue, craving,
response, reward. Clear introduces identity-based habits: instead of "I want to
run a marathon", say "I am a runner". The Four Laws of Behaviour Change—make it
obvious, attractive, easy and satisfying—provide a systematic approach to
building good habits and breaking bad ones.
"""

ATOMIC_NOTES_CONTENT = """\
Atomic notes are the foundational principle of effective personal knowledge
management. Each note captures exactly one idea: a claim, concept, argument or
question. Atomicity enables combinatorial linking—a single idea can connect to
many other ideas without confusion. Non-atomic notes create retrieval problems
because they are hard to resurface in contexts different from the one in which
they were created.
"""


@skip_no_creds
def test_bidir_drops_atomic_false_positive():
    """
    BLOQUE 2 — False positive prevention.

    Strategy C showed that LinkerAgent links atomic_habits ↔ atomic_notes
    because of surface-level shared vocabulary ("atomic").

    Expectation:
      - LinkerAgent.run()              → creates link   (we accept this is broken)
      - BidirectionalLinkerAgent.run() → drops the link (backward pass rejects it)

    If both agents create the link OR both drop it, the test still logs
    correctly and the assertion describes the actual failure mode.
    """
    ids = []
    try:
        na = _save_note_with_embedding(ATOMIC_HABITS_CONTENT, "atomic_habits")
        nb = _save_note_with_embedding(ATOMIC_NOTES_CONTENT, "atomic_notes")
        ids = [na.id, nb.id]

        dist = _measure_distance(na, nb)
        tier = _tier(dist)

        std_links  = _run_standard(na, nb, dist)
        bidir_links = _run_bidirectional(na, nb, dist)

        std_linked   = _linked(std_links, na.id)
        bidir_linked = _linked(bidir_links, na.id)

        print(f"\n  atomic_habits ↔ atomic_notes")
        print(f"    distance = {dist:.4f}   tier = {tier!r}")
        print(f"    standard_linker    → {'LINK' if std_linked   else 'NO LINK'}")
        print(f"    bidir_linker       → {'LINK' if bidir_linked else 'NO LINK'}")
        if std_linked and not bidir_linked:
            print("    ✅ Bidirectional successfully dropped the false positive.")
        elif not std_linked and not bidir_linked:
            print("    ✅ Both agents correctly rejected the link (may depend on tier).")
        elif std_linked and bidir_linked:
            print("    ⚠️  Both agents created the link. Possible causes:")
            print(f"       • Tier is {tier!r} — backward validation only runs on 'Weak topical connection'.")
            print("       • Both LLM calls were fooled by 'atomic' surface similarity.")
        elif not std_linked and bidir_linked:
            print("    ⚠️  Bidirectional created a link that standard didn't — unexpected.")

    finally:
        _cleanup(ids)

    # Soft assertion: bidirectional should never be WORSE than standard
    assert not (not std_linked and bidir_linked), (
        "Bidirectional created a link that standard linker didn't — regression."
    )


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 3 — TRUE POSITIVE PRESERVATION: zettelkasten ↔ evergreen_notes
# ─────────────────────────────────────────────────────────────────────────────

ZETTELKASTEN_CONTENT = """\
Zettelkasten is a note-taking method developed by sociologist Niklas Luhmann.
Each note captures exactly one idea and is connected to other notes through
explicit bidirectional links. Notes are stored with a unique ID and a set of
keywords. The value accumulates not in individual notes but in the network of
connections between them. Luhmann produced over 90,000 notes and 70 books
using this system.
"""

EVERGREEN_NOTES_CONTENT = """\
Evergreen notes, coined by Andy Matuschak, are notes written for long-term
reuse. Unlike fleeting notes captured in the moment, evergreen notes are revised
over time to remain accurate and generalisable. They are written in your own
words, focused on a single concept, and densely linked to related ideas. The
name comes from the trees that stay green year-round — these notes don't become
obsolete.
"""


@skip_no_creds
def test_bidir_preserves_true_positive():
    """
    BLOQUE 3 — True positive preservation.

    zettelkasten ↔ evergreen_notes are genuinely related (both PKM, atomic notes,
    link-based systems). Both agents should create the link.

    A bidirectional approach would only improve things if its backward pass correctly
    confirms this genuine relationship from both perspectives.
    """
    ids = []
    try:
        na = _save_note_with_embedding(ZETTELKASTEN_CONTENT, "zettelkasten")
        nb = _save_note_with_embedding(EVERGREEN_NOTES_CONTENT, "evergreen_notes")
        ids = [na.id, nb.id]

        dist = _measure_distance(na, nb)
        tier = _tier(dist)

        std_links   = _run_standard(na, nb, dist)
        bidir_links = _run_bidirectional(na, nb, dist)

        std_linked   = _linked(std_links, na.id)
        bidir_linked = _linked(bidir_links, na.id)

        print(f"\n  zettelkasten ↔ evergreen_notes")
        print(f"    distance = {dist:.4f}   tier = {tier!r}")
        print(f"    standard_linker    → {'LINK' if std_linked   else 'NO LINK'}")
        print(f"    bidir_linker       → {'LINK' if bidir_linked else 'NO LINK'}")

    finally:
        _cleanup(ids)

    assert bidir_linked, (
        f"Bidirectional linker dropped a genuine relationship (zettelkasten ↔ evergreen_notes).\n"
        f"  distance={dist:.4f}  tier={tier!r}\n"
        f"  This is a recall regression — the backward pass rejected a true positive.\n"
        f"  Check: does the backward call from zettelkasten's perspective see evergreen_notes?"
    )


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 4 — RECALL COMPARISON: los 9 pares intra-cluster de Strategy B
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_B_NOTE_CONTENTS = {
    "zettelkasten":              ZETTELKASTEN_CONTENT,
    "evergreen_notes":           EVERGREEN_NOTES_CONTENT,
    "progressive_summarisation": """\
        Progressive Summarisation is a note-taking technique by Tiago Forte where
        you highlight the most important passages in layers over multiple review
        sessions. Layer 1: save the source. Layer 2: bold key sentences.
        Layer 3: highlight the boldest. Layer 4: write an executive summary.
        The goal is to make future retrieval frictionless by investing effort
        incrementally rather than all at once during initial capture.
        """,
    "docker": """\
        Docker is an open-source platform that packages applications into
        containers—standardised units that include the application code, runtime,
        system libraries and settings. Containers share the host OS kernel but
        run in isolated user-space processes. A Dockerfile defines the image
        layers; `docker build` creates the image; `docker run` starts a container.
        """,
    "kubernetes": """\
        Kubernetes (K8s) is an open-source container orchestration system that
        automates deployment, scaling and management of containerised applications.
        Its control plane manages a cluster of worker nodes. Core abstractions:
        Pod (smallest deployable unit), Deployment (desired state), Service
        (stable network endpoint). The scheduler assigns pods to nodes based on
        resource availability.
        """,
    "ci_cd": """\
        Continuous Integration (CI) and Continuous Delivery (CD) are practices
        that automate the software delivery pipeline. CI: developers merge code
        frequently; automated tests run on every commit to detect regressions
        early. CD: every passing build is kept in a deployable state; deployment
        to production is automated or one-click. Tools: GitHub Actions, GitLab CI.
        """,
    "dieta_mediterranea": """\
        La dieta mediterránea está basada en el consumo abundante de frutas,
        verduras, legumbres, cereales integrales, aceite de oliva virgen extra
        y pescado. Múltiples estudios la asocian con reducción del riesgo
        cardiovascular y mayor longevidad. El aceite de oliva es su principal
        grasa, rico en ácidos grasos monoinsaturados.
        """,
    "ayuno_intermitente": """\
        El ayuno intermitente alterna periodos de alimentación y ayuno. El protocolo
        16:8 restringe la ingesta a 8 horas diarias. El ayuno activa la autofagia,
        mejora la sensibilidad a la insulina y puede promover la pérdida de grasa
        sin pérdida muscular si se mantiene la ingesta proteica adecuada.
        """,
    "microbioma": """\
        El microbioma intestinal es el conjunto de billones de microorganismos del
        tracto digestivo. Una microbiota diversa se asocia con mejor metabolismo e
        inmunidad. Los prebióticos (fibra) alimentan las bacterias beneficiosas.
        La dieta es el principal modulador: una dieta rica en fibra vegetal diversa
        aumenta la diversidad microbiana en semanas.
        """,
}

STRATEGY_B_INTRA_PAIRS = [
    ("zettelkasten",         "evergreen_notes"),
    ("zettelkasten",         "progressive_summarisation"),
    ("evergreen_notes",      "progressive_summarisation"),
    ("docker",               "kubernetes"),
    ("docker",               "ci_cd"),
    ("kubernetes",           "ci_cd"),
    ("dieta_mediterranea",   "ayuno_intermitente"),
    ("dieta_mediterranea",   "microbioma"),
    ("ayuno_intermitente",   "microbioma"),
]


@skip_no_creds
def test_bidir_recall_strategy_b():
    """
    BLOQUE 4 — Recall comparison on Strategy B pairs.

    Saves all 9 notes, then for each intra-cluster pair runs both agents
    and computes recall (TP / total_positive_pairs).

    Goal: bidirectional recall ≥ standard recall (no regression)
    and ideally improved recall on the pairs that standard missed.
    """
    saved: dict[str, NoteRecord] = {}
    ids = []
    try:
        # Save all notes
        for label, content in STRATEGY_B_NOTE_CONTENTS.items():
            rec = _save_note_with_embedding(textwrap.dedent(content).strip(), label)
            saved[label] = rec
            ids.append(rec.id)

        print("\n\n  BLOQUE 4 — RECALL COMPARISON (Strategy B intra-cluster pairs)")
        print("  " + "═" * 68)

        std_tp = 0
        bidir_tp = 0
        results = []

        for label_a, label_b in STRATEGY_B_INTRA_PAIRS:
            na = saved[label_a]
            nb = saved[label_b]
            dist = _measure_distance(na, nb)
            tier = _tier(dist)

            std_links   = _run_standard(na, nb, dist)
            bidir_links = _run_bidirectional(na, nb, dist)

            std_linked   = _linked(std_links, na.id)
            bidir_linked = _linked(bidir_links, na.id)

            if std_linked:
                std_tp += 1
            if bidir_linked:
                bidir_tp += 1

            symbol = ""
            if std_linked and bidir_linked:
                symbol = "✅ both linked"
            elif std_linked and not bidir_linked:
                symbol = "⬇️  standard only — bidir dropped (regression)"
            elif not std_linked and bidir_linked:
                symbol = "⬆️  bidir only — recall improvement!"
            else:
                symbol = "❌ neither linked"

            print(f"\n  {label_a!r:30s} ↔  {label_b!r}")
            print(f"    dist={dist:.4f}  tier={tier!r}")
            print(f"    {symbol}")

        total = len(STRATEGY_B_INTRA_PAIRS)
        std_recall   = std_tp / total
        bidir_recall = bidir_tp / total

        print(f"\n  ─────────────────────────────────────────────────────────────────")
        print(f"  Standard    recall : {std_recall:.2f}  ({std_tp}/{total})")
        print(f"  Bidir       recall : {bidir_recall:.2f}  ({bidir_tp}/{total})")
        delta = bidir_recall - std_recall
        print(f"  Delta (bidir - std): {delta:+.2f}")
        print(f"  {'═' * 68}\n")

    finally:
        _cleanup(ids)

    # Hard assertion: bidirectional must not regress below standard
    assert bidir_recall >= std_recall, (
        f"Bidirectional linker has LOWER recall than standard ({bidir_recall:.2f} < {std_recall:.2f}).\n"
        f"The backward validation is dropping true positives. Check the backward prompt."
    )


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 5 — PRECISION COMPARISON: los 4 pares trampa de Strategy C
# ─────────────────────────────────────────────────────────────────────────────

STRATEGY_C_TRAP_PAIRS = [
    ("atomic_habits",  ATOMIC_HABITS_CONTENT,
     "atomic_notes",   ATOMIC_NOTES_CONTENT),
    ("flow_psychology",
     "Flow (Csikszentmihalyi): complete absorption in a challenging activity when skill matches challenge. "
     "Characteristics: loss of time sense, intrinsic motivation, peak performance and subjective well-being.",
     "flow_programming",
     "Flow-based programming (FBP): applications as networks of black-box processes exchanging data packets "
     "over predefined connections. Each process runs concurrently; coordination through data flow, not shared state."),
    ("containers_docker",
     "In DevOps, a container is a lightweight executable package with code, runtime and libraries. "
     "Docker popularised containers via Dockerfiles. They share the host kernel, making them faster than VMs.",
     "containers_java",
     "In Java, the Collections Framework provides container data structures: List, Set, Map. "
     "ArrayList (O(1) random access), HashSet (O(1) lookup), TreeMap (red-black tree). "
     "Choose based on access patterns."),
    ("network_effects",
     "Network effects: product value increases as more people use it. Metcalfe's Law: value ∝ n². "
     "Examples: social media, payment networks. Strong network effects create durable competitive moats.",
     "neural_network",
     "Artificial neural network (ANN): layers of neurons trained via backpropagation and gradient descent. "
     "CNNs for images, RNNs/LSTMs for sequences, Transformers use self-attention for language tasks."),
]


@skip_no_creds
def test_bidir_precision_strategy_c():
    """
    BLOQUE 5 — Precision comparison on Strategy C trap pairs.

    For each homonym pair: saves both notes, measures distance, runs both agents.
    Goal: bidirectional creates FEWER false positives than standard.

    A successful result: bidir_fp ≤ std_fp (no precision regression).
    An ideal result: bidir_fp < std_fp (precision improvement).
    """
    std_fp = 0
    bidir_fp = 0
    ids = []

    print("\n\n  BLOQUE 5 — PRECISION COMPARISON (Strategy C trap pairs)")
    print("  " + "═" * 68)

    try:
        for label_a, content_a, label_b, content_b in STRATEGY_C_TRAP_PAIRS:
            na = _save_note_with_embedding(content_a, label_a)
            nb = _save_note_with_embedding(content_b, label_b)
            ids.extend([na.id, nb.id])

            dist = _measure_distance(na, nb)
            tier = _tier(dist)

            std_links   = _run_standard(na, nb, dist)
            bidir_links = _run_bidirectional(na, nb, dist)

            std_linked   = _linked(std_links, na.id)
            bidir_linked = _linked(bidir_links, na.id)

            if std_linked:
                std_fp += 1
            if bidir_linked:
                bidir_fp += 1

            if std_linked and not bidir_linked:
                symbol = "✅ bidir correctly dropped the false positive"
            elif not std_linked and not bidir_linked:
                symbol = "✅ both correctly rejected"
            elif std_linked and bidir_linked:
                symbol = "⚠️  both fall for the homonym"
            else:
                symbol = "⚠️  bidir created a link that standard didn't"

            print(f"\n  {label_a!r:25s} ↔  {label_b!r}")
            print(f"    dist={dist:.4f}  tier={tier!r}")
            print(f"    {symbol}")

    finally:
        _cleanup(ids)

    total = len(STRATEGY_C_TRAP_PAIRS)
    std_prec   = 1.0 - (std_fp / total)
    bidir_prec = 1.0 - (bidir_fp / total)

    print(f"\n  ─────────────────────────────────────────────────────────────────")
    print(f"  Standard    false positives : {std_fp}/{total}  (precision = {std_prec:.2f})")
    print(f"  Bidir       false positives : {bidir_fp}/{total}  (precision = {bidir_prec:.2f})")
    delta = bidir_prec - std_prec
    print(f"  Delta (bidir - std)         : {delta:+.2f}")
    print(f"  {'═' * 68}\n")

    assert bidir_fp <= std_fp, (
        f"Bidirectional linker has MORE false positives than standard "
        f"({bidir_fp} > {std_fp}) — precision regression detected."
    )
