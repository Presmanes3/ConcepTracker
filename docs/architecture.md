# Architecture

ConcepTracker is a two-process system: a containerised FastAPI backend that owns all
persistence, LLM calls, and workflow execution, and a local CLI process that communicates
with the backend exclusively over HTTP and WebSocket. No backend code runs in the CLI
process; no terminal-rendering code runs in the backend.

---

## Container / Process Split

```
Docker container (Dockerfile.api)          Local process (never in Docker)
┌─────────────────────────────────┐        ┌──────────────────────────────┐
│  src/api/        src/agents/    │        │  src/cli/commands/           │
│  src/repository/ src/services/  │◄─HTTP─►│  src/cli/interactors/        │
│  src/workflows/  src/utils/     │   /WS  │  src/cli/screens/            │
│  src/registry/   shared/        │        │  src/cli/views/              │
└─────────────────────────────────┘        │  src/cli/client/             │
                                           └──────────────────────────────┘
```

The `src/cli/` directory is never copied into the Docker image.

---

## Layer Diagram

```
┌─────────────────────── CLI process ──────────────────────────┐
│  commands/   →   interactors/   →   client/http_client.py    │
│                             ↘   →   screens/ → views/        │
└──────────────────────────────────────────────────────────────┘
                                    │  HTTP / WebSocket
┌─────────────────────── API Container ────────────────────────┐
│  FastAPI routers  →  workflows (LangGraph)                   │
│                   →  repository (SQLModel + pgvector)        │
│                   →  services   (Bedrock, Embedding, etc.)   │
└──────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────── PostgreSQL + pgvector ────────────────────┐
│  notes   links   archipelagos   transcriptions   inferences  │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Flow — Note Ingestion

```
CLI: ct add "text"
       │
       ▼
POST /notes  (NoteIngestRequest)
       │
       ▼
ingest_workflow (LangGraph)
  1. normalize          ← NormalizerAgent   (clean text, tags, summary)
  2. classify_concept   ← ConceptTaxonomyAgent (domain, concept_type)
  3. search_pre         ← vector search     (dedup candidates)
  4. gatekeeper         ← GatekeeperAgent   (CREATE / MERGE / SKIP)
       ├── SKIP  → END
       ├── MERGE → update_note → END
       └── CREATE
              │
  5. save_note          ← note_repository.save_note
  6. search_links       ← hybrid search (vector + BM25 + RRF)
  7. match_relations    ← BidirectionalLinkerAgent (FORWARD + BACKWARD links)
  8. save_links         ← link_repository.save_link
  9. detect_archipelago ← geo_workflow (sub-graph)
       │
       ▼
NoteIngestResponse (action, note_id, near_miss_candidates)
```

---

## Data Flow — Semantic Search

```
CLI: ct find "query"
       │
       ▼
POST /search  (SearchRequest)
       │
       ▼
search_workflow (LangGraph)
  1. expand_query    ← QueryExpansionAgent  (N alternative phrasings)
  2. embed_query     ← EmbeddingService     (Titan v2, 1024 dims)
  3. retrieve_vector ← SearchService        (cosine distance, all variants)
  4. retrieve_bm25   ← SearchService        (FTS, all variants)
  5. fuse_results    ← rrf_fuse()           (Reciprocal Rank Fusion)
  6. rerank          ← RerankService        (Cohere Rerank v3.5)
       │
       ▼
SearchResponse (ranked hits)
```

---

## Data Flow — Geography (Knowledge Clustering)

```
detect_archipelago node (at end of ingest)
       │
       ▼
geo_workflow (sub-graph)
  geo_router (rule-based, 0 LLM)
       ├── NONE    → END
       ├── JOIN    → join_executor  → END
       └── CREATE
              │
         arch_namer        ← GeoNamerAgent (Nova Micro)
         geo_persister     ← archipelago_repository
         continent_check_router
              ├── done      → END
              └── continent
                     │
                continent_namer      ← GeoNamerAgent
                continent_persister  ← archipelago_repository
                     │
                    END
```

---

## Data Flow — Real-Time Transcription

```
CLI: ct listen
       │
       ▼
WebSocket  ws://<host>/ws/transcribe
       │
  Amazon Transcribe (streaming)
  → TranscriptionInteractor (FSM)
  → POST /transcriptions/enhance
       │
  transcription_workflow
    1. speech_cleaner      ← SpeechCleanerAgent
    2. markdown_formatter  ← MarkdownFormatterAgent
       │
  [User confirms]
  → POST /transcriptions (ingest=true)  →  ingest_workflow
```

---

## Shared Schemas

| Sub-namespace | Owner | Consumer |
|---|---|---|
| `shared/schemas/api/` | Backend (defines wire format) | CLI (imports for typed requests/responses) |
| `shared/schemas/models/` | Backend (SQLModel tables) | CLI (`TYPE_CHECKING` only) |
| `shared/schemas/agents/` | Backend (agent I/O) | Backend only |
| `shared/schemas/workflow/` | Backend (LangGraph state) | Backend only |
| `shared/enums/` | Both | Both |

---

## Key Design Invariants

- All repository/service singletons are obtained from `src/registry/`. Direct
  instantiation is forbidden outside tests.
- One compiled `StateGraph` per workflow file.
- Router functions delegate entirely to workflows or repositories; no business logic.
- `rich` and `textual` are CLI-only dependencies. The backend produces no
  terminal-formatted output.
