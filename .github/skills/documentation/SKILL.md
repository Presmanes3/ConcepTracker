---
name: documentation
description: >
  Applies minimalist, professional documentation standards to this codebase.
  Use this skill whenever asked to write, update, or review documentation —
  including Python docstrings, module headers, README files, CLI help text,
  architecture notes, and inline comments.
---

# Documentation Skill

## Principles

- Write only what adds value. If a reader can infer it from the code, omit it.
- No emojis. No filler phrases ("Please note that…", "This function is responsible for…").
- Prefer short sentences and direct language.
- Use tables and code blocks to convey structure, not prose.

---

## Python Docstrings

Use **Google style**. Every public class, method, and function must have a docstring.

### Format

```python
def method(self, param: Type) -> ReturnType:
    """One-line summary ending with a period.

    Args:
        param: Description of what it represents, not its type.

    Returns:
        Description of the returned value.

    Raises:
        ValueError: When the input violates a constraint.
    """
```

### Rules

- The first line is a single sentence, imperative mood, no subject ("Run…" not "This method runs…").
- Omit `Args` / `Returns` / `Raises` sections when the signature is self-explanatory (e.g., `def get_id(self) -> int`).
- For abstract methods, document the contract, not the implementation.
- For `__init__`, document only if construction has non-obvious side effects.

### Class docstrings

```python
class EmbeddingService:
    """Singleton that generates embeddings via AWS Bedrock Titan v2."""
```

Document the class purpose in one line. List invariants or ownership semantics only when they are non-obvious.

---

## Module Headers

Place a single docstring at the top of every module when the module purpose is not obvious from its name.

```python
"""Workflow that orchestrates note ingestion: normalize → embed → gate → link."""
```

Omit the header for modules whose name fully describes their purpose (e.g., `db.py`, `enums/source_type.py`).

---

## Inline Comments

Use inline comments only to explain **why**, never **what**.

```python
# include_raw=True preserves token usage metadata lost after structured parsing
chain = self.llm.with_structured_output(schema, include_raw=True)
```

Do not comment self-evident code.

```python
# BAD
i += 1  # increment i

# GOOD
i += 1  # offset by one to skip the header row
```

---

## Markdown Files (README, architecture docs)

### Structure

```
# Title

One-paragraph description.

---

## Section

Content.
```

- Use `---` horizontal rules to separate top-level sections.
- Headings: `#` for title, `##` for sections, `###` for subsections. Never skip levels.
- Use a table when listing more than three key–value pairs.
- Every code block must declare its language (` ```python`, ` ```bash`, ` ```sql`).

### README template

```markdown
# <Project Name>

<One sentence stating what the project does and for whom.>

---

## Overview

<Two to four sentences on the core problem and approach.>

---

## Tech Stack

| Layer | Technology |
|---|---|
| … | … |

---

## Setup

**Prerequisites:** …

```bash
# numbered, minimal steps
```

---

## Usage

```bash
<command> <args>   # short description
```

---

## Architecture

<Optional. Link to a separate doc or embed a brief diagram.>
```

### Tone in markdown

- Present tense, second person ("Run the following command", not "You should run").
- No motivational language ("powerful", "amazing", "seamlessly").
- No summaries at the end of sections.

---

## CLI Help Text (Typer)

```python
app = typer.Typer(help="ConcepTracker — atomic capture and semantic traceability.")

@app.command(help="Ingest a new note into the knowledge graph.")
def ingest(text: str = typer.Argument(..., help="Raw note text.")):
    ...
```

- `help=` on `Typer()`: one sentence, no period.
- `help=` on each command: imperative, one sentence with a period.
- `help=` on each argument/option: noun phrase, no period.

---

## What to Avoid

| Pattern | Replace with |
|---|---|
| "This class is responsible for…" | Direct description of what it does |
| Restating the type in the docstring | Describe the semantic meaning |
| Emojis in any documentation surface | Plain text |
| Redundant section titles ("Description:", "Notes:") | Omit or merge |
| TODO comments without an owner or issue reference | `# TODO(#42): …` |
