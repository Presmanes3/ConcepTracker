# Schemas

This document covers the key shared Pydantic schemas used as the HTTP wire format
(`shared/schemas/api/`) and the LangGraph workflow state models
(`shared/schemas/workflow/`). Agent I/O schemas are documented in
[agents.md](agents.md).

---

## API Schemas (`shared/schemas/api/`)

### NoteIngestRequest

| Field | Type | Required | Description |
|---|---|---|---|
| content | string | yes | Raw text or source content to ingest |
| source_type | string | no | Origin category: `manual`, `web`, `pdf`, `transcription` (default `manual`) |
| source_url | string | no | Optional URI or file path of the source |

---

### NoteIngestResponse

| Field | Type | Description |
|---|---|---|
| note_id | int \| null | ID of the created or merged note |
| action | string | `CREATE`, `MERGE`, or `SKIP` |
| reasoning | string \| null | LLM justification |
| near_miss_candidates | NearMissCandidate[] | Similar notes surfaced during deduplication |

---

### NearMissCandidate

| Field | Type | Description |
|---|---|---|
| note_id | int | Candidate note identifier |
| score | float | Similarity score (0.0–1.0) |
| summary | string | Candidate summary |
| tags | string \| null | Candidate tags |
| domain | string \| null | Candidate domain |

---

### NoteResponse

| Field | Type | Description |
|---|---|---|
| id | int | Primary identifier |
| content | string | Full note text |
| summary | string | LLM-generated summary |
| tags | string \| null | Comma-separated tags |
| created_at | datetime | Creation timestamp (UTC) |
| domain | string \| null | Primary subject area |
| domain_family | string \| null | Broader domain grouping |
| archipelago_id | int \| null | Parent archipelago ID |

---

### NoteUpdateRequest

| Field | Type | Description |
|---|---|---|
| content | string \| null | Replacement text content |
| summary | string \| null | Manual summary override |
| tags | string \| null | Updated tags |

---

### NoteEnhanceRequest

| Field | Type | Description |
|---|---|---|
| user_instruction | string | Natural language directive for the AI |

---

### SearchRequest

| Field | Type | Required | Description |
|---|---|---|---|
| query | string | yes | High-level user question or keywords |
| limit | int | no | Maximum hits to return (1–50, default 10) |

---

### SearchResponse

| Field | Type | Description |
|---|---|---|
| query | string | Echoed input query |
| results | SearchResultItem[] | Ranked list of hits |

---

### SearchResultItem

| Field | Type | Description |
|---|---|---|
| id | int | Note identifier |
| content | string | Note content |
| summary | string | Note summary |
| tags | string \| null | Note tags |
| score | float \| null | Combined relevance score |
| domain | string \| null | Note domain |
| archipelago_id | int \| null | Parent archipelago |

---

### LinkConfirmRequest

| Field | Type | Description |
|---|---|---|
| target_id | int | Destination note ID |
| relation_type | string | `REINFORCES`, `CONTRADICTS`, or `RELATES` |
| reason | string | Explanation for the relationship |

---

### LinkResponse

| Field | Type | Description |
|---|---|---|
| id | int | Link record identifier |
| source_id | int | Originating note ID |
| target_id | int | Receiving note ID |
| relation_type | string | Interaction mode |
| reason | string | Justification text |
| created_at | datetime | Link creation timestamp |

---

### ArchipelagoResponse

| Field | Type | Description |
|---|---|---|
| id | int | Archipelago identifier |
| name | string | LLM-generated name |
| summary | string | Consensus theme description |
| type | string | `ISLAND` or `OCEAN` |
| parent_id | int \| null | Parent continent ID |
| needs_refresh | bool | True if metadata is stale |
| created_at | datetime | Creation timestamp |

---

### TranscriptionSaveRequest

| Field | Type | Required | Description |
|---|---|---|---|
| content | string | yes | Original ASR output |
| enhanced_content | string | no | Cleaned or LLM-improved text |
| duration_seconds | float | no | Audio length in seconds |
| applied_enhancements | string | no | Comma-separated pipeline stages applied |
| ingest | bool | no | Run note ingestion after saving (default `true`) |

---

### TranscriptionEnhanceRequest

| Field | Type | Required | Description |
|---|---|---|---|
| raw_text | string | yes | Noisy ASR text |
| user_prompt | string | no | Optional custom instruction |

---

### TranscriptionEnhanceResponse

| Field | Type | Description |
|---|---|---|
| enhanced_text | string | Final clean text |
| applied_layers | string[] | Sequential processing steps taken |
| error | string \| null | Partial-failure reason if applicable |

---

### DeviceResponse

| Field | Type | Description |
|---|---|---|
| id | int | System device index |
| name | string | Human-readable label |
| channels | int | Available input channels |
| default | bool | True if system default |
| active | bool | True if currently configured |

---

### ConfigResponse

| Field | Type | Description |
|---|---|---|
| active_model_id | string | Global Bedrock model identifier |
| pricing | object | Map of model IDs to `{input, output}` USD per 1M tokens |
| is_configured | bool | True if the backend has initialised |
| auto_pause_seconds | int | Inactivity timeout for audio ingestion |

---

### StatsResponse

| Field | Type | Description |
|---|---|---|
| total_tokens | int | Total LLM tokens consumed |
| prompt_tokens | int | Input tokens |
| completion_tokens | int | Completion tokens |
| total_cost | string | Formatted cost string |
| total_requests | int | Total inference calls |

---

### HealthResponse

| Field | Type | Description |
|---|---|---|
| status | string | `ok` or `degraded` |
| services | ServiceStatus[] | Per-service health entries |

---

### MessageResponse

| Field | Type | Description |
|---|---|---|
| message | string | Human-readable confirmation |
| detail | any \| null | Optional diagnostic details |

---

## Workflow State Schemas (`shared/schemas/workflow/`)

### IngestState

The end-to-end mutable state object threaded through the `IngestWorkflow`.

| Field | Type | Description |
|---|---|---|
| content | string | Current version of the note text |
| source_type | string | Origin category (default `manual`) |
| source_url | HttpUrl \| null | Optional source URI |
| original_content | string \| null | Raw uncleaned text for traceability |
| summary | string \| null | LLM-generated summary |
| embedding | float[] \| null | Titan v2 vector (1024 dimensions) |
| tags | string \| null | Comma-separated normalised tags |
| language | string | ISO 639-1 language code (default `en`) |
| taxonomy | ConceptTaxonomy \| null | Semantic fingerprint from the taxonomy agent |
| note_id | int \| null | ID of the saved or merged note |
| action | string | Gatekeeper decision: `CREATE`, `MERGE`, or `SKIP` |
| reasoning | string \| null | Gatekeeper LLM justification |
| similar_notes | dict[] | Candidate notes for deduplication or linking |
| links | LinkItem[] | Forward and backward links to persist |
| retrospective_links | dict[] | Kept for schema compatibility; always empty in current pipeline |
| near_miss_candidates | dict[] | Candidates rejected by the linker; surfaced for `--review` |
| archipelago_action | string \| null | Geo sub-workflow outcome: `NONE`, `JOIN`, or `CREATE` |
| archipelago_id | int \| null | ID of the joined or created archipelago |
