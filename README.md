# ConcepTracker

ConcepTracker is a CLI-first personal knowledge management system that organizes atomic notes into a semantic graph. Each note is embedded, deduplicated, and automatically linked to related past notes using vector similarity and LLM-driven relation classification.

---

## Overview

The system turns free-form text input into a structured, queryable knowledge base without manual tagging or organization. Notes are the primary unit; relationships and geographic clusters emerge automatically from the content.

- A note is normalized and embedded on ingestion. Near-duplicate notes are detected before saving via cosine similarity on pgvector.
- An LLM-based Gatekeeper decides whether the input is new (`CREATE`), redundant (`SKIP`), or a refinement of an existing note (`MERGE`).
- A `BidirectionalLinkerAgent` classifies semantic relationships (`REINFORCES`, `CONTRADICTS`, `RELATES`) between the new note and its neighbours in a single LLM call, handling both forward and backward directions simultaneously.
- A geographic clustering sub-workflow groups semantically cohesive notes into Archipelagos, and Archipelagos into Continents, using rule-based routing and GeoNamerAgent.

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
# Add a note
ct add "RAG with GraphRAG improves global context via knowledge graphs" --tag "AI"

# List notes
ct ls

# Semantic search
ct find "retrieval augmented generation"

# Trace concept evolution
ct trace "retrieval augmented generation"

# Open a note in the TUI
ct show 42

# Start a real-time transcription session
ct listen

# View AI cost statistics
ct stats --days 7
```

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

Planned work includes: web/PDF ingestion, spaced repetition reviews, multi-hop graph traversal, and a conversational Q&A mode grounded in local notes.
