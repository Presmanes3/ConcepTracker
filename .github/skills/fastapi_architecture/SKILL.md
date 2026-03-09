---
name: fastapi_architecture
description: >
  Defines the backend/frontend split for ConcepTracker.
  Use this skill whenever adding, editing, or reviewing code in src/api/ or
  when CLI code (src/cli/) needs to call the backend.
  Activating this skill ensures correct layer ownership, HTTP contract shapes,
  WebSocket protocol, and dependency direction are respected throughout the stack.
---

# FastAPI Architecture Skill

## High-Level Split

```
src/
├── api/               ← FastAPI backend — NO Textual, NO Rich, NO sounddevice
│   ├── main.py            Application factory (FastAPI instance, router mounts)
│   ├── dependencies.py    FastAPI Depends: get_db_session, get_repos, get_services
│   ├── routers/           One file per domain
│   └── schemas/           Pydantic request/response shapes (NOT SQLModel table models)
├── cli/               ← Textual/Rich frontend — NO direct repo/service calls
│   ├── client/            The ONLY layer allowed to call the API
│   │   ├── http_client.py     httpx sync wrapper, one method per endpoint
│   │   └── ws_client.py       websockets async client for /ws/transcription
│   ├── commands/          Entry points — call Interactors only
│   ├── interactors/       Orchestrators — call http_client, run screens
│   ├── views/             Pure Rich renderables
│   └── screens/           Textual AppScreen subclasses
├── agents/            shared — used only by src/api/
├── repository/        shared — used only by src/api/
├── services/          shared — used only by src/api/
├── workflows/         shared — used only by src/api/
└── utils/             shared utilities
```

---

## Layer Ownership Rules

| Layer | Can import | Must NOT import |
|---|---|---|
| `src/api/routers/*` | `src/repository/*`, `src/services/*`, `src/workflows/*`, `src/agents/*`, `shared/*`, `src/api/dependencies` | `src/cli/*`, `rich`, `textual`, `sounddevice` |
| `src/api/dependencies.py` | `src/utils/db.py`, `src/registry/*`, `src/services/*`, `src/repository/*` | `src/cli/*` |
| `src/cli/client/*` | `httpx`, `websockets`, `shared/schemas/*` | `src/repository/*`, `src/services/*`, `src/workflows/*`, `src/agents/*` |
| `src/cli/commands/*` | `src/cli/interactors/*` only | Direct service/repo/workflow imports |
| `src/cli/interactors/*` | `src/cli/client/*`, `src/cli/screens/*`, `src/cli/views/*`, `shared/schemas/*` | `src/repository/*`, `src/services/*`, `src/workflows/*` |
| `src/cli/views/*` | `rich`, `shared/schemas/*` | Everything else |
| `src/cli/screens/*` | `textual`, `src/cli/components/*`, `src/cli/views/*` | Direct repo/service calls |

---

## API Surface

### Base URL

`CONCEPTRACKER_API_URL` env var (default: `http://localhost:8000`).

### REST Endpoints

| Method | Path | Description | Request body | Response |
|---|---|---|---|---|
| `GET` | `/health` | Service health checks | — | `HealthResponse` |
| `POST` | `/init` | Initialize DB tables + services | — | `MessageResponse` |
| `GET` | `/notes` | List notes (paginated) | `?limit&tag&page` | `List[NoteResponse]` |
| `GET` | `/notes/{id}` | Get single note | — | `NoteResponse` |
| `POST` | `/notes` | Ingest note (phase 1) | `NoteIngestRequest` | `NoteIngestResponse` (202, includes near-miss candidates) |
| `POST` | `/notes/{id}/links` | Confirm manual links (phase 2) | `List[LinkConfirmRequest]` | `MessageResponse` |
| `DELETE` | `/notes/{id}` | Delete note | — | `MessageResponse` |
| `GET` | `/notes/{id}/links` | Get links for a note | — | `List[LinkResponse]` |
| `POST` | `/search` | Hybrid semantic search | `SearchRequest` | `SearchResponse` |
| `GET` | `/archipelagos` | List archipelagos | — | `List[ArchipelagoResponse]` |
| `GET` | `/archipelagos/{id}` | Get single archipelago | — | `ArchipelagoResponse` |
| `GET` | `/stats` | Token/cost analytics | `?days&hours` | `StatsResponse` |
| `GET` | `/config` | Get LLM config | — | `ConfigResponse` |
| `PUT` | `/config` | Update LLM config | `ConfigUpdateRequest` | `ConfigResponse` |
| `GET` | `/devices` | List audio devices | — | `List[DeviceResponse]` |
| `PUT` | `/devices/active` | Set active device | `DeviceSetRequest` | `MessageResponse` |
| `POST` | `/transcriptions` | Save transcription result | `TranscriptionSaveRequest` | `NoteIngestResponse` |

### WebSocket Endpoint

**`WS /ws/transcription`**

Flow:
1. Client connects via WebSocket.
2. Client sends JSON `{"type": "config", "device_id": <int>}` to set device.
3. Client streams raw `bytes` (PCM 16-bit, 16kHz mono) as binary WebSocket frames.
4. Server forwards chunks to AWS Transcribe, echoes back JSON text frames:
   - `{"type": "partial", "text": "..."}` — partial transcript
   - `{"type": "final", "text": "..."}` — confirmed phrase segment
   - `{"type": "error", "message": "..."}` — error
5. Client sends JSON `{"type": "stop"}` to end the session.
6. Server runs enhancement pipeline (`NormalizerAgent`, `MarkdownFormatterAgent`), saves via `repos.transcriptions` + `ingest_graph`, then sends:
   - `{"type": "done", "note_id": <int>, "content": "..."}` — completion
7. WebSocket closes.

---

## HTTP Client Contract (`src/cli/client/http_client.py`)

```python
from src.cli.client.http_client import ConcepTrackerClient

client = ConcepTrackerClient()  # reads CONCEPTRACKER_API_URL env var

notes = client.list_notes(limit=20, tag="python")
note  = client.get_note(note_id=42)
result = client.ingest_note(content="...", source_type="manual")
client.confirm_links(note_id=result.note_id, links=[...])
client.delete_note(note_id=42)
results = client.search(query="concept drift")
stats = client.get_stats(days=7)
health = client.get_health()
```

All methods raise `httpx.HTTPStatusError` on non-2xx. Callers (interactors) handle them.

---

## Configuration

### `CONCEPTRACKER_API_URL`

- CLI reads this env var to know where the backend is.
- Default: `http://localhost:8000`.
- Docker Compose sets this automatically via `environment:` block.

### `CONCEPTRACKER_CONFIG`

- Backend reads this env var to find `settings.yaml`.
- Default: `Path(__file__).parent.parent.parent / "config" / "settings.yaml"`.
- Fallback chain: env var → relative-to-package path → empty defaults.
- **Never use a bare `Path("config/settings.yaml")`** — it breaks when the CWD is not the project root.

---

## LangGraph Workflows in FastAPI

LangGraph `invoke()` is synchronous. In FastAPI async route handlers:

```python
import asyncio
from functools import partial

result = await asyncio.to_thread(ingest_graph.invoke, state.model_dump())
```

Never call `.invoke()` directly inside an `async def` route handler — it blocks the event loop.

---

## Two-Phase Ingest

`add` command requires user confirmation of near-miss link candidates between ingest steps:

1. **Phase 1** — `POST /notes` returns `202 Accepted`:
   ```json
   {
     "note_id": 42,
     "action": "CREATE",
     "near_miss_candidates": [
       {"note_id": 7, "score": 0.91, "summary": "...", "tags": "..."}
     ]
   }
   ```
2. User reviews candidates in the TUI (Textual screen or questionary).
3. **Phase 2** — `POST /notes/42/links`:
   ```json
   [
     {"target_id": 7, "relation_type": "REINFORCES", "reason": "Manually confirmed"}
   ]
   ```

The backend saves the confirmed links and returns `200 OK`.

---

## Docker Setup

- **Backend**: `Dockerfile.api` — only installs `src/api/`, `src/agents/`, `src/repository/`, `src/services/`, `src/utils/`, `src/workflows/`, `shared/`.
- **Frontend**: runs locally outside Docker (CLI with Textual needs a real terminal).
- **Docker Compose**: `api` service depends on `db`; port `8000:8000`; mounts `config/` volume.

```yaml
# docker-compose.yml (abbreviated)
services:
  db:   # postgres + pgvector
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    depends_on: [db]
    ports: ["8000:8000"]
    volumes:
      - ./config:/app/config:ro
```

