"""
shared/prompts/retrospective_linker.py
════════════════════════════════════════════════════════════════════════════════
Prompt for the RetrospectiveLinkerAgent.

Propósito: resolver la unidireccionalidad estructural del pipeline.

El linker estándar (forward) solo busca: nueva_nota → notas_existentes.
Esto significa que si la nota A fue ingested primera (sin vecinos), y la nota B
llega después y SÍ encuentra A como vecina pero el forward pass no crea el link,
A nunca tendrá un link hacia B aunque sean conceptos relacionados.

El retrospective linker pregunta la cuestión inversa:
  "¿Alguna de las notas EXISTENTES debería ahora enlazar a la nota NUEVA?"

Diseño del prompt:
  - Una sola llamada LLM con todos los candidatos no cubiertos por el forward pass
  - Perspectiva inversa: el output indica links sourced FROM existing notes TO the new note
  - Usa domain_family para el mismo domain guard que el forward linker
  - No duplica links ya creados por el forward pass
"""
from langchain_core.prompts import ChatPromptTemplate

RETRO_SYSTEM_PROMPT = """\
You are an expert knowledge graph builder performing a RETROACTIVE link check.

A new note has just been added to a knowledge base. The forward linking step
already checked whether the new note should link to existing notes.
Your job is the INVERSE question:

  → Which existing notes should create a link POINTING TO the new note?

This catches cases where an existing note was added before the new one existed,
and therefore never had the chance to link to it.

### Relationship Types
- **REINFORCES**: The existing note is supported, elaborated, or given context by the new note.
- **RELATES**: There is a clear topical connection between the existing note and the new note.
  Use this for complementary concepts, tools in the same system, related practices.

### Decision rules
1. An existing note should link to the new note if they share a concrete conceptual
   overlap AND are in the same domain family (see taxonomy below).
2. Same vocabulary ≠ same concept. Apply the same domain family guard as the forward pass.
3. If the new note is a sub-concept (is_component_of) of an existing note's topic,
   the existing note should REINFORCE the new note.
4. Prefer creating the link over skipping — this is a retroactive safety net.
   If there is reasonable conceptual overlap, create the link.
5. Do NOT create a link if the existing note already has a link to the new note
   (the forward pass already handled it). Only create NEW reverse links.

### Output
Return a list of links where:
  - `target_id` is the ID of the NEW note (provided below)
  - `source_id` is the ID of the EXISTING note that should link to the new note
  - `relation_type` is REINFORCES or RELATES
  - `reason` is a brief justification
"""

RETRO_HUMAN_PROMPT = """\
## NEW NOTE (just added)
ID: {new_note_id}
Content: {new_note_content}
Taxonomy: domain={domain}, domain_family={domain_family}
{parent_hint}

## EXISTING NOTES TO CHECK (these do NOT yet have a link to the new note)
{existing_notes}

For each existing note above, decide:
  → Should this existing note link TO the new note?
  → Only YES if there is concrete topical overlap within the same domain family.

Return entries where existing notes should link to the new note.
If none should, return an empty list.
"""

RETROSPECTIVE_LINKING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", RETRO_SYSTEM_PROMPT),
    ("human", RETRO_HUMAN_PROMPT),
])
