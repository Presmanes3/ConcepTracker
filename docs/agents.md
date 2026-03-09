# Agents

Each agent in `src/agents/` is a LangGraph node: a class that accepts a typed state
object, calls the LLM via `BaseAgent._call_llm()`, and returns a partial state dict.
All agents inherit from `src/agents/base_agent.py`.

---

## NormalizerAgent

Cleans raw content and generates a summary, tags, and language detection.

**File:** `src/agents/normalizer_agent.py`  
**Task name:** `normalization`  
**State:** `IngestState`

**Input fields consumed**

| Field | Description |
|---|---|
| content | Raw note text |
| source_type | Origin category used as prompt context |
| source_url | Optional URI, included in prompt |
| tags | Pre-existing tags (passed as context) |

**Output fields produced**

| Field | Description |
|---|---|
| content | Sanitised Markdown content |
| summary | 2–3 sentence summary of the core idea |
| tags | Comma-separated normalised tags |
| language | ISO 639-1 code of detected language |
| original_content | Original text preserved for traceability |

**Structured output:** `LLMNormalizerOutput`

---

## ConceptTaxonomyAgent

Classifies a note into a semantic taxonomy before retrieval. Runs as a lightweight
pre-processing step so the Gatekeeper and Linker can use domain as a hard guard.

**File:** `src/agents/taxonomy_agent.py`  
**Task name:** `taxonomy_classification`  
**State:** `IngestState`

**Input fields consumed**

| Field | Description |
|---|---|
| content | Note text to classify |

**Output fields produced**

| Field | Description |
|---|---|
| taxonomy | `ConceptTaxonomy` object, or `None` on failure |

`ConceptTaxonomy` fields:

| Field | Type | Description |
|---|---|---|
| concept_name | string | Short canonical name (max 6 words) |
| concept_type | string | One of: methodology, tool, principle, practice, phenomenon, theory, technique, data, person, other |
| domain | string | Specific subject area (free text) |
| domain_family | string | Broad family: technology, knowledge_work, life_sciences, business, arts_humanities, or other |
| is_component_of | string \| null | Parent concept if this note describes a sub-component |

Falls back to `{"taxonomy": None}` on any exception; downstream agents handle `None` gracefully.

---

## GatekeeperAgent

Decides whether an incoming note is new (`CREATE`), an update to an existing one
(`MERGE`), or a duplicate (`SKIP`).

**File:** `src/agents/gatekeeper_agent.py`  
**Task name:** `gatekeeping`  
**State:** `IngestState`

**Input fields consumed**

| Field | Description |
|---|---|
| content | Normalised note text |
| similar_notes | Candidate notes from dedup search |
| summary | LLM summary from normalisation |
| taxonomy | Semantic fingerprint (domain guard) |

**Output fields produced**

| Field | Description |
|---|---|
| action | `CREATE`, `MERGE`, or `SKIP` |
| note_id | Existing note ID if MERGE or SKIP |
| reasoning | LLM justification text |
| summary | Synthesised summary (MERGE) or passthrough (CREATE) |

**Structured output:** `GatekeeperResult`

Domain guard: if `taxonomy.domain` of the new note differs from a candidate, the
Gatekeeper always selects CREATE regardless of vector similarity.

---

## BidirectionalLinkerAgent

Determines semantic relationships between the newly ingested note and its neighbours,
producing both forward and backward links in a single LLM call.

**File:** `src/agents/bidirectional_linker_agent.py`  
**Task name:** `bidirectional_linking`  
**State:** `IngestState`

**Confidence tiers (pre-LLM)**

| Tier | Score range | Action |
|---|---|---|
| AUTO-LINK | ≥ 0.90 | Linked without LLM call |
| LLM | [0.25, 0.90) | Single batched LLM call |
| DROP | < 0.25 (below NEAR_MISS_MIN) | Discarded silently |
| Near-miss | [NEAR_MISS_MIN, SEND_TO_LLM_LOW) | Surfaced for `--review` |

**Input fields consumed**

| Field | Description |
|---|---|
| similar_notes | Candidates enriched with `link_confidence` scores |
| note_id | ID of the newly saved note |
| taxonomy | Domain fingerprint for cross-domain guard |

**Output fields produced**

| Field | Description |
|---|---|
| links | List of `LinkItem` (FORWARD and BACKWARD combined) |
| retrospective_links | Always `[]` (kept for schema compatibility) |
| near_miss_candidates | Candidates rejected before or by the LLM |

**Structured output:** `LinkerResult`

`LinkItem.direction`:
- `FORWARD` — new note → existing note
- `BACKWARD` — existing note → new note (`source_id` must be set)

---

## QueryExpansionAgent

Generates N alternative phrasings of the user query for multi-branch retrieval.

**File:** `src/agents/query_expansion_agent.py`  
**Task name:** `query_expansion`  
**State:** `SearchState`

**Constructor parameter**

| Parameter | Type | Default | Description |
|---|---|---|---|
| expansion_count | int | 2 | Number of alternative queries to generate |

**Input fields consumed**

| Field | Description |
|---|---|
| query | Original user search query |

**Output fields produced**

| Field | Description |
|---|---|
| expanded_queries | List of alternative query strings |

---

## SpeechCleanerAgent

Removes filler words, stutters, and false starts from raw transcription text without
changing the semantic content.

**File:** `src/agents/speech_cleaner_agent.py`  
**Task name:** `speech_cleaner`  
**State:** `TranscriptionEnhancementState`

**Input:** `state["current_text"]`  
**Output:** cleaned `current_text`, `"speech_cleaner"` appended to `applied_layers`.

---

## MarkdownFormatterAgent

Structures cleaned transcription text into readable Markdown.

**File:** `src/agents/markdown_formatter_agent.py`  
**Task name:** `markdown_formatter`  
**State:** `TranscriptionEnhancementState`

**Input:** `state["current_text"]`  
**Output:** formatted `current_text`, `"markdown_formatter"` appended to `applied_layers`.

---

## GeoNamerAgent

Names geographic entities (Archipelagos and Continents) using Amazon Nova Micro.
Always uses model `eu.amazon.nova-micro-v1:0` regardless of the active model setting.

**File:** `src/agents/geo_namer_agent.py`  
**Task name:** `geo_naming`

`run()` raises `NotImplementedError`. Use the dedicated interface:

```python
agent = GeoNamerAgent()
result: GeoNamerOutput = agent.name(prompt_template, **format_kwargs)
```

**Output:** `GeoNamerOutput` with `name` (string) and `summary` (string).
