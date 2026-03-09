# Workflows

Each file in `src/workflows/` exports exactly one compiled `StateGraph`.
All state models are Pydantic `BaseModel` subclasses defined under
`shared/schemas/workflow/`.

---

## IngestWorkflow

Orchestrates the full note ingestion pipeline from raw text to a saved, linked, and
geographically clustered note.

**File:** `src/workflows/ingest_workflow.py`  
**Compiled graph:** `ingest_graph`  
**State:** `IngestState`  
**Entry point:** `normalize`

### Nodes

| Node | Agent / function | State keys consumed | State keys produced |
|---|---|---|---|
| normalize | NormalizerAgent | content, source_type, source_url, tags | content, summary, tags, language, original_content, embedding |
| classify_concept | ConceptTaxonomyAgent | content | taxonomy |
| search_pre | note_repository.get_similar_notes | embedding, content | similar_notes |
| gatekeeper | GatekeeperAgent | content, similar_notes, summary, taxonomy | action, note_id, reasoning, summary |
| save_note | note_repository.save_note | content, summary, embedding, tags, taxonomy | note_id |
| update_note | note_repository.update_note | note_id, summary | note_id |
| search_links | hybrid search + link_confidence | embedding, content, note_id, taxonomy | similar_notes |
| match_relations | BidirectionalLinkerAgent | similar_notes, note_id, taxonomy | links, near_miss_candidates |
| save_links | link_repository.save_link | links, note_id | links |
| detect_archipelago | geo_workflow (sub-graph) | note_id, summary, links | archipelago_action, archipelago_id |

### Edges

```
START → normalize → classify_concept → search_pre → gatekeeper
gatekeeper ──(CREATE)──► save_note → search_links → match_relations → save_links → detect_archipelago → END
           ──(MERGE) ──► update_note → END
           ──(SKIP)  ──► END
```

### Partial Re-normalisation Graph

**Compiled graph:** `run_normalize(content, note_id)`  
Used by `PUT /notes/{note_id}` to regenerate summary, tags, embedding, and taxonomy
without triggering the gatekeeper or linker.

```
START → normalize → classify_concept → END
```

---

## SearchWorkflow

Runs a multi-variant hybrid search pipeline to retrieve the most relevant notes.

**File:** `src/workflows/search_workflow.py`  
**Compiled graph:** `run_search(query) → List[dict]`  
**State:** `SearchState`  
**Entry point:** `expand_query`

### Nodes

| Node | Agent / service | State keys consumed | State keys produced |
|---|---|---|---|
| expand_query | QueryExpansionAgent | query | expanded_queries |
| embed_query | EmbeddingService | query | query_embedding |
| retrieve_vector | SearchService.vector_search | query_embedding, expanded_queries | vector_results |
| retrieve_bm25 | SearchService.bm25_search | query, expanded_queries | bm25_results |
| fuse_results | rrf_fuse() | vector_results, bm25_results | fused_results |
| rerank | RerankService | query, fused_results | reranked_results |

### Edges

```
START → expand_query → embed_query → retrieve_vector
                                   → retrieve_bm25
retrieve_vector ─► fuse_results → rerank → END
retrieve_bm25   ─►
```

---

## GeoWorkflow

Assigns newly ingested notes to geographic knowledge clusters (Archipelagos and
Continents). Runs as a sub-graph inside `detect_archipelago` at the end of
`IngestWorkflow`.

**File:** `src/workflows/geo_workflow.py`  
**Compiled graph:** `geo_graph`  
**State:** `GeoState`  
**Entry point:** `geo_router`

### Nodes

| Node | Agent / function | Description |
|---|---|---|
| geo_router | Pure rule-based | Decides NONE / JOIN / CREATE |
| join_executor | archipelago_repository | Assigns note to most common existing archipelago |
| arch_namer | GeoNamerAgent (Nova Micro) | Names a new archipelago |
| geo_persister | archipelago_repository | Saves the new archipelago and updates note |
| continent_check_router | Pure rule-based | Checks whether ≥ MIN_ORPHAN_ARCHS exist |
| continent_namer | GeoNamerAgent (Nova Micro) | Names a new continent |
| continent_persister | archipelago_repository | Saves the continent, links orphan archipelagos |

### Edges

```
START → geo_router
geo_router ──(none)────► END
           ──(join)────► join_executor → END
           ──(create)──► arch_namer → geo_persister → continent_check_router
                                    continent_check_router ──(done)──────► END
                                                           ──(continent)──► continent_namer → continent_persister → END
```

### LLM cost per `ct add`

| Outcome | LLM calls |
|---|---|
| NONE or JOIN | 0 |
| CREATE | 1 × Nova Micro |
| CREATE + new continent | 2 × Nova Micro |

---

## TranscriptionWorkflow

Dynamically builds a sequential enhancement pipeline based on `settings.yaml`.
Stages are activated by listing their names in `transcription.enhancement_pipeline`.

**File:** `src/workflows/transcription_workflow.py`  
**Compiled graph:** `transcription_workflow`  
**State:** `TranscriptionEnhancementState`  
**Entry point:** first active stage, or `no_op` if the pipeline is empty

### Available stages

| Stage name | Agent | Action |
|---|---|---|
| `speech_cleaner` | SpeechCleanerAgent | Removes filler words and stutters |
| `markdown_formatter` | MarkdownFormatterAgent | Structures text as Markdown |

### Default pipeline (from `settings.yaml`)

```
START → speech_cleaner → markdown_formatter → END
```

---

## EnhancementWorkflow

Refactors note content using RAG-based context retrieval and a user-supplied
instruction. Invoked by `POST /notes/{note_id}/enhance`.

**File:** `src/workflows/enhancement_workflow.py`  
**Compiled graph:** `enhancement_graph`  
**State:** `EnhancementState`

### Nodes

| Node | Description |
|---|---|
| retrieve_context | Embeds the current note content, retrieves up to 3 related notes via vector search |
| enhance | EnhancementAgent — builds a RAG prompt and generates the enhanced Markdown content |
| save | Updates the note in the repository with the enhanced content |

### Edges

```
START → retrieve_context → enhance → save → END
```
