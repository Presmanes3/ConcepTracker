"""
ground_truth.py
───────────────
Canonical test data for ConcepTracker's linker and geo precision tests.

Design decisions:
  - Pairs chosen to have unambiguous semantic relationships or lack thereof.
  - Written in a PKM (Personal Knowledge Management) domain so they match the
    system prompt's framing exactly.
  - Geo sequence engineered to exercise the accumulative MIN_ISLANDS=2 rule.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


RelationLabel = Literal["REINFORCES", "CONTRADICTS", "RELATES", "NO_LINK"]


@dataclass(frozen=True)
class NotePair:
    """A pair of notes with the expected linker decision."""
    note_a: str          # full content of note A
    note_b: str          # full content of note B
    summary_a: str       # short summary (used in linker prompt)
    summary_b: str
    expected: RelationLabel
    rationale: str       # human explanation of why


# ── Pairs that SHOULD produce a link ─────────────────────────────────────────

SHOULD_LINK: list[NotePair] = [
    NotePair(
        note_a="Zettelkasten is a note-taking method where every note is a single atomic idea, linked to other notes by explicit references.",
        note_b="Evergreen notes are notes written to be reused indefinitely; they age well because they capture one concept per note and link to related ideas.",
        summary_a="Zettelkasten: atomic notes with explicit links.",
        summary_b="Evergreen notes: reusable single-concept notes linked to related ideas.",
        expected="REINFORCES",
        rationale="Both describe the same atomic-note philosophy; one reinforces the other.",
    ),
    NotePair(
        note_a="Spaced repetition exploits the forgetting curve by scheduling reviews at increasing intervals to maximise long-term retention.",
        note_b="Active recall is the practice of retrieving information from memory rather than re-reading, which strengthens the memory trace.",
        summary_a="Spaced repetition: scheduling reviews to fight the forgetting curve.",
        summary_b="Active recall: retrieving from memory to strengthen retention.",
        expected="REINFORCES",
        rationale="Both are evidence-based memory techniques that complement each other.",
    ),
    NotePair(
        note_a="The map is not the territory — mental models are simplifications of reality and can mislead us when we confuse the model with the real system.",
        note_b="Second-order thinking requires considering the consequences of consequences, not just the immediate effect of an action.",
        summary_a="Map vs territory: models are simplifications that can mislead.",
        summary_b="Second-order thinking: consider downstream consequences, not just direct effects.",
        expected="RELATES",
        rationale="Both are meta-cognitive frameworks for clearer reasoning; topically related.",
    ),
    NotePair(
        note_a="Inbox zero is a workflow where you process every email in your inbox, deciding immediately whether to archive, delegate, or act.",
        note_b="GTD (Getting Things Done) is a productivity system that externalises tasks into a trusted system so your mind can focus on doing, not remembering.",
        summary_a="Inbox zero: process every email with immediate decision.",
        summary_b="GTD: externalise tasks so the mind can focus on execution.",
        expected="RELATES",
        rationale="Both are personal productivity workflows that reduce cognitive load.",
    ),
    NotePair(
        note_a="Premature optimisation is the root of all evil — optimising before profiling introduces complexity without guaranteed benefit.",
        note_b="YAGNI (You Aren't Gonna Need It) advises against implementing features until they are actually required.",
        summary_a="Premature optimisation: don't optimise without evidence of need.",
        summary_b="YAGNI: don't implement features before they're required.",
        expected="REINFORCES",
        rationale="Both caution against adding unnecessary complexity too early.",
    ),
]


# ── Pairs that SHOULD NOT produce a link ─────────────────────────────────────

SHOULD_NOT_LINK: list[NotePair] = [
    NotePair(
        note_a="The French Revolution began in 1789 and led to the abolition of the monarchy and the rise of Napoleon Bonaparte.",
        note_b="Sourdough bread fermentation depends on wild yeast and lactic acid bacteria; hydration ratio determines crumb texture.",
        summary_a="French Revolution: abolished monarchy, 1789.",
        summary_b="Sourdough fermentation: wild yeast + bacteria; hydration affects crumb.",
        expected="NO_LINK",
        rationale="History and bread-making share no meaningful semantic connection.",
    ),
    NotePair(
        note_a="The Pythagorean theorem states that in a right triangle, the square of the hypotenuse equals the sum of squares of the other two sides.",
        note_b="Jazz improvisation is based on playing over chord changes by internalising scales and learning to hear the harmonic movement.",
        summary_a="Pythagorean theorem: a² + b² = c².",
        summary_b="Jazz improvisation: scales over chord changes.",
        expected="NO_LINK",
        rationale="Geometry and jazz performance are entirely unrelated domains.",
    ),
    NotePair(
        note_a="Containerisation with Docker packages an application and its dependencies into a portable image that runs consistently across environments.",
        note_b="The Roman aqueduct system transported water over hundreds of kilometres using gravity, arches, and precise gradients.",
        summary_a="Docker containers: portable, consistent application images.",
        summary_b="Roman aqueducts: long-distance water transport via gravity and arches.",
        expected="NO_LINK",
        rationale="DevOps tooling and ancient civil engineering have no conceptual overlap.",
    ),
    NotePair(
        note_a="Intermittent fasting is an eating pattern where calorie intake is restricted to specific windows of time during the day.",
        note_b="Tidal locking occurs when a body's orbital period equals its rotational period, as with the Moon relative to Earth.",
        summary_a="Intermittent fasting: time-restricted calorie intake.",
        summary_b="Tidal locking: orbital and rotational period synchronisation.",
        expected="NO_LINK",
        rationale="Nutrition practice and orbital mechanics are completely unrelated.",
    ),
    NotePair(
        note_a="Watercolour is a painting medium where pigments are dissolved in water and applied in transparent washes, building depth through layering.",
        note_b="The TCP/IP model defines four layers of network communication: link, internet, transport, and application.",
        summary_a="Watercolour: transparent washes built up in layers.",
        summary_b="TCP/IP model: four network communication layers.",
        expected="NO_LINK",
        rationale="Fine arts and computer networking have no substantive relationship.",
    ),
]


# ── Geo accumulation sequence ─────────────────────────────────────────────────
# Designed to exercise MIN_ISLANDS=2 + JOIN logic in geo_router.
#
# Sequence:
#   Note 1: "Atomic notes"                      → no links yet → geo: NONE
#   Note 2: "Evergreen notes"  links→ Note 1    → both unassigned (2 islands) → geo: CREATE "PKM Philosophy"
#   Note 3: "Zettelkasten"     links→ Note 1,2  → linked notes are in PKM Philosophy → geo: JOIN
#   Note 4: "Docker containers" (unrelated)     → no links → geo: NONE
#
# After note 3: all three notes are in "PKM Philosophy" archipelago.
# After note 4: note 4 is unassigned; no archipelago for it.

@dataclass(frozen=True)
class GeoNote:
    content: str
    summary: str
    tags: str


GEO_SEQUENCE: list[GeoNote] = [
    GeoNote(
        content="Atomic notes capture a single idea per note. Each note should be self-contained and meaningful without context.",
        summary="Atomic notes: one idea per note, self-contained.",
        tags="pkm,atomic-notes",
    ),
    GeoNote(
        content="Evergreen notes are designed to accumulate insights over time. Unlike fleeting notes, they are rewritten and refined.",
        summary="Evergreen notes: refined, long-lived knowledge artefacts.",
        tags="pkm,evergreen",
    ),
    GeoNote(
        content="Zettelkasten connects notes through explicit links rather than hierarchical folders, creating an emergent web of knowledge.",
        summary="Zettelkasten: emergent knowledge web via explicit note links.",
        tags="pkm,zettelkasten",
    ),
    GeoNote(
        content="Docker containers package an application and its runtime dependencies into a portable, reproducible image.",
        summary="Docker containers: portable, reproducible application packaging.",
        tags="devops,docker",
    ),
]

# Expected geo outcomes after ingesting each note in sequence
# (assuming a clean DB before the run)
GEO_EXPECTED_OUTCOMES = [
    {"action": "NONE",   "archipelago_name": None},           # Note 1: no links
    {"action": "CREATE", "archipelago_name_contains": "PKM"}, # Note 2: 2 unassigned islands
    {"action": "JOIN",   "archipelago_name_contains": None},  # Note 3: joins existing
    {"action": "NONE",   "archipelago_name": None},           # Note 4: unrelated
]
