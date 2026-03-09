# CLI Reference

The CLI entry point is `ct`. Commands are registered in `src/cli/commands/` and
grouped by function. Each command delegates all logic to an interactor.

---

## Note Management

### ct add

Capture a new concept atomically and link it to the past.

```bash
ct add "DeepSeek-R1 uses reinforcement learning" --tag "AI"
ct add "Zettelkasten promotes atomic note-taking" -r
```

| Argument / Option | Type | Required | Default | Description |
|---|---|---|---|---|
| content | string | yes | — | Raw note text |
| --tag, -t | string | no | — | Single tag to attach |
| --review, -r | bool | no | false | Interactively review near-miss candidates after save |

Aliases: `a`

---

### ct rm

Remove a note and its links from the graph.

```bash
ct rm 42
ct rm --search "biography"
```

| Argument / Option | Type | Required | Default | Description |
|---|---|---|---|---|
| note_id | int | no | — | ID of the note to remove |
| --search, -s | string | no | — | Search string to locate the note by content |

---

## Search & Discovery

### ct ls

List recent captures with interactive arrow-key pagination.

```bash
ct ls
ct ls --tag AI --archipelago "Machine Learning"
ct ls --limit 200 --page-size 20
```

| Option | Type | Default | Description |
|---|---|---|---|
| --tag, -t | string | — | Filter by tag |
| --limit, -l | int | 100 | Max notes to fetch (0 = all) |
| --page-size, -p | int | 10 | Rows per page |
| --archipelago, -a | string | — | Filter by archipelago name |

Aliases: `l`

---

### ct find

Find concepts by meaning using AI-powered semantic search.

```bash
ct find "concepts about machine learning"
ct find "retrieval augmented generation" --limit 20
```

| Argument / Option | Type | Required | Default | Description |
|---|---|---|---|---|
| query | string | yes | — | Semantic search query |
| --limit, -l | int | no | 10 | Max results to retrieve |
| --page-size, -p | int | no | 10 | Rows per page |

Aliases: `f`

---

### ct trace

Trace the chronological evolution of a concept by semantic similarity.

```bash
ct trace "Large Language Models"
ct trace "intermittent fasting" --threshold 0.8
```

| Argument / Option | Type | Required | Default | Description |
|---|---|---|---|---|
| concept | string | yes | — | Term or phrase to trace |
| --threshold | float | no | 0.85 | Minimum similarity score to include a note |

Aliases: `t`

---

### ct show

Open a note in an interactive TUI screen showing its content, links, and actions.

```bash
ct show 42
```

| Argument | Type | Required | Description |
|---|---|---|---|
| note_id | int | yes | ID of the note to open |

Aliases: `s`, `open`

---

## Transcription

### ct listen

Start a real-time transcription session using Amazon Transcribe. Audio is captured
from the configured input device, enhanced by the transcription pipeline, and
optionally ingested as an atomic note.

```bash
ct listen
```

Aliases: `lt`, `live`

---

## Devices

### ct devices

Open an interactive list of all available audio input devices and set the active one.

```bash
ct devices
```

Aliases: `ld`, `devs`

---

## Statistics

### ct stats

Explore inference performance and costs.

```bash
ct stats
ct stats --days 7
ct stats --hours 24
```

| Option | Type | Default | Description |
|---|---|---|---|
| --days, -d | int | 0 | Filter to last N days |
| --hours, -hr | int | 0 | Filter to last N hours |

---

## Configuration

### ct config

Manage system configuration without touching files manually.

```bash
ct config --list
ct config --model eu.amazon.nova-micro-v1:0 --input 0.035 --output 0.14 --active
```

| Option | Type | Default | Description |
|---|---|---|---|
| --model, -m | string | — | Bedrock model ID |
| --input, -i | float | 0.0 | Cost per 1M input tokens (USD) |
| --output, -o | float | 0.0 | Cost per 1M completion tokens (USD) |
| --active, -a | bool | false | Set this model as the active one |
| --list, -l | bool | false | Display all current configuration |

---

## Initialisation

### ct init

Build the brain. Initialize database and pgvector extension.

```bash
ct init
```

Run once after setting up the database for the first time.

---

## Error Handling

Every command wraps its interactor call in a try/except block:

- `ValueError` — displays a red panel with the message and exits with code 1.
- Any other exception — displays "Unexpected error: \<message\>" and exits with code 1.
