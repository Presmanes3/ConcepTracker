# TODO

---

## Critical - Runtime Crashes (all fixed)

- **archipelago_badge arg order** - FIXED: open_note_interactor._resolve_badge now calls archipelago_badge(arch.name, arch.type)
- **BidirectionalLinkerAgent missing prompt variables** - FIXED: _forward_pass and _run_backward_call now pass domain/domain_family/concept_type/parent_hint; _forward_pass mirrors LinkerAgent domain-guard logic
- **TagRecommenderAgent undefined self.logger** - FIXED: BaseAgent.__init__ now assigns self.logger = logging.getLogger(self.__class__.__name__)
- **ChunkEmbedAgent undefined ChunkEmbedAgentInput** - FIXED: constructor type hint replaced with IngestState
- **ingestion_node.py** - FIXED: abandoned file with syntax error deleted from src/nodes/
- **Missing .env.example** - FIXED: .env.example added to project root
- **README command names** - FIXED: ct transcribe -> ct live_transcription, ct open -> ct open_note

---

## High - Incomplete Features

### open_note menu actions not implemented
src/cli/interactors/open_note_interactor.py has five lambda: None stubs:
- Edit Note, AI (not connected), Trace, Manage Tags, Manage Links

### ~~BidirectionalLinkerAgent not wired into production~~ — FIXED
LinkerAgent and RetrospectiveLinkerAgent deleted. BidirectionalLinkerAgent is the sole linker in ingest_workflow.py.

### ~~ChunkEmbedAgent not wired into any workflow~~ — FIXED
chunk_embed_agent.py deleted (did not subclass BaseAgent, had undeclared dependency).

### Transcription language hardcoded to Spanish
src/cli/interactors/_transcription_async.py: language_code='es-ES' hardcoded. Expose via config/settings.yaml.

### Full-text search language hardcoded to Spanish
src/repository/note_repository.py: to_tsvector('spanish') hardcoded. Non-Spanish notes return degraded FTS results.

---

## Medium - Dev Experience

- ~~**langchain-text-splitters missing from pyproject.toml**~~ — FIXED: chunk_embed_agent.py deleted
- **No database migration system** - schema changes require reset_db.py (data loss). Consider Alembic.
- **AgentRegistry zero entries** - src/registry/agent_registry.py defines a registration decorator but no agent uses it

---

## Medium - Test Coverage

No unit tests for (priority order):
- Agents: gatekeeper, normalizer, bidirectional_linker, speech_cleaner, markdown_formatter, tag_recommender, taxonomy
- CLI views (pure functions, no mocks needed): all src/cli/views/ files
- CLI interactors: note_list, note_find, open_note, transcription, pause_transcription, device_list
- CLI commands: all src/cli/commands/ files
- Services: bedrock, cost, embedding, audio_device, transcribe
- Repositories: all src/repository/ files
- Workflows: ingest_workflow (mocked e2e), transcription_workflow
- pytest-asyncio missing from pyproject.toml dev optional-dependencies

---

## Low - Silent Failures / Technical Debt

- **TranscriptionInteractor._do_enhance silent failure** - if enhancement fails, _do_save silently saves unenhanced text
- **GeoNamerAgent.run() raises NotImplementedError** - will crash any caller using the standard agent.run() interface

---

## Refactoring: CLI layer violations

The commands below import backend code (repositories, services, workflows) directly
instead of going through an interactor + `http_client.py`. The Docker split makes these
blockers: the CLI process cannot import backend singletons once they live in a separate
container.

### High priority — block Docker split

**`src/cli/commands/add.py`** — create `AddInteractor`
- L6: `from shared.schemas.models.link import Link`
- L9: `from src.repository.link_repository import link_repository`
- L10: `from src.workflows.ingest_workflow import ingest_graph`
- L11: `from src.registry import repos`
- L12: `from src.services.cost_service import cost_service`
- L16–100: entire `_interactive_link_review()` function is business logic; move to interactor
- L92: `link_repository.save_link()` — DB write from command
- L106: `ingest_graph.invoke(state)` — workflow executed from command
- Replace all of the above with: `http_client.ingest_note()` + `http_client.confirm_links()`

**`src/cli/screens/search_screen.py`** — delegate to `NoteSearchInteractor` (or use existing `NoteSearchInteractor`)
- L19: `from src.workflows.search_workflow import run_search`
- L20: `from src.registry import repos`
- L52: `run_search(self._query)` — workflow executed from screen
- L70: `repos.notes.get_notes_by_ids(result_ids)` — repo call from screen
- L75: `repos.archipelagos` passed to view helper from screen
- Replace with: interactor calls `http_client.search()`, passes results to screen constructor

### Medium priority — violate layer rules

**`src/cli/commands/stats.py`** — create `StatsInteractor`
- L4: `from src.services.cost_service import cost_service`
- L17, L21: `cost_service.get_stats(days=days, hours=hours)`
- Replace with: `http_client.get_stats(days=days, hours=hours)`

**`src/cli/commands/trace.py`** — create `TraceInteractor`
- L4: `from src.registry import repos`
- L5: `from src.services.search_service import search_service`
- L7: `from src.services.embedding_service import embedding_service`
- L21–32: three direct service/repo calls
- Replace with: `http_client.search()` (semantic search endpoint covers this)

**`src/cli/commands/rm.py`** — create `RmInteractor`
- L7–8: direct `repos` + `embedding_service` imports
- L32–78: inline ID selection, semantic search, confirmation, and deletion
- Replace with: `http_client.search()` for candidate lookup, `http_client.delete_note()` for deletion

**`src/cli/commands/config.py`** — create `ConfigInteractor`
- L4–5: direct `repos` + `bedrock_service` imports
- L31–49: read config, validate model, write config all in command
- Replace with: `http_client.get_config()` + `http_client.update_config()`

### Low priority — minor inconsistencies

- `src/cli/screens/recording_screen.py` L113–116: `config_repository` imported inside `_load_auto_pause()`; `auto_pause_seconds` should be passed from `TranscriptionInteractor` constructor
- `shared/schemas/workflow/transcription.py`: uses `TypedDict` instead of Pydantic `BaseModel`; inconsistent with all other workflow state models
- `src/repository/note_repository.py`: `get_similar_notes()` duplicates logic now owned by `SearchService`; add `# DEPRECATED` and migrate callers
- ~~`src/registry/agent_registry.py` L53: `_load_defaults()` still loads `LinkerAgent`~~ — FIXED: removed from registry, file deleted
