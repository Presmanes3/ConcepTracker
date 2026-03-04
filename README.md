# ConcepTracker

ConcepTracker is a CLI-first personal knowledge management system that organizes atomic notes into a semantic graph. Each note is embedded, deduplicated, and automatically linked to related past notes using vector similarity and LLM-driven relation classification.

---

## Overview

The system turns free-form text input into a structured, queryable knowledge base without manual tagging or organization. Notes are the primary unit; relationships and geographic clusters emerge automatically from the content.

**Ingestion pipeline (`ct add`, `POST /notes`)**

- Raw text is cleaned and summarized by `NormalizerAgent`, then classified into a semantic domain by `ConceptTaxonomyAgent` before any database lookup occurs.
- Near-duplicate notes are detected via cosine similarity on pgvector. `GatekeeperAgent` decides `CREATE`, `MERGE`, or `SKIP` using the domain taxonomy as a hard guard against false deduplication.
- `BidirectionalLinkerAgent` classifies forward and backward semantic relationships (`REINFORCES`, `CONTRADICTS`, `RELATES`) in a single LLM call, using pre-computed multi-signal confidence scores to auto-link high-confidence pairs without any LLM cost.
- A geographic sub-workflow groups linked notes into Archipelagos (clusters) and Continents (meta-clusters) using rule-based routing and `GeoNamerAgent` (Nova Micro only).

**Search (`ct find`, `POST /search`)**

- `QueryExpansionAgent` generates alternative phrasings, then both vector and BM25 results are fused with Reciprocal Rank Fusion and reranked by Cohere Rerank v3.5.

**Transcription (`ct listen`)**

- Real-time audio is streamed to Amazon Transcribe via WebSocket. Raw output passes through a configurable enhancement pipeline (`SpeechCleanerAgent` → `MarkdownFormatterAgent`) before the user confirms ingestion.

**Enhancement (`ct show` → AI action)**

- Any existing note can be refactored with a natural language instruction via `POST /notes/{id}/enhance`, which retrieves related notes via vector search and applies them as RAG context.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM & Embeddings | AWS Bedrock (Amazon Nova Micro, Amazon Titan v2 1024-dim) |
| Semantic reranking | Cohere Rerank v3.5 via Bedrock |
| Workflow orchestration | LangGraph |
| Database | PostgreSQL + pgvector |
| ORM / schema | SQLModel + Pydantic |
| API server | FastAPI + Uvicorn |
| CLI | Typer + Rich + Textual |
| Audio transcription | Amazon Transcribe (streaming) |
| HTTP client | httpx + websockets |
| Runtime | Python 3.11+ |

---

## Setup

**Prerequisites:** Docker, Python 3.11+, AWS credentials with Bedrock access.

```bash
# 1. Start Postgres with pgvector
docker-compose up -d

# 2. Create a virtual environment and install the package
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[api,client]"

# 3. Configure environment variables
cp .env.example .env        # fill in AWS_REGION, DB_URL, etc.

# 4. Initialize the database schema
ct init
```

---

## Usage

```bash
# ── Setup ──────────────────────────────────────────────────────────────────
ct auth                                    # configure AWS credentials
ct init                                    # create database schema and init services
ct health                                  # verify DB and AI connectivity

# ── Notes ──────────────────────────────────────────────────────────────────
ct add "RAG with GraphRAG improves recall" --tag "AI"   # ingest a note
ct ls                                      # list recent notes (paginated)
ct ls --tag AI --archipelago "Machine Learning"         # filter by tag or cluster
ct show 42                                 # open a note in the TUI
ct rm 42                                   # remove a note and its links

# ── Search & Discovery ─────────────────────────────────────────────────────
ct find "retrieval augmented generation"   # semantic search
ct trace "retrieval augmented generation" # trace concept evolution over time

# ── Transcription ──────────────────────────────────────────────────────────
ct devices                                 # list and select audio input device
ct listen                                  # start real-time transcription session

# ── Configuration & Admin ──────────────────────────────────────────────────
ct config --list                           # show active model and pricing
ct stats --days 7                          # view AI usage and cost analytics
ct reset-db                                # drop and recreate all tables (destructive)
```

Run `ct help` for the full command dashboard.

---

## Project Structure

```
src/
  agents/        # LangGraph nodes (NormalizerAgent, GatekeeperAgent, BidirectionalLinkerAgent, ...)
  workflows/     # Compiled LangGraph graphs (ingest_workflow, search_workflow, geo_workflow, ...)
  api/           # FastAPI routers and dependencies
  cli/           # Commands, interactors, views, screens
  repository/    # Database access layer (SQLModel)
  services/      # Service singletons (EmbeddingService, BedrockService, RerankService, ...)
  registry/      # Singleton registry for repos and services
shared/
  schemas/       # Pydantic models for wire format, workflow state, agent I/O, and DB entities
  prompts/       # LangChain prompt templates for each agent
config/
  settings.yaml  # Active model, pricing, audio, and pipeline configuration
```

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | System topology and data flow |
| [API Reference](docs/api.md) | HTTP endpoint contracts |
| [Agents](docs/agents.md) | LangGraph node reference |
| [Workflows](docs/workflows.md) | Pipeline graph topology |
| [CLI Reference](docs/cli.md) | Command reference |
| [Schemas](docs/schemas.md) | Shared Pydantic model reference |
| [Configuration](docs/configuration.md) | settings.yaml reference |

---

## Roadmap

See [TODO.md](TODO.md) for the current implementation status.
