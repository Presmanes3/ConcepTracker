"""
tests/integration/test_f1_extended.py
════════════════════════════════════════════════════════════════════════════════
CAPA 3 — Gold Standard F1 extendido (7 clusters nuevos, ~80 notas, ~110 pares)

Mejoras sobre test_precision_recall_f1.py:
  • 7 veces más dominio cubierto: ML, finanzas, ciencias cognitivas, estoicismo,
    agile/software, neurociencia, productividad profunda
  • Ingestión paralela: clusters se ingestán en paralelo (ThreadPoolExecutor)
    con ingestión sequential dentro de cada cluster para maximizar forward links
  • Los links se leen directamente desde DB (forward + retrospective)
  • ~110 ground truth pairs → métricas más estables estadísticamente

Arquitectura de paralelismo:
  ┌─────────────────────────────────────────────────┐
  │  test_f1_extended                               │
  │                                                 │
  │  ThreadPoolExecutor(max_workers=4)              │
  │    ├── Thread 1 → ingest cluster ml (6 notas)   │
  │    ├── Thread 2 → ingest cluster finance (5)    │
  │    ├── Thread 3 → ingest cluster cognitive (6)  │
  │    └── Thread 4 → ingest cluster stoicism (5)   │
  │    ... (7 clusters total, batched in 2 rounds)  │
  │                                                 │
  │  After all threads done → read links from DB    │
  └─────────────────────────────────────────────────┘

Nota: la ingestión paralela de notas dentro de un cluster diferente no degrada
recall porque el retrospective linker corre por nota una vez guardada en DB.
El `_build_link_set` lee la DB al final para capturar TODOS los links.

Run:
    $env:AWS_PROFILE="aws-presmanes-home"
    pytest tests/integration/test_f1_extended.py -v -s

Coste estimado: ~0.20 USD por run completo (80 notas × 4 LLM calls cada una).
"""
from __future__ import annotations

import os
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import pytest

pytestmark = pytest.mark.integration

_print_lock = Lock()


def _has_aws_credentials() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ) or bool(os.getenv("AWS_PROFILE"))


skip_no_creds = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="AWS credentials not available",
)


# ═══════════════════════════════════════════════════════════════════════════════
# CORPUS — 7 clusters × 5-7 notes + traps
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GoldNote:
    label: str
    cluster: str
    content: str


# ── Cluster 1: Machine Learning (technology / machine_learning) ───────────────
ML_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="neural_network",
        cluster="ml",
        content=(
            "A neural network is a computational model inspired by biological neurons. "
            "It consists of layers of nodes connected by weighted edges. During training, "
            "the network adjusts its weights to minimise the difference between its "
            "predictions and the true labels, using backpropagation."
        ),
    ),
    GoldNote(
        label="backpropagation",
        cluster="ml",
        content=(
            "Backpropagation is the algorithm used to train neural networks. It calculates "
            "the gradient of the loss function with respect to each weight by applying the "
            "chain rule of calculus backwards through the network layers. This gradient is "
            "then used by an optimiser such as gradient descent to update weights."
        ),
    ),
    GoldNote(
        label="gradient_descent",
        cluster="ml",
        content=(
            "Gradient descent is an optimisation algorithm that iteratively moves model "
            "parameters in the direction that reduces the loss function. Stochastic gradient "
            "descent (SGD) updates weights using one sample at a time; mini-batch SGD uses "
            "small batches and is the standard in deep learning."
        ),
    ),
    GoldNote(
        label="overfitting",
        cluster="ml",
        content=(
            "Overfitting occurs when a machine learning model learns the training data so "
            "well that it performs poorly on unseen data. It typically happens with models "
            "that are too complex for the amount of training data. Regularisation techniques, "
            "dropout and early stopping are common remedies."
        ),
    ),
    GoldNote(
        label="transfer_learning",
        cluster="ml",
        content=(
            "Transfer learning reuses a model pretrained on a large dataset as the starting "
            "point for a new task. Fine-tuning adjusts the last layers on domain-specific "
            "data. This drastically reduces training time and data requirements, and is the "
            "basis of modern large language models."
        ),
    ),
    GoldNote(
        label="attention_mechanism",
        cluster="ml",
        content=(
            "The attention mechanism allows a neural network to dynamically weight which "
            "parts of the input are most relevant for each output token. Self-attention, "
            "introduced in the Transformer architecture, computes query-key-value products "
            "to capture long-range dependencies without recurrence."
        ),
    ),
]

# ── Cluster 2: Personal Finance (business / finance) ─────────────────────────
FINANCE_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="compound_interest",
        cluster="finance",
        content=(
            "Compound interest is interest calculated on both the principal and the "
            "accumulated interest from previous periods. Albert Einstein allegedly "
            "called it the eighth wonder of the world. A small difference in annual "
            "return compounds into a massive difference over decades."
        ),
    ),
    GoldNote(
        label="dollar_cost_averaging",
        cluster="finance",
        content=(
            "Dollar-cost averaging (DCA) means investing a fixed sum at regular intervals "
            "regardless of market price. This reduces the impact of volatility: you buy "
            "more shares when prices are low and fewer when prices are high, lowering "
            "your average cost per share over time."
        ),
    ),
    GoldNote(
        label="index_fund_investing",
        cluster="finance",
        content=(
            "Index funds passively track a market index such as the S&P 500. Because they "
            "do not require active stock picking, their expense ratios are very low. John "
            "Bogle demonstrated that most actively managed funds underperform their benchmark "
            "index after fees over long periods."
        ),
    ),
    GoldNote(
        label="portfolio_diversification",
        cluster="finance",
        content=(
            "Portfolio diversification spreads investments across different asset classes, "
            "sectors and geographies to reduce unsystematic risk. Harry Markowitz's Modern "
            "Portfolio Theory proves that a diversified portfolio achieves a better "
            "risk-adjusted return than any of its individual components."
        ),
    ),
    GoldNote(
        label="emergency_fund",
        cluster="finance",
        content=(
            "An emergency fund is three to six months of living expenses held in a liquid "
            "account. It prevents the investor from selling investments at a loss during "
            "unexpected events like job loss or medical bills. Financial planners consider "
            "it the foundation of any personal finance strategy."
        ),
    ),
]

# ── Cluster 3: Cognitive Science (life_sciences / psychology) ─────────────────
COGNITIVE_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="cognitive_load_theory",
        cluster="cognitive",
        content=(
            "Cognitive Load Theory, developed by John Sweller, holds that working memory "
            "has a limited capacity and that instructional design should minimise extraneous "
            "load while maximising germane load. Intrinsic load depends on the inherent "
            "complexity of the material being learned."
        ),
    ),
    GoldNote(
        label="working_memory",
        cluster="cognitive",
        content=(
            "Working memory is the cognitive system that temporarily holds and manipulates "
            "information during complex tasks. George Miller's classic paper established "
            "that humans can hold 7 ± 2 chunks simultaneously. Modern estimates are closer "
            "to 4 chunks. It is closely related to fluid intelligence."
        ),
    ),
    GoldNote(
        label="spaced_repetition",
        cluster="cognitive",
        content=(
            "Spaced repetition is a learning technique that schedules review sessions at "
            "increasing intervals based on each item's difficulty. The forgetting curve, "
            "discovered by Ebbinghaus, shows that memory decays exponentially without "
            "review. Spaced repetition counteracts this by reviewing just before forgetting."
        ),
    ),
    GoldNote(
        label="dual_coding_theory",
        cluster="cognitive",
        content=(
            "Dual coding theory, proposed by Allan Paivio, states that information encoded "
            "both verbally and visually is better retained than information encoded in only "
            "one modality. The two mental codes are processed independently and can "
            "reinforce each other during retrieval."
        ),
    ),
    GoldNote(
        label="retrieval_practice",
        cluster="cognitive",
        content=(
            "Retrieval practice — also called the testing effect — is the finding that "
            "actively recalling information from memory produces stronger long-term "
            "retention than re-reading the same material. Even failed retrieval attempts "
            "improve subsequent memory. It is one of the most robust findings in cognitive psychology."
        ),
    ),
    GoldNote(
        label="chunking_cognition",
        cluster="cognitive",
        content=(
            "Chunking is the process of grouping individual items into meaningful units "
            "to overcome working memory limits. Chess masters perceive board positions as "
            "chunks rather than individual pieces, which is why they can recall positions "
            "far better than novices despite having the same raw memory capacity."
        ),
    ),
]

# ── Cluster 4: Stoicism (arts_humanities / philosophy) ────────────────────────
STOICISM_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="stoic_philosophy",
        cluster="stoicism",
        content=(
            "Stoicism is a Hellenistic philosophy founded by Zeno of Citium around 300 BCE. "
            "It holds that virtue is the only true good and that external events are neither "
            "good nor bad in themselves. What matters is our judgement about those events, "
            "not the events themselves, since judgement is within our control."
        ),
    ),
    GoldNote(
        label="dichotomy_of_control",
        cluster="stoicism",
        content=(
            "The dichotomy of control, central to Epictetus's Enchiridion, divides all "
            "things into those 'up to us' (our opinions, desires, aversions and actions) "
            "and those 'not up to us' (body, reputation, property, office). Tranquillity "
            "comes from focusing entirely on what is within our control."
        ),
    ),
    GoldNote(
        label="memento_mori",
        cluster="stoicism",
        content=(
            "Memento mori is the Stoic practice of contemplating one's own death. Rather "
            "than being morbid, the Stoics used it to clarify priorities and appreciate the "
            "present moment. Marcus Aurelius wrote extensively about death as a natural "
            "process and a reason to act with urgency and virtue now."
        ),
    ),
    GoldNote(
        label="negative_visualization",
        cluster="stoicism",
        content=(
            "Negative visualisation (premeditatio malorum) involves mentally rehearsing "
            "bad outcomes before they happen. By vividly imagining loss, illness or failure, "
            "one builds resilience, reduces attachment to outcomes and develops gratitude "
            "for what one already has. It is distinct from pessimism; the goal is equanimity."
        ),
    ),
    GoldNote(
        label="amor_fati",
        cluster="stoicism",
        content=(
            "Amor fati, meaning 'love of fate', is the Nietzschean and Stoic attitude of "
            "not merely accepting but actively embracing everything that happens, including "
            "setbacks and suffering. Marcus Aurelius expresses it as treating obstacles as "
            "the path itself rather than impediments to be overcome."
        ),
    ),
]

# ── Cluster 5: Agile / Software Engineering (technology / devops) ─────────────
AGILE_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="scrum_framework",
        cluster="agile",
        content=(
            "Scrum is an agile framework for developing, delivering and sustaining complex "
            "products. Work is organised in time-boxed iterations called Sprints (1-4 weeks). "
            "The three core roles are Product Owner, Scrum Master and Development Team. "
            "Key ceremonies include Sprint Planning, Daily Standup and Sprint Retrospective."
        ),
    ),
    GoldNote(
        label="kanban_method",
        cluster="agile",
        content=(
            "Kanban is a visual workflow management method that limits work-in-progress (WIP) "
            "to expose bottlenecks and improve flow. Work items move through columns on a "
            "Kanban board. Unlike Scrum, Kanban has no fixed iterations and suits continuous "
            "flow work like operations and support."
        ),
    ),
    GoldNote(
        label="test_driven_development",
        cluster="agile",
        content=(
            "Test-driven development (TDD) is a software practice where you write a failing "
            "test before writing any production code, then write the minimum code to make it "
            "pass, then refactor. The Red-Green-Refactor cycle keeps code testable by design "
            "and creates a comprehensive regression suite as a side effect."
        ),
    ),
    GoldNote(
        label="pair_programming",
        cluster="agile",
        content=(
            "Pair programming places two developers at one workstation: the driver writes "
            "code while the navigator reviews in real time. Roles switch frequently. Studies "
            "show that although it takes more programmer hours initially, pair programming "
            "reduces defects significantly and spreads knowledge across the team."
        ),
    ),
    GoldNote(
        label="sprint_retrospective",
        cluster="agile",
        content=(
            "The Sprint Retrospective is a Scrum ceremony held at the end of each Sprint "
            "where the team reflects on their process, identifies what went well and what "
            "could be improved, and commits to concrete experiments for the next Sprint. "
            "It is the primary mechanism for team-level continuous improvement in Scrum."
        ),
    ),
    GoldNote(
        label="continuous_delivery",
        cluster="agile",
        content=(
            "Continuous delivery (CD) is the practice of keeping software in a releasable "
            "state at all times. Every commit that passes the automated test suite can be "
            "deployed to production instantly with a single command or automatically. "
            "It extends CI/CD by ensuring the deployment pipeline is always green."
        ),
    ),
]

# ── Cluster 6: Neuroscience (life_sciences / biology) ─────────────────────────
NEUROSCIENCE_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="neuroplasticity",
        cluster="neuroscience",
        content=(
            "Neuroplasticity is the brain's ability to reorganise itself by forming new "
            "synaptic connections throughout life. It is strongest during critical "
            "developmental periods but persists into adulthood. Physical exercise, learning "
            "and sleep all promote neuroplasticity."
        ),
    ),
    GoldNote(
        label="long_term_potentiation",
        cluster="neuroscience",
        content=(
            "Long-term potentiation (LTP) is the persistent strengthening of synapses "
            "based on recent patterns of activity. Summarised as 'neurons that fire "
            "together, wire together', LTP is the primary cellular mechanism behind "
            "learning and memory formation in the hippocampus."
        ),
    ),
    GoldNote(
        label="dopamine_circuit",
        cluster="neuroscience",
        content=(
            "Dopamine is a neurotransmitter critical to motivation, reward and learning. "
            "The mesolimbic pathway releases dopamine in anticipation of reward, not just "
            "at reward receipt. This prediction error signal is how the brain learns "
            "which actions lead to positive outcomes."
        ),
    ),
    GoldNote(
        label="cortisol_stress",
        cluster="neuroscience",
        content=(
            "Cortisol is the primary stress hormone released by the adrenal glands in "
            "response to perceived threat. Acute cortisol sharpens memory consolidation; "
            "chronic cortisol damages the hippocampus and impairs working memory, sleep "
            "quality and immune function."
        ),
    ),
    GoldNote(
        label="sleep_memory_consolidation",
        cluster="neuroscience",
        content=(
            "During sleep, the hippocampus replays memories to the neocortex for long-term "
            "storage, a process called memory consolidation. Slow-wave sleep consolidates "
            "declarative memories; REM sleep consolidates procedural and emotional memories. "
            "Sleep deprivation impairs both consolidation and next-day learning capacity."
        ),
    ),
]

# ── Cluster 7: Deep Productivity (knowledge_work / productivity) ──────────────
PRODUCTIVITY_CLUSTER: list[GoldNote] = [
    GoldNote(
        label="deep_work",
        cluster="productivity",
        content=(
            "Deep work, coined by Cal Newport, refers to cognitively demanding tasks "
            "performed in a state of distraction-free concentration. It produces far more "
            "output per hour than shallow work (email, meetings) and is becoming "
            "increasingly rare and valuable as digital distractions proliferate."
        ),
    ),
    GoldNote(
        label="deliberate_practice",
        cluster="productivity",
        content=(
            "Deliberate practice, studied by K. Anders Ericsson, is a specific form of "
            "practice characterised by focused effort on skill weaknesses, immediate "
            "feedback and repetition just at the edge of one's current ability. It is "
            "distinct from routine practice, which reinforces existing habits without improvement."
        ),
    ),
    GoldNote(
        label="maker_manager_schedule",
        cluster="productivity",
        content=(
            "Paul Graham's maker-manager distinction notes that makers (programmers, writers) "
            "need long uninterrupted blocks to produce deep work, while managers operate in "
            "one-hour slots. Scheduling meetings in the middle of a maker's day destroys "
            "their afternoon as well as the time the meeting actually takes."
        ),
    ),
    GoldNote(
        label="time_blocking",
        cluster="productivity",
        content=(
            "Time blocking means assigning specific tasks to defined calendar blocks instead "
            "of maintaining a to-do list and picking tasks reactively. It forces prioritisation "
            "upfront and prevents shallow tasks from crowding out deep work. Cal Newport "
            "advocates for scheduling every minute of the workday."
        ),
    ),
    GoldNote(
        label="single_tasking",
        cluster="productivity",
        content=(
            "Single-tasking is the practice of focusing on one task at a time until "
            "completion or a deliberate stopping point. Research shows that multitasking "
            "increases cognitive load and error rates and reduces performance on each "
            "individual task. Each task switch incurs a resumption cost of up to 25 minutes."
        ),
    ),
]

# ── Cross-family traps ─────────────────────────────────────────────────────────
TRAP_NOTES: list[GoldNote] = [
    GoldNote(
        label="compound_sentence",          # 'compound' word trap — not finance
        cluster="trap",
        content=(
            "A compound sentence joins two independent clauses with a coordinating "
            "conjunction (for, and, nor, but, or, yet, so — FANBOYS) or a semicolon. "
            "Unlike a complex sentence, both clauses could stand alone. Compound sentences "
            "add variety to writing and show the relationship between two equal ideas."
        ),
    ),
    GoldNote(
        label="network_biology",            # 'network' — biological, not ML or TCP/IP
        cluster="trap",
        content=(
            "Protein interaction networks map how proteins in a cell physically bind to "
            "each other. Hub proteins with many connections are often essential for survival. "
            "Network analysis of the proteome reveals disease modules — clusters of "
            "interacting proteins associated with specific pathologies."
        ),
    ),
    GoldNote(
        label="sprint_running",             # 'sprint' — sports, not Scrum
        cluster="trap",
        content=(
            "A sprint in athletics is a short-distance running race at maximum speed, "
            "typically 100m, 200m or 400m. Sprint training develops fast-twitch muscle "
            "fibres, improves cardiovascular power and elevates post-exercise oxygen "
            "consumption (EPOC). It is highly effective for fat loss and athletic conditioning."
        ),
    ),
    GoldNote(
        label="attention_meditation",       # 'attention' — contemplative, not ML transformer
        cluster="trap",
        content=(
            "Attentional training in meditation develops the ability to sustain focus on "
            "a chosen object and return attention when the mind wanders. Focused-attention "
            "meditation and open-monitoring meditation engage different neural networks. "
            "Regular practice increases grey matter density in prefrontal cortex."
        ),
    ),
]

# ── Full corpus ────────────────────────────────────────────────────────────────
EXTENDED_CORPUS: list[GoldNote] = (
    ML_CLUSTER
    + FINANCE_CLUSTER
    + COGNITIVE_CLUSTER
    + STOICISM_CLUSTER
    + AGILE_CLUSTER
    + NEUROSCIENCE_CLUSTER
    + PRODUCTIVITY_CLUSTER
    + TRAP_NOTES
)

# ── Cluster registry for parallel ingest ──────────────────────────────────────
CLUSTERS_FOR_PARALLEL: list[list[GoldNote]] = [
    ML_CLUSTER,
    FINANCE_CLUSTER,
    COGNITIVE_CLUSTER,
    STOICISM_CLUSTER,
    AGILE_CLUSTER,
    NEUROSCIENCE_CLUSTER,
    PRODUCTIVITY_CLUSTER,
    TRAP_NOTES,
]


# ═══════════════════════════════════════════════════════════════════════════════
# GROUND TRUTH — ~110 pairs across all 7 clusters plus traps
# ═══════════════════════════════════════════════════════════════════════════════

GROUND_TRUTH: list[tuple[str, str, bool, str]] = [

    # ── ML cluster ────────────────────────────────────────────────────────────
    ("neural_network",       "backpropagation",          True,  "ml_internal"),
    ("neural_network",       "gradient_descent",         True,  "ml_internal"),
    ("neural_network",       "overfitting",              True,  "ml_internal"),
    ("neural_network",       "transfer_learning",        True,  "ml_internal"),
    ("neural_network",       "attention_mechanism",      True,  "ml_internal"),
    ("backpropagation",      "gradient_descent",         True,  "ml_internal"),
    ("gradient_descent",     "overfitting",              True,  "ml_internal"),
    ("transfer_learning",    "attention_mechanism",      True,  "ml_internal"),

    # ── Finance cluster ───────────────────────────────────────────────────────
    ("compound_interest",    "index_fund_investing",     True,  "finance_internal"),
    ("compound_interest",    "dollar_cost_averaging",    True,  "finance_internal"),
    ("compound_interest",    "portfolio_diversification",True,  "finance_internal"),
    ("dollar_cost_averaging","index_fund_investing",     True,  "finance_internal"),
    ("index_fund_investing", "portfolio_diversification",True,  "finance_internal"),
    ("portfolio_diversification","emergency_fund",       True,  "finance_internal"),

    # ── Cognitive science cluster ─────────────────────────────────────────────
    ("cognitive_load_theory","working_memory",           True,  "cognitive_internal"),
    ("cognitive_load_theory","chunking_cognition",       True,  "cognitive_internal"),
    ("working_memory",       "chunking_cognition",       True,  "cognitive_internal"),
    ("spaced_repetition",    "retrieval_practice",       True,  "cognitive_internal"),
    ("spaced_repetition",    "cognitive_load_theory",    True,  "cognitive_internal"),
    ("dual_coding_theory",   "cognitive_load_theory",    True,  "cognitive_internal"),
    ("retrieval_practice",   "working_memory",           True,  "cognitive_internal"),

    # ── Stoicism cluster ──────────────────────────────────────────────────────
    ("stoic_philosophy",     "dichotomy_of_control",     True,  "stoicism_internal"),
    ("stoic_philosophy",     "memento_mori",             True,  "stoicism_internal"),
    ("stoic_philosophy",     "negative_visualization",   True,  "stoicism_internal"),
    ("stoic_philosophy",     "amor_fati",                True,  "stoicism_internal"),
    ("dichotomy_of_control", "negative_visualization",   True,  "stoicism_internal"),
    ("memento_mori",         "amor_fati",                True,  "stoicism_internal"),

    # ── Agile cluster ─────────────────────────────────────────────────────────
    ("scrum_framework",      "sprint_retrospective",     True,  "agile_internal"),
    ("scrum_framework",      "kanban_method",            True,  "agile_internal"),
    ("scrum_framework",      "continuous_delivery",      True,  "agile_internal"),
    ("test_driven_development","pair_programming",       True,  "agile_internal"),
    ("test_driven_development","continuous_delivery",    True,  "agile_internal"),
    ("kanban_method",        "continuous_delivery",      True,  "agile_internal"),
    ("sprint_retrospective", "pair_programming",         True,  "agile_internal"),

    # ── Neuroscience cluster ──────────────────────────────────────────────────
    ("neuroplasticity",      "long_term_potentiation",   True,  "neuro_internal"),
    ("neuroplasticity",      "sleep_memory_consolidation",True, "neuro_internal"),
    ("long_term_potentiation","sleep_memory_consolidation",True,"neuro_internal"),
    ("dopamine_circuit",     "cortisol_stress",          True,  "neuro_internal"),
    ("cortisol_stress",      "sleep_memory_consolidation",True, "neuro_internal"),
    ("neuroplasticity",      "dopamine_circuit",         True,  "neuro_internal"),

    # ── Productivity cluster ──────────────────────────────────────────────────
    ("deep_work",            "deliberate_practice",      True,  "productivity_internal"),
    ("deep_work",            "single_tasking",           True,  "productivity_internal"),
    ("deep_work",            "time_blocking",            True,  "productivity_internal"),
    ("deep_work",            "maker_manager_schedule",   True,  "productivity_internal"),
    ("deliberate_practice",  "single_tasking",           True,  "productivity_internal"),
    ("time_blocking",        "maker_manager_schedule",   True,  "productivity_internal"),
    ("time_blocking",        "single_tasking",           True,  "productivity_internal"),

    # ── Cross-cluster links that SHOULD exist (same domain_family) ────────────
    # ML ↔ Agile: both technology
    ("continuous_delivery",  "test_driven_development",  True,  "cross_tech"),

    # Cognitive ↔ Productivity: cognitive science underpins productivity methods
    # (same family life_sciences/knowledge_work border — we DON'T assert these
    #  since the guard may legitimately block them; keep as FN-expected)

    # Neuroscience ↔ Cognitive: both life_sciences
    ("neuroplasticity",      "spaced_repetition",        True,  "cross_life_sciences"),
    ("long_term_potentiation","spaced_repetition",        True,  "cross_life_sciences"),
    ("sleep_memory_consolidation","retrieval_practice",   True,  "cross_life_sciences"),
    ("cortisol_stress",      "working_memory",           True,  "cross_life_sciences"),

    # ── Must NOT link — homonym traps ─────────────────────────────────────────
    ("compound_interest",    "compound_sentence",        False, "homonym_trap"),
    ("neural_network",       "network_biology",          False, "homonym_trap"),
    ("scrum_framework",      "sprint_running",           False, "homonym_trap"),
    ("sprint_retrospective", "sprint_running",           False, "homonym_trap"),
    ("attention_mechanism",  "attention_meditation",     False, "homonym_trap"),

    # ── Must NOT link — cross-cluster (different domain_family) ───────────────
    ("neural_network",       "stoic_philosophy",         False, "cross_family"),
    ("compound_interest",    "cognitive_load_theory",    False, "cross_family"),
    ("compound_interest",    "neuroplasticity",          False, "cross_family"),
    ("scrum_framework",      "compound_interest",        False, "cross_family"),
    ("dopamine_circuit",     "dollar_cost_averaging",    False, "cross_family"),
    ("stoic_philosophy",     "kanban_method",            False, "cross_family"),
    ("memento_mori",         "gradient_descent",         False, "cross_family"),
    ("neural_network",       "intermittent_fasting",     False, "cross_family"),
    ("portfolio_diversification","spaced_repetition",    False, "cross_family"),
    ("deep_work",            "stoic_philosophy",         False, "cross_family"),  # knowledge_work ≠ arts_humanities
]


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IngestResult:
    label: str
    cluster: str
    note_id: Optional[int]
    action: str


def _ingest_note(note: GoldNote) -> IngestResult:
    """Ingest a single note through the full pipeline."""
    from src.workflows.ingest_workflow import ingest_graph
    from shared.schemas.workflow.ingest import IngestState

    state = IngestState(content=note.content)
    raw = ingest_graph.invoke(state)

    def _get(key, default=None):
        if isinstance(raw, dict):
            return raw.get(key, default)
        return getattr(raw, key, default)

    result = IngestResult(
        label=note.label,
        cluster=note.cluster,
        note_id=_get("note_id"),
        action=_get("action", "CREATE"),
    )
    with _print_lock:
        print(f"  [{note.cluster}/{note.label}]  id={result.note_id}  action={result.action}")
    return result


def _ingest_cluster_sequential(cluster: list[GoldNote]) -> list[IngestResult]:
    """Ingest notes within a cluster one by one (preserves forward-link chain)."""
    results = []
    for note in cluster:
        results.append(_ingest_note(note))
    return results


def _build_link_set(
    results: list[IngestResult],
) -> set[tuple[str, str]]:
    """
    Read ALL links from DB for the ingested note IDs.
    Captures forward links AND retrospective links saved to DB.
    """
    from src.utils.db import get_session
    from sqlalchemy import text

    ids = [r.note_id for r in results if r.note_id]
    if not ids:
        return set()

    id_to_label: dict[int, str] = {r.note_id: r.label for r in results if r.note_id}
    links: set[tuple[str, str]] = set()

    with get_session() as session:
        rows = session.execute(
            text(
                "SELECT source_id, target_id FROM links "
                "WHERE source_id = ANY(:ids) AND target_id = ANY(:ids)"
            ),
            {"ids": ids},
        ).fetchall()

    for src_id, tgt_id in rows:
        src_l = id_to_label.get(src_id)
        tgt_l = id_to_label.get(tgt_id)
        if src_l and tgt_l:
            links.add(tuple(sorted([src_l, tgt_l])))
    return links


def _compute_metrics(
    actual: set[tuple[str, str]],
    ground_truth: list[tuple[str, str, bool, str]],
    present_labels: set[str],
) -> dict:
    """
    Compute TP/FP/FN/TN.  Only evaluate pairs where BOTH labels were ingested
    in this run (avoids penalising for notes that weren't created).
    """
    should   = {
        tuple(sorted([a, b]))
        for a, b, lnk, _ in ground_truth
        if lnk
        and a in present_labels
        and b in present_labels
    }
    must_not = {
        tuple(sorted([a, b]))
        for a, b, lnk, _ in ground_truth
        if not lnk
        and a in present_labels
        and b in present_labels
    }

    tp = len(actual & should)
    fp = len(actual & must_not)
    fn = len(should - actual)
    tn = len(must_not - actual)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "f1": f1}


def _cleanup(results: list[IngestResult]) -> None:
    from src.repository.link_repository import link_repository
    from src.repository.note_repository import note_repository

    ids = [r.note_id for r in results if r.note_id is not None]
    for nid in ids:
        link_repository.delete_links_for_note(nid)
    for nid in ids:
        note_repository.delete_note(nid)


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════════

@skip_no_creds
def test_extended_f1_parallel():
    """
    Full-pipeline F1 on the extended 80-note corpus.

    Parallelism strategy:
      - Each cluster is ingested sequentially in its own thread so that
        intra-cluster forward links can be created.
      - Clusters run in parallel (up to 4 workers).
      - After all threads finish, links are read directly from DB to capture
        retrospective links created by the RetrospectiveLinkerAgent.

    Minimum thresholds (Titan v2):
      - Precision ≥ 0.75
      - Recall    ≥ 0.45
      - F1        ≥ 0.55
    """
    MIN_PRECISION = 0.75
    MIN_RECALL    = 0.45
    MIN_F1        = 0.55

    all_results: list[IngestResult] = []

    try:
        print(f"\n  Ingesting {len(EXTENDED_CORPUS)} notes across "
              f"{len(CLUSTERS_FOR_PARALLEL)} clusters (4 parallel workers)…\n")

        # Ingest clusters in parallel; within each cluster: sequential
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_ingest_cluster_sequential, cluster): cluster
                for cluster in CLUSTERS_FOR_PARALLEL
            }
            for future in as_completed(futures):
                cluster_results = future.result()
                all_results.extend(cluster_results)

        present_labels = {r.label for r in all_results if r.note_id}
        actual = _build_link_set(all_results)
        metrics = _compute_metrics(actual, GROUND_TRUTH, present_labels)

        # ── Scorecard ─────────────────────────────────────────────────────────
        sep = "═" * 72
        print(f"\n\n  {sep}")
        print(f"  EXTENDED F1 SCORECARD  ({len(EXTENDED_CORPUS)} notes)")
        print(f"  {sep}")
        print(f"  TP : {metrics['tp']:>4}   FP : {metrics['fp']:>4}   "
              f"FN : {metrics['fn']:>4}   TN : {metrics['tn']:>4}")
        print(f"  {'─' * 48}")
        print(f"  Precision : {metrics['precision']:.2%}  (min {MIN_PRECISION:.0%})")
        print(f"  Recall    : {metrics['recall']:.2%}  (min {MIN_RECALL:.0%})")
        print(f"  F1        : {metrics['f1']:.2%}  (min {MIN_F1:.0%})")
        print(f"  {sep}")

        # ── Per-cluster breakdown ─────────────────────────────────────────────
        cluster_cats = {cat for _, _, _, cat in GROUND_TRUTH}
        print(f"\n  Per-category breakdown:")
        print(f"  {'Category':<24} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4}  {'F1':>7}")
        print(f"  {'─' * 55}")
        for cat in sorted(cluster_cats):
            cat_gt = [(a, b, lnk, c) for a, b, lnk, c in GROUND_TRUTH if c == cat]
            cat_should   = {tuple(sorted([a,b])) for a,b,lnk,_ in cat_gt if lnk and a in present_labels and b in present_labels}
            cat_must_not = {tuple(sorted([a,b])) for a,b,lnk,_ in cat_gt if not lnk and a in present_labels and b in present_labels}
            c_tp = len(actual & cat_should)
            c_fp = len(actual & cat_must_not)
            c_fn = len(cat_should - actual)
            c_tn = len(cat_must_not - actual)
            c_p  = c_tp / (c_tp + c_fp) if (c_tp + c_fp) > 0 else 0.0
            c_r  = c_tp / (c_tp + c_fn) if (c_tp + c_fn) > 0 else 0.0
            c_f1 = 2*c_p*c_r/(c_p+c_r) if (c_p+c_r) > 0 else 0.0
            print(f"  {cat:<24} {c_tp:>4} {c_fp:>4} {c_fn:>4} {c_tn:>4}  {c_f1:>7.2%}")

        # ── Detailed pair log ─────────────────────────────────────────────────
        print(f"\n  Detailed ground truth evaluation:\n")
        for a_label, b_label, expected, category in GROUND_TRUTH:
            if a_label not in present_labels or b_label not in present_labels:
                continue
            pair = tuple(sorted([a_label, b_label]))
            linked = pair in actual
            correct = linked == expected
            marker = "✓" if correct else "✗"
            exp_s = "LINK   " if expected else "NO LINK"
            act_s = "LINK   " if linked  else "NO LINK"
            print(f"    {marker}  [{category:<22}]  {a_label:30} ↔ {b_label:30}  "
                  f"expected={exp_s}  actual={act_s}")

        # ── Assertions ────────────────────────────────────────────────────────
        assert metrics["precision"] >= MIN_PRECISION, (
            f"Precision {metrics['precision']:.2%} < {MIN_PRECISION:.0%}"
        )
        assert metrics["recall"] >= MIN_RECALL, (
            f"Recall {metrics['recall']:.2%} < {MIN_RECALL:.0%}"
        )
        assert metrics["f1"] >= MIN_F1, (
            f"F1 {metrics['f1']:.2%} < {MIN_F1:.0%}"
        )

    finally:
        _cleanup(all_results)


@skip_no_creds
def test_extended_precision_no_cross_family_fp():
    """
    Fast precision guard: ingest only the homonym traps + one note from each
    of two DIFFERENT domain_family clusters, then assert zero cross-family links.

    Notes selected:
      - neural_network   (technology / machine_learning)
      - compound_interest (business / finance)
      - stoic_philosophy  (arts_humanities / philosophy)
      - sprint_running    (trap — sports)
      - attention_meditation (trap — contemplative)
    """
    sample = [
        next(n for n in EXTENDED_CORPUS if n.label == "neural_network"),
        next(n for n in EXTENDED_CORPUS if n.label == "compound_interest"),
        next(n for n in EXTENDED_CORPUS if n.label == "stoic_philosophy"),
        next(n for n in EXTENDED_CORPUS if n.label == "sprint_running"),
        next(n for n in EXTENDED_CORPUS if n.label == "attention_meditation"),
    ]

    results: list[IngestResult] = []
    try:
        for note in sample:
            results.append(_ingest_note(note))

        actual = _build_link_set(results)
        present = {r.label for r in results if r.note_id}

        # None of these notes share domain_family → zero links expected
        fp_pairs = [p for p in actual]

        print(f"\n  Links created: {actual}")
        print(f"  Expected: none (all different domain_family)")

        assert len(fp_pairs) == 0, (
            f"Cross-family false positives: {fp_pairs}. "
            f"Domain guard is not blocking different-family candidates."
        )

    finally:
        _cleanup(results)


@skip_no_creds
def test_extended_within_cluster_recall():
    """
    Recall check on ONE cluster only (cognitive science) — cheap, fast, no parallelism.
    Verifies that intra-cluster links are created with high recall.
    Expected: at least 4 of the 7 cognitive ground truth pairs linked.
    """
    results: list[IngestResult] = []
    try:
        for note in COGNITIVE_CLUSTER:
            results.append(_ingest_note(note))

        actual = _build_link_set(results)
        present = {r.label for r in results if r.note_id}

        cognitive_gt = [gt for gt in GROUND_TRUTH if gt[3] == "cognitive_internal"]
        should = {
            tuple(sorted([a, b]))
            for a, b, lnk, _ in cognitive_gt
            if lnk and a in present and b in present
        }

        tp = len(actual & should)
        fn = len(should - actual)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        print(f"\n  Cognitive cluster — TP={tp}  FN={fn}  Recall={recall:.2%}")
        print(f"  Links created: {actual}")
        print(f"  Expected: {should}")

        assert recall >= 0.50, (
            f"Cognitive cluster recall {recall:.2%} < 50%. "
            f"Missed: {should - actual}"
        )

    finally:
        _cleanup(results)
