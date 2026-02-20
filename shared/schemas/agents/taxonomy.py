"""
shared/schemas/agents/taxonomy.py
──────────────────────────────────
Structured output schema for the ConceptTaxonomyAgent.

Purpose: extract a semantic fingerprint from a note before any retrieval
happens. The taxonomy acts as HARD SIGNAL for downstream agents:

  • Gatekeeper: notes from different domains → always CREATE (never MERGE)
  • Gatekeeper: is_component_of set → always CREATE (sub-concept ≠ parent)
  • Linker: domain guard prevents cross-domain false positives
"""
from typing import Literal, Optional  # Literal kept only for domain_family (critical guard)
from pydantic import BaseModel, Field


# concept_type is free-form str to avoid Pydantic validation failures when the LLM
# produces an unexpected value. Downstream agents do NOT use concept_type as a
# hard signal — only domain_family (Literal) matters for guards.
# Suggested values (not enforced): methodology | tool | principle | practice |
# phenomenon | theory | technique | data | person | other
CONCEPT_TYPE_HINT = (
    "methodology | tool | principle | practice | phenomenon "
    "| theory | technique | data | person | other"
)

DOMAIN_FAMILIES = Literal[
    "technology",      # devops, software_engineering, machine_learning, data_science
    "knowledge_work",  # pkm, productivity, writing, research
    "life_sciences",   # nutrition, biology, psychology, medicine
    "business",        # finance, management, marketing
    "arts_humanities", # history, philosophy, literature, art
    "other",
]


class ConceptTaxonomy(BaseModel):
    """
    Semantic fingerprint of a note, extracted before DB retrieval.
    Used as hard signals by the Gatekeeper and Linker agents.
    """

    concept_name: str = Field(
        ...,
        description=(
            "Short, canonical name of the primary concept (e.g. 'Zettelkasten method', "
            "'Docker container', 'intermittent fasting'). Max 6 words."
        ),
    )

    concept_type: str = Field(
        ...,
        description=(
            "Type category of the concept. Use one of: "
            "methodology | tool | principle | practice | phenomenon "
            "| theory | technique | data | person | other."
        ),
    )

    domain: str = Field(
        ...,
        description=(
            "Primary knowledge domain as a lowercase slug. Use consistent names: "
            "'pkm' (personal knowledge management), 'devops', 'nutrition', "
            "'psychology', 'machine_learning', 'software_engineering', "
            "'finance', 'biology', 'history', etc. Be specific: prefer 'devops' "
            "over 'technology', 'nutrition' over 'science'."
        ),
    )

    domain_family: DOMAIN_FAMILIES = Field(  # type: ignore[valid-type]
        ...,
        description=(
            "Coarse domain family. Maps domain slugs: "
            "technology (devops, software_engineering, machine_learning, data_science, cloud); "
            "knowledge_work (pkm, productivity, writing, research, education); "
            "life_sciences (nutrition, biology, psychology, medicine, neuroscience); "
            "business (finance, management, marketing, economics); "
            "arts_humanities (history, philosophy, literature, art, music)."
        ),
    )

    sub_domain: Optional[str] = Field(
        None,
        description=(
            "More specific sub-domain (e.g. 'note_taking', 'container_orchestration', "
            "'metabolic_health'). Optional."
        ),
    )

    is_component_of: Optional[str] = Field(
        None,
        description=(
            "If this concept is a sub-concept, component, or specialisation of a "
            "larger concept, name that parent concept here. "
            "Examples: 'atomic notes' → is_component_of='Zettelkasten'; "
            "'Kubernetes pods' → is_component_of='Kubernetes'. "
            "Leave null if the concept stands on its own."
        ),
    )
