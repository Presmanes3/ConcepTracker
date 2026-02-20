# ConcepTracker
ConcepTracker is a local-first, multi-agent knowledge app that helps you capture ideas over days and weeks without losing context. It turns scattered notes into an evolving concept graph by automatically suggesting links, surfacing related thoughts, and scheduling lightweight review/track-back workflows.

## Core features:

- Capture notes quickly (Markdown/text) with metadata (source, tags, confidence).

- Semantic search + auto-link suggestions with evidence from your own notes.

- Concept graph visualization and idea timelines for long-term tracking.

- Review workflows (7/30/90-day revisits) and weekly digests to fight forgetting.

### CF 1: Note Capture & Ingestion

**MVP:** A minimal Markdown editor with fields: title, source_url, tags[], and confidence_level (idea/fact/hypothesis). On save, a background ingestion pipeline normalizes the text, chunks it, generates embeddings, and indexes it into the local vector store.

**Mature:** Web clipper (browser extension), PDF ingestion, and audio-to-text. The ingestion becomes a robust workflow with retries, partial-failure handling, and a dead-letter queue for failed notes.

- **NormalizerAgent:** Cleans up and standardizes incoming notes (e.g. from web clippings, PDFs, manual input) to ensure consistent formatting and metadata.
- **ChunkEmbedAgent:** Breaks down long notes into smaller chunks and generates embeddings for semantic search and linking.

### CF 2: Semantic Auto-Linking

**MVP:** After indexing a note, the system retrieves the top-5 semantically similar notes and proposes links. Each proposal includes “evidence” (the exact snippet/chunk that motivated the link) and a simple Accept/Reject UI.

**Mature:** Link proposals are validated by a quality/critic step so you don’t get hallucinated relations. Links also get an editable relation_type (supports / contradicts / extends / references), enabling richer reasoning over your concept graph.

### CF 3: Concept Graph View

**MVP:** An interactive graph where nodes = notes and edges = accepted links, with basic filters (tag, project). Clicking a node opens the note; clicking an edge shows why it exists (evidence).

**Mature:** Multi-hop exploration (2–3 steps), clustering by concept/entity, and concept timelines (“how this idea evolved”). A navigation agent can explain paths between two notes in natural language.

### EF 1: Review & Spaced Repetition Tracker

**MVP:** When a note is created, schedule review tasks at 7/30/90 days and show a “Due today” list. One-click actions: “reviewed”, “snooze”, “mark as resolved”.

**Mature:** Weekly digests (forgotten ideas, evolving theses, emerging contradictions) and optional notifications (email/push). Reviews feed back into the system to improve linking and prioritization.

### EF 2: Conversational Q&A over your Notes

**MVP:** A simple chat that answers questions using retrieval over your notes and returns responses with explicit citations to note IDs (and optionally chunk IDs).

**Mature:** “Debate mode” (pros/cons grounded only in your notes), persistent sessions you can resume later, and structured outputs (action items, follow-up questions, suggested new notes to write).