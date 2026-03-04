# ConcepTracker

ConcepTracker is a CLI-first personal knowledge management system that organizes atomic notes into a semantic graph. Each note is embedded, deduplicated, and automatically linked to related past notes based on vector similarity and LLM-driven relation classification.

---

## Overview

The core idea is to turn free-form text input into a structured, queryable knowledge base without manual tagging or organization. Notes are the primary unit; relationships and clusters emerge automatically from the content.

**Key behaviors:**

- A note is normalized and embedded on ingestion. Near-duplicate notes are detected before saving via cosine similarity on pgvector.
- An LLM-based Gatekeeper decides whether the input is new (`CREATE`), redundant (`SKIP`), or a refinement of an existing note (`MERGE`).
- A Linker agent classifies semantic relationships (supports / contradicts / extends / references) between the new note and its nearest neighbors.
- A Retrospective Linker scans previously unlinked notes and creates back-links to the new entry.
- A geographic clustering layer groups semantically cohesive notes into Archipelagos, and Archipelagos into Continents, using a separate LangGraph sub-workflow.


---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM & Embeddings | AWS Bedrock (Amazon Nova Micro, Amazon Titan v2 1024-dim) |
| Workflow orchestration | LangGraph |
| Database | PostgreSQL + pgvector |
| ORM / schema | SQLModel + Pydantic |
| CLI | Typer + Rich + Textual |
| Audio transcription | Amazon Transcribe |
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
pip install -e .

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

# Trace concept evolution
ct trace "retrieval augmented generation"

# Start a voice transcription session
ct live_transcription

# Open a note in the TUI
ct open_note <note_id>
```

---

## Project Structure

```
src/
  agents/        # Individual LangGraph nodes (NormalizerAgent, GatekeeperAgent, LinkerAgent, ...)
  workflows/     # Compiled LangGraph graphs (ingest_workflow, geo_workflow, transcription_workflow)
  cli/           # Commands, interactors, views, screens
  repository/    # Database access layer (SQLModel)
  services/      # Stateless service singletons (EmbeddingService, BedrockService, ...)
shared/
  schemas/       # Pydantic models for workflow state, agent I/O, and DB entities
  prompts/       # LangChain prompt templates for each agent
config/
  settings.yaml  # Active model, pricing, audio, and pipeline configuration
```

---

## Roadmap

See [TODO.md](TODO.md) for the current implementation status.

Planned work includes: web/PDF ingestion, spaced repetition reviews, multi-hop graph traversal, and a conversational Q&A mode grounded in local notes.
