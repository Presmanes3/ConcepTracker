# API Reference

All endpoints are served by the FastAPI application defined in `src/api/main.py`.
The base URL in the default Docker setup is `http://localhost:8000`.

---

## Health

### GET /health

Returns operational status for every registered service.

**Response** `200 HealthResponse`

| Field | Type | Description |
|---|---|---|
| status | string | `ok` if all services are healthy, `degraded` otherwise |
| services | ServiceStatus[] | Per-service health entries |

`ServiceStatus`

| Field | Type | Description |
|---|---|---|
| name | string | Service identifier |
| healthy | bool | `true` if the service is operational |
| message | string \| null | Optional status or error detail |

---

## Initialisation

### POST /init

Creates the database schema and runs the `init` function for every active service.
Call once after first deployment.

**Response** `200 MessageResponse`

| Field | Type | Description |
|---|---|---|
| message | string | Confirmation text |
| detail | string[] \| null | Per-service init results |

---

## Notes

### GET /notes

Returns a paginated list of notes.

**Query Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| limit | int | 20 | Maximum notes to return (1–200) |
| tag | string | — | Filter to notes that carry this tag |

**Response** `200 NoteResponse[]`

| Field | Type | Description |
|---|---|---|
| id | int | Primary identifier |
| content | string | Full note text |
| summary | string | LLM-generated summary |
| tags | string \| null | Comma-separated tags |
| created_at | datetime | Creation timestamp |
| domain | string \| null | Primary subject area |
| domain_family | string \| null | Broader domain grouping |
| archipelago_id | int \| null | Parent archipelago ID |

---

### GET /notes/{note_id}

Returns a single note by ID.

**Path Parameters**

| Parameter | Type | Description |
|---|---|---|
| note_id | int | Target note identifier |

**Response** `200 NoteResponse` · `404` if not found.

---

### POST /notes

Runs the full ingest pipeline on the supplied content. Returns the outcome
(CREATE / MERGE / SKIP) and any near-miss candidates for manual review.

**Request** `NoteIngestRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| content | string | yes | Raw text to ingest |
| source_type | string | no | Origin category (`manual`, `web`, `pdf`, `transcription`) |
| source_url | string | no | Optional URI of the source document |

**Response** `202 NoteIngestResponse`

| Field | Type | Description |
|---|---|---|
| note_id | int \| null | ID of the created or merged note |
| action | string | `CREATE`, `MERGE`, or `SKIP` |
| reasoning | string \| null | LLM justification |
| near_miss_candidates | NearMissCandidate[] | Similar notes surfaced during deduplication |

`NearMissCandidate`

| Field | Type | Description |
|---|---|---|
| note_id | int | Candidate note identifier |
| score | float | Similarity score (0.0–1.0) |
| summary | string | Candidate note summary |
| tags | string \| null | Candidate tags |
| domain | string \| null | Candidate domain |

---

### PUT /notes/{note_id}

Updates note content. Triggers re-normalisation (fresh summary, tags, embedding,
taxonomy) without invoking the gatekeeper or linker.

**Request** `NoteUpdateRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| content | string | no | Replacement text |
| summary | string | no | Manual summary override |
| tags | string | no | Updated tags |

**Response** `200 NoteResponse` · `404` if not found.

---

### DELETE /notes/{note_id}

Removes a note and all its outgoing and incoming links.

**Response** `200 MessageResponse` · `404` if not found.

---

### POST /notes/{note_id}/enhance

Re-writes a note using the Enhancement workflow. Uses RAG to find related notes and
applies the supplied user instruction.

**Request** `NoteEnhanceRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| user_instruction | string | yes | Natural language directive for the AI |

**Response** `200 NoteResponse` · `404` / `500` on failure.

---

### GET /notes/{note_id}/links

Returns all links (outgoing and incoming) for a note, de-duplicated by ID.

**Response** `200 LinkResponse[]`

| Field | Type | Description |
|---|---|---|
| id | int | Link record identifier |
| source_id | int | Originating note ID |
| target_id | int | Receiving note ID |
| relation_type | string | `REINFORCES`, `CONTRADICTS`, or `RELATES` |
| reason | string | Justification text |
| created_at | datetime | Link creation timestamp |

---

### POST /notes/{note_id}/links

Saves manually confirmed links for a note (Phase 2 of two-phase ingest).

**Request** `LinkConfirmRequest[]`

| Field | Type | Required | Description |
|---|---|---|---|
| target_id | int | yes | Destination note ID |
| relation_type | string | yes | `REINFORCES`, `CONTRADICTS`, or `RELATES` |
| reason | string | yes | Explanation for the relationship |

**Response** `200 MessageResponse`.

---

## Search

### POST /search

Runs the hybrid search pipeline: query expansion → embedding → vector + BM25 →
Reciprocal Rank Fusion → Cohere rerank.

**Request** `SearchRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| query | string | yes | Natural language query |
| limit | int | no | Maximum results to return (1–50, default 10) |

**Response** `200 SearchResponse`

| Field | Type | Description |
|---|---|---|
| query | string | Echoed input query |
| results | SearchResultItem[] | Ranked hits |

`SearchResultItem`

| Field | Type | Description |
|---|---|---|
| id | int | Note identifier |
| content | string | Note content |
| summary | string | Note summary |
| tags | string \| null | Note tags |
| score | float \| null | Combined relevance score |
| domain | string \| null | Domain of the note |
| archipelago_id | int \| null | Parent archipelago |

---

## Archipelagos

### GET /archipelagos

Returns all archipelago groupings.

**Response** `200 ArchipelagoResponse[]`

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

### GET /archipelagos/{arch_id}

Returns a single archipelago by ID.

**Response** `200 ArchipelagoResponse` · `404` if not found.

---

## Transcription

### POST /transcriptions

Saves a completed transcription record and optionally ingests it as a note.

**Request** `TranscriptionSaveRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| content | string | yes | Raw ASR output |
| enhanced_content | string | no | Cleaned or LLM-improved text |
| duration_seconds | float | no | Audio length in seconds |
| applied_enhancements | string | no | Comma-separated pipeline stages applied |
| ingest | bool | no | Run note ingestion after saving (default `true`) |

**Response** `200 NoteIngestResponse`

---

### POST /transcriptions/enhance

Runs the enhancement pipeline (speech cleaning + Markdown formatting) on raw
transcription text without persisting anything.

**Request** `TranscriptionEnhanceRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| raw_text | string | yes | Noisy ASR text |
| user_prompt | string | no | Optional instruction (e.g., "keep medical terms") |

**Response** `200 TranscriptionEnhanceResponse`

| Field | Type | Description |
|---|---|---|
| enhanced_text | string | Final cleaned text |
| applied_layers | string[] | Processing stages that ran |
| error | string \| null | Partial-failure reason if applicable |

---

### WebSocket /ws/transcribe

Streams real-time transcription from Amazon Transcribe. The CLI connects,
sends raw PCM audio chunks, and receives partial and final transcripts as JSON.

---

## Devices

### GET /devices

Lists available audio input devices.

**Response** `200 DeviceResponse[]`

| Field | Type | Description |
|---|---|---|
| id | int | System device index |
| name | string | Human-readable device label |
| channels | int | Available input channels |
| default | bool | True if the system default |
| active | bool | True if this device is currently configured |

---

### PUT /devices/active

Sets the active recording device ID in configuration.

**Request** `DeviceSetRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| device_id | int | yes | System device index to activate |

**Response** `200 MessageResponse`.

---

## Configuration

### GET /config

Returns the current runtime configuration.

**Response** `200 ConfigResponse`

| Field | Type | Description |
|---|---|---|
| active_model_id | string | Active Bedrock model identifier |
| pricing | object | Map of model IDs to `{input, output}` USD per million tokens |
| is_configured | bool | True if the backend has initialised successfully |
| auto_pause_seconds | int | Inactivity timeout for audio ingestion |

---

### PUT /config

Updates model selection or pricing.

**Request** `ConfigUpdateRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| active_model_id | string | no | New Bedrock model ID (validated against AWS) |
| model_pricing | object | no | Pricing map updates |

**Response** `200 ConfigResponse` · `422` if the model ID is invalid.

---

## Statistics

### GET /stats

Returns LLM usage and cost analytics.

**Query Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| days | int | 0 | Filter to the last N days (`0` = all time) |
| hours | int | 0 | Filter to the last N hours |

**Response** `200 StatsResponse`

| Field | Type | Description |
|---|---|---|
| total_tokens | int | Total LLM tokens consumed |
| prompt_tokens | int | Input tokens |
| completion_tokens | int | Completion tokens |
| total_cost | string | Formatted total cost (e.g., `"$0.0042"`) |
| total_requests | int | Total inference calls made |

---

## Admin

### POST /admin/reset-db

Drops all database tables and recreates them. All data is permanently lost.

**Response** `200 MessageResponse`.
