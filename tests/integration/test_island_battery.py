"""
test_island_battery.py
──────────────────────
Batería de tests de inserción de islas con LLM real (Bedrock / Nova Micro EU).

Objetivo: estresar el sistema de linking y formación de archipiélagos con tres
estrategias diseñadas para revelar dónde falla el 20% que importa.

═══════════════════════════════════════════════════════════════════╗
  ESTRATEGIA A — RUIDO TOTAL                                       ║
  6 notas de dominios completamente distintos.                     ║
  Expectativa: 0 links, 0 archipiélagos.                          ║
  Falla detectada si: el sistema alucina conexiones entre          ║
  conceptos que no tienen nada en común.    (False Positive test)  ║
                                                                   ║
  ESTRATEGIA B — SILOS SEPARADOS                                   ║
  9 notas en 3 clusters temáticos (PKM · DevOps · Nutrición).     ║
  Expectativa: ≥2 archipiélagos, cero links cruzados entre silos. ║
  Falla detectada si: PKM se une a DevOps, etc.      (Bleed test)  ║
                                                                   ║
  ESTRATEGIA C — FALSOS AMIGOS                                     ║
  Pares de notas que comparten vocabulario superficial             ║
  pero son conceptualmente distintas.                              ║
  Expectativa: ≤1 link entre los pares "trampa".                  ║
  Falla detectada si: el LLM se deja engañar por las palabras.    ║
                                             (Discrimination test)  ║
═════════════════════════════════════════════════════════════════════

Run only these tests (costs Bedrock tokens):
    .venv\\Scripts\\python.exe -m pytest tests/integration/test_island_battery.py -v -s -m integration

Run a single strategy:
    ... -k "test_strategy_a"
    ... -k "test_strategy_b"
    ... -k "test_strategy_c"
"""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from typing import Optional

import pytest

pytestmark = pytest.mark.integration

# ── Skip guard ────────────────────────────────────────────────────────────────

def _has_aws_credentials() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ) or bool(os.getenv("AWS_PROFILE"))


skip_no_creds = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="AWS credentials not available; skipping Bedrock battery",
)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IslandInput:
    """A note to be ingested through the full pipeline."""
    content: str
    label: str          # human label for diagnostic output (not sent to LLM)
    cluster: str        # expected cluster; "none" = should stay solo


@dataclass
class IngestionResult:
    """Captures the pipeline output for one note."""
    label: str
    cluster: str
    note_id: Optional[int]
    action: str                      # "CREATE" | "MERGE" | "SKIP"
    arch_action: str                 # "NONE" | "JOIN" | "CREATE"
    arch_id: Optional[int]
    arch_name: Optional[str]
    links_created: list[dict]        # [{target_id, relation_type, reason}]
    summary: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ingest(content: str, label: str, cluster: str) -> IngestionResult:
    """Run a single note through the full ingest_graph and capture results."""
    from src.workflows.ingest_workflow import ingest_graph
    from shared.schemas.workflow.ingest import IngestState

    state = IngestState(content=content)
    raw = ingest_graph.invoke(state)

    # Normalise dict vs Pydantic result
    def _get(key, default=None):
        if isinstance(raw, dict):
            return raw.get(key, default)
        return getattr(raw, key, default)

    # Normalise links (may be LinkItem objects or dicts)
    raw_links = _get("links", [])
    links: list[dict] = []
    for lnk in raw_links:
        if isinstance(lnk, dict):
            links.append(lnk)
        else:
            links.append({
                "target_id":     lnk.target_id,
                "relation_type": lnk.relation_type,
                "reason":        lnk.reason,
            })

    return IngestionResult(
        label=label,
        cluster=cluster,
        note_id=_get("note_id"),
        action=_get("action", "CREATE"),
        arch_action=_get("archipelago_action", "NONE") or "NONE",
        arch_id=_get("archipelago_id"),
        arch_name=_get("archipelago_name"),
        links_created=links,
        summary=_get("summary"),
    )


def _cleanup(results: list[IngestionResult]) -> None:
    """Delete all notes (and their links via cascade) created during a test."""
    from src.repository.link_repository import link_repository
    from src.repository.note_repository import note_repository

    ids = [r.note_id for r in results if r.note_id is not None]
    for nid in ids:
        link_repository.delete_links_for_note(nid)
    for nid in ids:
        note_repository.delete_note(nid)


def _print_report(strategy: str, results: list[IngestionResult]) -> None:
    """Print a readable diagnostic table to stdout (visible with pytest -s)."""
    sep = "─" * 72
    print(f"\n\n{'═' * 72}")
    print(f"  BATTERY REPORT — {strategy}")
    print(f"{'═' * 72}")

    for r in results:
        print(f"\n  [{r.label}]  cluster_expected={r.cluster!r}")
        print(f"    note_id    : {r.note_id}")
        print(f"    gatekeeper : {r.action}")
        print(f"    geo_action : {r.arch_action}  →  arch={r.arch_name!r}  (id={r.arch_id})")
        if r.links_created:
            for lnk in r.links_created:
                tid    = lnk.get("target_id")
                rel    = lnk.get("relation_type")
                reason = lnk.get("reason", "")
                # Find the label of the target note
                target_label = next(
                    (rr.label for rr in results if rr.note_id == tid), f"note_{tid}"
                )
                print(f"    link       : {rel} → {target_label!r}  |  {reason[:80]}")
        else:
            print(f"    links      : (none)")
        if r.summary:
            print(f"    summary    : {textwrap.shorten(r.summary, 90)}")

    print(f"\n{'═' * 72}\n")


def _build_link_index(results: list[IngestionResult]) -> dict[tuple[int, int], str]:
    """
    Return a dict mapping (source_id, target_id) → relation_type for all links
    produced during the batch.  Direction-normalised: (min, max) as key.
    """
    index: dict[tuple[int, int], str] = {}
    for r in results:
        if r.note_id is None:
            continue
        for lnk in r.links_created:
            tid = lnk.get("target_id")
            if tid is None:
                continue
            pair = (min(r.note_id, tid), max(r.note_id, tid))
            index[pair] = lnk.get("relation_type", "RELATES")
    return index


def _notes_in_same_arch(
    results: list[IngestionResult],
    label_a: str,
    label_b: str,
) -> bool:
    """True if two notes ended up in the same non-None archipelago."""
    ra = next(r for r in results if r.label == label_a)
    rb = next(r for r in results if r.label == label_b)
    return (
        ra.arch_id is not None
        and rb.arch_id is not None
        and ra.arch_id == rb.arch_id
    )


def _are_linked(
    results: list[IngestionResult],
    label_a: str,
    label_b: str,
) -> bool:
    """True if a link was created between two notes (in either direction)."""
    ra = next(r for r in results if r.label == label_a)
    rb = next(r for r in results if r.label == label_b)
    if ra.note_id is None or rb.note_id is None:
        return False
    index = _build_link_index(results)
    pair = (min(ra.note_id, rb.note_id), max(ra.note_id, rb.note_id))
    return pair in index


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATEGIA A — RUIDO TOTAL
# ─────────────────────────────────────────────────────────────────────────────
#
# 6 notas de dominios radicalmente distintos. No tienen nada en común.
# Cualquier link creado es un falso positivo.
#
# Por qué puede fallar:
#   • El LLM "conecta" conceptos abstractos de forma filosófica
#     ("todo está relacionado con el aprendizaje")
#   • El embedding de Titan mete en la misma región vectores de textos
#     didácticos aunque traten de temas completamente distintos

STRATEGY_A_NOTES: list[IslandInput] = [
    IslandInput(
        label="paella",
        cluster="none",
        content="""
        Paella valenciana es el plato más representativo de la cocina española.
        Se elabora con arroz de grano corto, azafrán, judías verdes, garrofón,
        pollo y conejo. El secreto está en el socarrat: la capa crujiente de
        arroz que se forma en el fondo de la paella al final de la cocción.
        El recipiente tradicional es la paella, una sartén plana y poco honda.
        El fuego debe distribuirse de forma uniforme para que el arroz absorba
        el caldo sin voltearlo en ningún momento.
        """,
    ),
    IslandInput(
        label="teorema_pythagoras",
        cluster="none",
        content="""
        El teorema de Pitágoras establece que en un triángulo rectángulo la suma
        de los cuadrados de los catetos es igual al cuadrado de la hipotenusa:
        a² + b² = c². Es fundamental en geometría euclidiana y tiene aplicaciones
        directas en trigonometría, física (vectores) y arquitectura. La primera
        demostración conocida data de la Grecia antigua aunque civilizaciones
        mesopotámicas ya lo usaban 1000 años antes sin formalizarlo.
        """,
    ),
    IslandInput(
        label="revolucion_francesa",
        cluster="none",
        content="""
        La Revolución Francesa (1789-1799) abolió la monarquía absolutista y
        estableció los principios de libertad, igualdad y fraternidad. Surgió de
        la crisis fiscal del Antiguo Régimen, el descontento de la burguesía y
        el hambre del pueblo llano. La toma de la Bastilla el 14 de julio de 1789
        es su símbolo más reconocido. Desembocó en el Terror jacobino, el
        Directorio y finalmente el ascenso de Napoleón Bonaparte.
        """,
    ),
    IslandInput(
        label="jazz_harmony",
        cluster="none",
        content="""
        Jazz harmony is built on the cycle of fifths and extended chord voicings.
        A typical bebop progression moves through ii-V-I cadences in multiple
        keys. Chord extensions—9ths, 11ths, 13ths—add colour and tension.
        Tritone substitution replaces a dominant 7th chord with one whose root
        is a tritone away, creating chromatic bass movement. The Coltrane changes
        divide the octave into three equal parts using major thirds.
        """,
    ),
    IslandInput(
        label="sleep_hygiene",
        cluster="none",
        content="""
        Sleep hygiene refers to behavioural and environmental practices that
        support consistent, high-quality sleep. Key practices include keeping a
        fixed sleep–wake schedule, avoiding blue-light exposure two hours before
        bed, keeping the bedroom below 18°C, avoiding caffeine after 14:00 and
        alcohol within three hours of sleep. Chronic sleep deprivation impairs
        prefrontal cortex function, reducing decision-making capacity and
        emotional regulation.
        """,
    ),
    IslandInput(
        label="marea_astronomica",
        cluster="none",
        content="""
        Las mareas astronómicas son el resultado de la atracción gravitacional
        de la Luna y el Sol sobre las masas de agua terrestres. La Luna, al ser
        más cercana, ejerce el doble de fuerza mareal que el Sol. Las mareas
        vivas ocurren en luna nueva y luna llena cuando Sol, Tierra y Luna están
        alineados; las mareas muertas ocurren en cuartos creciente y menguante.
        El periodo típico de una marea es de 12 horas y 25 minutos (semidiurna).
        """,
    ),
]


@skip_no_creds
def test_strategy_a_ruido_total():
    """
    ESTRATEGIA A — Ruido Total.

    Inserta 6 notas de dominios completamente distintos.
    Aserciones duras:
      • Total de links creados ≤ 1  (tolerancia mínima de 1 por ruido embedding)
      • Ninguna nota forma archipiélago (actions = NONE)
    """
    results: list[IngestionResult] = []
    try:
        for note in STRATEGY_A_NOTES:
            r = _ingest(note.content, note.label, note.cluster)
            results.append(r)
    finally:
        _print_report("A — RUIDO TOTAL", results)
        _cleanup(results)

    link_index = _build_link_index(results)
    total_links = len(link_index)
    arch_actions = [r.arch_action for r in results]

    print(f"\n  → Total links created : {total_links}  (expected ≤ 1)")
    print(f"  → Geo actions         : {arch_actions}")

    # ── Hard assertions ───────────────────────────────────────────────────────
    assert total_links <= 1, (
        f"STRATEGY A FAILURE — False positives detected!\n"
        f"  Expected ≤ 1 link between totally unrelated notes.\n"
        f"  Got {total_links} link(s):\n"
        + "\n".join(
            f"    note_{src} ↔ note_{tgt} ({rel})"
            for (src, tgt), rel in link_index.items()
        )
    )

    arch_created = [r for r in results if r.arch_action in ("CREATE", "JOIN")]
    assert len(arch_created) == 0, (
        f"STRATEGY A FAILURE — Spurious archipelago formed!\n"
        f"  Expected no archipelago.\n"
        f"  Got: {[(r.label, r.arch_action, r.arch_name) for r in arch_created]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATEGIA B — SILOS SEPARADOS
# ─────────────────────────────────────────────────────────────────────────────
#
# 9 notas en 3 clusters temáticos (3 por cluster).
#   cluster "pkm"    → Zettelkasten · Evergreen Notes · Progressive Summarisation
#   cluster "devops" → Docker · Kubernetes · CI/CD
#   cluster "nutri"  → Dieta mediterránea · Ayuno intermitente · Microbioma
#
# Expectativas:
#   • Cada cluster forma su propio archipiélago (≥ 2 de 3 notas en el mismo arch)
#   • CERO links cruzados entre silos distintos
#   • Las notas del mismo cluster están linkadas entre sí
#
# Por qué puede fallar:
#   • El embedding de un texto sobre "sistemas" (Docker) se acerca a uno sobre
#     "sistemas de notas" (Zettelkasten) si el texto es demasiado abstracto
#   • El LLM inventa conexiones filosóficas ("ambos optimizan procesos")

STRATEGY_B_NOTES: list[IslandInput] = [
    # ── PKM ──────────────────────────────────────────────────────────────────
    IslandInput(
        label="zettelkasten",
        cluster="pkm",
        content="""
        Zettelkasten is a note-taking method developed by sociologist Niklas
        Luhmann. Each note captures exactly one idea and is connected to other
        notes through explicit bidirectional links. Notes are stored with a
        unique ID and a set of keywords. The value accumulates not in individual
        notes but in the network of connections between them. Luhmann produced
        over 90,000 notes and 70 books using this system throughout his career.
        """,
    ),
    IslandInput(
        label="evergreen_notes",
        cluster="pkm",
        content="""
        Evergreen notes, coined by Andy Matuschak, are notes written for long-
        term reuse. Unlike fleeting notes captured in the moment, evergreen notes
        are revised over time to remain accurate and generalisable. They are
        written in your own words, focused on a single concept, and densely
        linked to related ideas. The name comes from the trees that stay green
        year-round—these notes don't become obsolete.
        """,
    ),
    IslandInput(
        label="progressive_summarisation",
        cluster="pkm",
        content="""
        Progressive Summarisation is a note-taking technique by Tiago Forte where
        you highlight the most important passages in layers over multiple review
        sessions. Layer 1: save the source. Layer 2: bold key sentences.
        Layer 3: highlight the boldest. Layer 4: write an executive summary.
        The goal is to make future retrieval frictionless by investing effort
        incrementally rather than all at once during initial capture.
        """,
    ),

    # ── DevOps ────────────────────────────────────────────────────────────────
    IslandInput(
        label="docker",
        cluster="devops",
        content="""
        Docker is an open-source platform that packages applications into
        containers—standardised units that include the application code, runtime,
        system libraries and settings. Containers share the host OS kernel but
        run in isolated user-space processes. A Dockerfile defines the image
        layers; `docker build` creates the image; `docker run` starts a
        container. Images are stored in registries like Docker Hub or ECR.
        """,
    ),
    IslandInput(
        label="kubernetes",
        cluster="devops",
        content="""
        Kubernetes (K8s) is an open-source container orchestration system that
        automates deployment, scaling and management of containerised applications.
        Its control plane manages a cluster of worker nodes. Core abstractions:
        Pod (smallest deployable unit), Deployment (desired state), Service
        (stable network endpoint), ConfigMap and Secret (configuration). The
        scheduler assigns pods to nodes based on resource availability.
        """,
    ),
    IslandInput(
        label="ci_cd",
        cluster="devops",
        content="""
        Continuous Integration (CI) and Continuous Delivery (CD) are practices
        that automate the software delivery pipeline. CI: developers merge code
        frequently; automated tests run on every commit to detect regressions
        early. CD: every passing build is kept in a deployable state; deployment
        to production is automated or one-click. Tools: GitHub Actions, GitLab
        CI, Jenkins. Key metric: lead time from commit to production.
        """,
    ),

    # ── Nutrición ─────────────────────────────────────────────────────────────
    IslandInput(
        label="dieta_mediterranea",
        cluster="nutri",
        content="""
        La dieta mediterránea está basada en el consumo abundante de frutas,
        verduras, legumbres, cereales integrales, aceite de oliva virgen extra
        y pescado. El consumo de carne roja, azúcar y ultraprocesados es
        mínimo. Múltiples estudios epidemiológicos la asocian con reducción
        del riesgo cardiovascular, menor incidencia de diabetes tipo 2 y
        mayor longevidad. El aceite de oliva es su principal grasa,
        rico en ácidos grasos monoinsaturados y polifenoles antioxidantes.
        """,
    ),
    IslandInput(
        label="ayuno_intermitente",
        cluster="nutri",
        content="""
        El ayuno intermitente es un patrón alimentario que alterna periodos de
        alimentación y ayuno. El protocolo 16:8 restringe la ingesta a una
        ventana de 8 horas diarias. El ayuno activa la autofagia (limpieza
        celular), mejora la sensibilidad a la insulina y puede promover la
        pérdida de grasa sin pérdida muscular si se mantiene la ingesta
        proteica. No es adecuado para personas con trastornos alimentarios,
        diabetes tipo 1 ni embarazadas.
        """,
    ),
    IslandInput(
        label="microbioma",
        cluster="nutri",
        content="""
        El microbioma intestinal es el conjunto de billones de microorganismos
        que habitan el tracto digestivo. Una microbiota diversa se asocia con
        mejor metabolismo, mayor eficiencia del sistema inmune y menor
        inflamación sistémica. Los prebióticos (fibra fermentable) alimentan
        las bacterias beneficiosas; los probióticos los introducen directamente.
        La dieta es el principal modulador del microbioma: una dieta rica en
        fibra vegetal diversa aumenta la diversidad microbiana en semanas.
        """,
    ),
]

# Ground truth: qué pares SÍ deben estar linkados y cuáles NO
STRATEGY_B_SAME_CLUSTER_PAIRS = [
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

STRATEGY_B_CROSS_CLUSTER_PAIRS = [
    ("zettelkasten",  "docker"),
    ("zettelkasten",  "dieta_mediterranea"),
    ("evergreen_notes", "kubernetes"),
    ("progressive_summarisation", "ci_cd"),   # most dangerous: both are "processes"
    ("docker",        "microbioma"),
    ("kubernetes",    "dieta_mediterranea"),
    ("ci_cd",         "ayuno_intermitente"),
]


@skip_no_creds
def test_strategy_b_silos_separados():
    """
    ESTRATEGIA B — Silos Separados.

    Inserta 9 notas en 3 clusters temáticos. Verifica que:
      • Ningún link cross-cluster fue creado (false positives = 0)
      • Al menos 2 de 3 archipiélagos distintos se formaron
      • Los pares intra-cluster que sí están linkados representan recall ≥ 0.50

    La aserción más dura es la de cross-cluster: un solo link entre
    "progressive_summarisation" y "ci_cd" sería una señal de alarma grave.
    """
    results: list[IngestionResult] = []
    try:
        for note in STRATEGY_B_NOTES:
            r = _ingest(note.content, note.label, note.cluster)
            results.append(r)
    finally:
        _print_report("B — SILOS SEPARADOS", results)
        _cleanup(results)

    link_index = _build_link_index(results)

    # ── Cross-cluster false positives ────────────────────────────────────────
    cross_links: list[tuple[str, str, str]] = []
    for label_a, label_b in STRATEGY_B_CROSS_CLUSTER_PAIRS:
        if _are_linked(results, label_a, label_b):
            ra = next(r for r in results if r.label == label_a)
            rb = next(r for r in results if r.label == label_b)
            pair = (min(ra.note_id, rb.note_id), max(ra.note_id, rb.note_id))
            cross_links.append((label_a, label_b, link_index.get(pair, "?")))

    print(f"\n  → Cross-cluster false positives : {len(cross_links)}")
    for a, b, rel in cross_links:
        print(f"       {a} ↔ {b}  [{rel}]  ← PROBLEM")

    # ── Intra-cluster recall ──────────────────────────────────────────────────
    intra_correct = sum(
        1 for la, lb in STRATEGY_B_SAME_CLUSTER_PAIRS
        if _are_linked(results, la, lb)
    )
    intra_recall = intra_correct / len(STRATEGY_B_SAME_CLUSTER_PAIRS)
    print(f"  → Intra-cluster recall : {intra_recall:.2f}  ({intra_correct}/{len(STRATEGY_B_SAME_CLUSTER_PAIRS)})")

    # ── Archipelago count ─────────────────────────────────────────────────────
    distinct_arch_ids = {r.arch_id for r in results if r.arch_id is not None}
    print(f"  → Distinct archipelago IDs : {distinct_arch_ids}  (expected ≥ 2)")

    # ── Assertions ────────────────────────────────────────────────────────────
    assert len(cross_links) == 0, (
        f"STRATEGY B FAILURE — Cross-cluster bleed detected!\n"
        f"  The linker created {len(cross_links)} link(s) between unrelated silos:\n"
        + "\n".join(f"    {a} ↔ {b}  [{rel}]" for a, b, rel in cross_links)
        + "\n  These are false positives that will corrupt archipelago formation."
    )

    assert intra_recall >= 0.50, (
        f"STRATEGY B FAILURE — Poor intra-cluster recall: {intra_recall:.2f} < 0.50\n"
        f"  The linker is missing obvious same-topic links."
    )

    assert len(distinct_arch_ids) >= 2, (
        f"STRATEGY B FAILURE — Only {len(distinct_arch_ids)} archipelago(s) formed.\n"
        f"  Expected ≥ 2 distinct clusters to emerge from 3 topic groups."
    )


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATEGIA C — FALSOS AMIGOS
# ─────────────────────────────────────────────────────────────────────────────
#
# Pares de notas que comparten vocabulario superficial pero son conceptualmente
# distintas. Diseñadas para engañar tanto el embedding (nivel léxico) como
# el LLM (nivel semántico superficial).
#
# Pares trampa:
#   1. "atomic_habits"  vs "atomic_notes"
#      Comparten "atomic" pero uno es psicología del hábito (James Clear)
#      y el otro es arquitectura de un PKM.
#
#   2. "flow_csikszentmihalyi" vs "flow_programming"
#      "Flow" en psicología (estado mental óptimo) vs
#      "Flow" en arquitectura software (programación reactiva/event-driven).
#
#   3. "graph_theory" vs "graph_database"
#      "Grafos" en matemáticas discretas vs "grafos" como modelo de BD.
#      Relacionados pero el nivel de abstracción es completamente distinto.
#      Este par SÍ debería producir un link (RELATES).
#
#   4. "containers_docker" vs "containers_java"
#      "Container" como imagen Docker vs "Container" como estructura de datos
#      en Java (Collection framework). Homonimia técnica pura.
#
#   5. "network_effects" vs "neural_network"
#      "Red" en economía (externalidades de red, Metcalfe) vs
#      "Red" en ML (perceptrones, backprop). Comparten la palabra "network"
#      y la idea de nodos conectados, pero son dominios completamente distintos.
#
# Expectativas:
#   • Par 3 (graph_theory ↔ graph_database): SÍ debe linkarse
#   • Pares 1, 2, 4, 5: NO deben linkarse (falsos amigos)
#
# Por qué puede fallar:
#   • El embedding de Titan acerca vectores que comparten terminología técnica
#   • El LLM extrapola relaciones abstractas ("ambos modelan conexiones")

STRATEGY_C_NOTES: list[IslandInput] = [
    # Par 1 — "atomic"
    IslandInput(
        label="atomic_habits",
        cluster="behavior",
        content="""
        Atomic Habits by James Clear argues that 1% daily improvements compound
        into remarkable results over time. The core framework is the habit loop:
        cue, craving, response, reward. Clear introduces the concept of identity-
        based habits: instead of "I want to run a marathon", say "I am a runner".
        The Four Laws of Behaviour Change—make it obvious, attractive, easy and
        satisfying—provide a systematic approach to building good habits and
        breaking bad ones.
        """,
    ),
    IslandInput(
        label="atomic_notes",
        cluster="pkm",
        content="""
        Atomic notes are the foundational principle of effective personal
        knowledge management. Each note captures exactly one idea: a claim,
        concept, argument or question. Atomicity enables combinatorial linking—
        a single idea can connect to many other ideas without confusion.
        Non-atomic notes create retrieval problems because they are hard to
        resurface in contexts different from the one in which they were created.
        """,
    ),

    # Par 2 — "flow"
    IslandInput(
        label="flow_csikszentmihalyi",
        cluster="psychology",
        content="""
        Flow, as described by Mihaly Csikszentmihalyi, is a state of complete
        absorption in a challenging activity. It occurs when skill level and
        challenge level are in balance: too easy → boredom; too hard → anxiety.
        Characteristics: loss of sense of time, effortless concentration,
        intrinsic motivation, clear goals with immediate feedback. Flow is
        associated with peak performance, creativity and subjective well-being.
        """,
    ),
    IslandInput(
        label="flow_programming",
        cluster="software",
        content="""
        Flow-based programming (FBP) is a programming paradigm where applications
        are defined as networks of black-box processes that exchange data as
        packets over predefined connections. Each process runs concurrently and
        independently; coordination happens entirely through data flow, not
        shared state. Node-RED is a popular FBP tool for IoT automation.
        FBP naturally maps to reactive systems and event-driven architectures.
        """,
    ),

    # Par 3 — "graph" (este SÍ debe linkarse — son RELATES)
    IslandInput(
        label="graph_theory",
        cluster="math",
        content="""
        Graph theory is the branch of mathematics that studies graphs: structures
        consisting of vertices (nodes) connected by edges. Key concepts: degree
        of a vertex, paths, cycles, trees, directed vs undirected graphs,
        weighted edges. Fundamental algorithms: Dijkstra (shortest path),
        Kruskal/Prim (minimum spanning tree), BFS/DFS (traversal). Graph theory
        underpins network analysis, social network modelling and compiler design.
        """,
    ),
    IslandInput(
        label="graph_database",
        cluster="data",
        content="""
        A graph database stores data as nodes and edges with properties, making
        relationship queries orders of magnitude faster than joins in relational
        databases. Neo4j uses the Cypher query language; Amazon Neptune supports
        Gremlin and SPARQL. Ideal use cases: social networks, recommendation
        engines, fraud detection, knowledge graphs. The property graph model
        allows arbitrary key-value pairs on both nodes and relationships.
        """,
    ),

    # Par 4 — "containers" (homonimia técnica)
    IslandInput(
        label="containers_docker",
        cluster="devops",
        content="""
        In the context of DevOps and cloud computing, a container is a lightweight,
        standalone executable package that includes everything needed to run a
        piece of software: code, runtime, libraries and configuration. Docker
        popularised containers by making image creation reproducible via Dockerfiles.
        Containers differ from virtual machines in that they share the host kernel,
        making them faster to start and less resource-intensive.
        """,
    ),
    IslandInput(
        label="containers_java",
        cluster="programming",
        content="""
        In Java, the Collections Framework provides container data structures that
        store and organise objects. The main interfaces are Collection, List, Set
        and Map. Common implementations: ArrayList (dynamic array), LinkedList
        (doubly linked), HashSet (hash table), TreeMap (red-black tree). Choosing
        the right container depends on access patterns: ArrayList for O(1) random
        access, LinkedList for O(1) insertion at ends, HashSet for O(1) lookup.
        """,
    ),

    # Par 5 — "network"
    IslandInput(
        label="network_effects",
        cluster="economics",
        content="""
        Network effects occur when a product or service becomes more valuable as
        more people use it. Metcalfe's Law states that the value of a network is
        proportional to the square of the number of connected users (n²).
        Classic examples: telephone networks, social media platforms, payment
        systems. Businesses with strong network effects are hard to displace
        because switching costs rise with the size of the network.
        """,
    ),
    IslandInput(
        label="neural_network",
        cluster="ml",
        content="""
        An artificial neural network (ANN) is a computational model inspired by
        the biological brain. It consists of layers of neurons (perceptrons):
        input, hidden and output. Training adjusts weights via backpropagation
        and gradient descent to minimise a loss function. Deep neural networks
        (many hidden layers) learn hierarchical feature representations.
        CNNs specialise in image data; RNNs/LSTMs handle sequential data;
        Transformers use self-attention for language tasks.
        """,
    ),
]

# Which pairs should link and which should not
STRATEGY_C_SHOULD_LINK    = [("graph_theory", "graph_database")]  # RELATES — same formalism
STRATEGY_C_SHOULD_NOT_LINK = [
    ("atomic_habits",         "atomic_notes"),       # "atomic" is just a shared adjective
    ("flow_csikszentmihalyi", "flow_programming"),   # "flow" is a homonym
    ("containers_docker",     "containers_java"),    # "container" is a homonym
    ("network_effects",       "neural_network"),     # "network" is a homonym
]


@skip_no_creds
def test_strategy_c_falsos_amigos():
    """
    ESTRATEGIA C — Falsos Amigos.

    Inserta 10 notas con homonimia terminológica.
    Aserciones:
      • Los 4 pares trampa NO deben producir links (false positives = 0)
      • El par real (graph_theory ↔ graph_database) SÍ debe linkarse
    """
    results: list[IngestionResult] = []
    try:
        for note in STRATEGY_C_NOTES:
            r = _ingest(note.content, note.label, note.cluster)
            results.append(r)
    finally:
        _print_report("C — FALSOS AMIGOS", results)
        _cleanup(results)

    # ── Should NOT be linked ──────────────────────────────────────────────────
    false_positives: list[tuple[str, str]] = []
    for label_a, label_b in STRATEGY_C_SHOULD_NOT_LINK:
        if _are_linked(results, label_a, label_b):
            false_positives.append((label_a, label_b))

    print(f"\n  → False positives (falsos amigos linkados): {len(false_positives)}")
    for a, b in false_positives:
        print(f"       {a} ↔ {b}  ← PROBLEM: homonimia creó un link incorrecto")

    # ── Should be linked ──────────────────────────────────────────────────────
    false_negatives: list[tuple[str, str]] = []
    for label_a, label_b in STRATEGY_C_SHOULD_LINK:
        if not _are_linked(results, label_a, label_b):
            false_negatives.append((label_a, label_b))

    print(f"  → False negatives (relaciones reales no detectadas): {len(false_negatives)}")
    for a, b in false_negatives:
        print(f"       {a} ↔ {b}  ← MISSED: debería haberse linkado como RELATES")

    # ── Assertions ────────────────────────────────────────────────────────────
    assert len(false_positives) == 0, (
        f"STRATEGY C FAILURE — El LLM fue engañado por homonimia terminológica!\n"
        f"  {len(false_positives)} par(es) trampa producen links incorrectos:\n"
        + "\n".join(f"    {a} ↔ {b}" for a, b in false_positives)
        + "\n\n  Diagnóstico: revisar el prompt del LinkerAgent — añadir instrucción\n"
        + "  explícita de distinguir entre homonimia léxica y relación conceptual."
    )

    assert len(false_negatives) == 0, (
        f"STRATEGY C FAILURE — El link real (graph_theory ↔ graph_database) no se detectó.\n"
        f"  Diagnóstico: el LLM es demasiado conservador o el embedding no acerca\n"
        f"  suficientemente estos conceptos."
    )


# ─────────────────────────────────────────────────────────────────────────────
# BONUS — DUPLICADOS Y PARÁFRASIS
# ─────────────────────────────────────────────────────────────────────────────
#
# Test extra: dos notas que son paráfrasis de la misma idea.
# El Gatekeeper debe reconocerlas como MERGE o SKIP (no CREATE).
# Si ambas entran como notas distintas, deben tener REINFORCES link.

@skip_no_creds
def test_strategy_d_parafraseo():
    """
    BONUS ESTRATEGIA D — Paráfrasis.

    Dos notas que expresan la misma idea con vocabulario distinto.
    Expectativas:
      • La segunda nota es MERGE o SKIP (no CREATE), O
      • Si se crea, existe un link REINFORCES entre ellas.
    """
    note_a = IslandInput(
        label="spaced_rep_a",
        cluster="memory",
        content="""
        Spaced repetition is a learning technique that schedules reviews at
        increasing intervals based on the forgetting curve. Each successful
        recall postpones the next review; each failure resets it to a shorter
        interval. The algorithm—Leitner box or SM-2—ensures you spend more
        time on material you know poorly and less on material you know well.
        Consistent use over months creates durable long-term memory representations.
        """,
    )
    note_b = IslandInput(
        label="spaced_rep_b",
        cluster="memory",
        content="""
        La repetición espaciada es un método de estudio que programa los
        repasos en intervalos crecientes de tiempo, aprovechando la curva
        del olvido de Ebbinghaus. Cuando recuerdas bien un concepto, el
        siguiente repaso se aleja en el tiempo; cuando fallas, el intervalo
        se acorta. Este sistema garantiza que dediques más tiempo a lo que
        no dominas, haciendo el estudio más eficiente que releer pasivamente.
        """,
    )

    results: list[IngestionResult] = []
    try:
        for note in [note_a, note_b]:
            r = _ingest(note.content, note.label, note.cluster)
            results.append(r)
    finally:
        _print_report("D — PARÁFRASIS", results)
        _cleanup(results)

    ra, rb = results

    # Aceptamos dos comportamientos correctos:
    # 1. La segunda nota fue reconocida como MERGE o SKIP → gatekeeper funciona
    # 2. Ambas son CREATE pero están linkadas como REINFORCES

    gatekeeper_handled = rb.action in ("MERGE", "SKIP")
    linked = _are_linked(results, "spaced_rep_a", "spaced_rep_b")

    print(f"\n  → Nota B gatekeeper action : {rb.action}")
    print(f"  → Linkadas               : {linked}")

    assert gatekeeper_handled or linked, (
        f"STRATEGY D FAILURE — Paráfrasis no detectada:\n"
        f"  Nota A: {ra.action}, arch={ra.arch_action}\n"
        f"  Nota B: {rb.action}, arch={rb.arch_action}\n"
        f"  Linked: {linked}\n"
        f"  El Gatekeeper no detectó la similitud NI el Linker creó un REINFORCES link.\n"
        f"  Diagnóstico: comprobar umbral DISTANCE_DEDUP_CUTOFF y prompt del Gatekeeper."
    )
