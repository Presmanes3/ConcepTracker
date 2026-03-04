---
name: backend_patterns
description: >
  Canonical implementation patterns for ConcepTracker's backend layer.
  Use this skill whenever adding or modifying a LangGraph agent, FastAPI router,
  SQLModel repository, service singleton, or LangGraph workflow in src/agents/,
  src/api/, src/repository/, src/services/, or src/workflows/.
---

## 1. BaseAgent pattern

Every LangGraph node is a class that extends `BaseAgent[TInput, TOutput]`.

### Mandatory structure

```python
# shared/schemas/agents/my_agent.py
from pydantic import BaseModel

class MyAgentInput(BaseModel):
    # Fields consumed from the workflow state
    content: str
    domain: str

class MyAgentOutput(BaseModel):
    # Structured output expected from the LLM
    result: str
    confidence: float
```

```python
# src/agents/my_agent.py
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from shared.schemas.agents.my_agent import MyAgentInput, MyAgentOutput

class MyAgent(BaseAgent[MyAgentInput, MyAgentOutput]):
    """One-line imperative description of what this agent does."""

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Consume <field> from state, return <output_key> update."""
        input_data = MyAgentInput(**state)
        result: MyAgentOutput = self._call_llm(
            messages=self._build_messages(input_data),
            output_schema=MyAgentOutput,
        )
        return {"my_output_key": result.result}

    def _build_messages(self, input_data: MyAgentInput) -> list:
        prompt = self.prompt_template.format_messages(**input_data.model_dump())
        return prompt
```

### Rules

- `_call_llm(messages, output_schema)` handles cost tracking, Nova Micro quirks, and
  structured output parsing. Never call `self.llm.invoke()` directly in a subclass.
- The agent's I/O schema files live in `shared/schemas/agents/<agent_name>.py`.
- Register the agent in `AgentRegistry` via the `@agent_registry.register("key")`
  decorator on the class.
- The prompt template for the agent lives in `shared/prompts/<agent_name>.py`.
- Mark agents under active replacement as `# DEPRECATED: use XAgent instead` at the
  module docstring level, then remove them from `agent_registry._load_defaults()`.

---

## 2. Repository pattern

Every repository is a singleton that wraps a single SQLModel table.

### Mandatory structure

```python
# src/repository/thing_repository.py
from typing import Optional, List
from sqlmodel import Session, select
from src.utils.db import get_engine
from shared.schemas.models.thing import Thing

class ThingRepository:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_by_id(self, thing_id: int) -> Optional[Thing]:
        with Session(get_engine()) as session:
            return session.get(Thing, thing_id)

    def get_all(self, limit: int = 50) -> List[Thing]:
        with Session(get_engine()) as session:
            return list(session.exec(select(Thing).limit(limit)).all())

    def save(self, thing: Thing) -> Thing:
        with Session(get_engine()) as session:
            session.add(thing)
            session.commit()
            session.refresh(thing)
            return thing

    def delete(self, thing_id: int) -> bool:
        with Session(get_engine()) as session:
            obj = session.get(Thing, thing_id)
            if not obj:
                return False
            session.delete(obj)
            session.commit()
            return True

thing_repository = ThingRepository()
```

### Rules

- Every repository ends with a module-level singleton alias: `thing_repository = ThingRepository()`.
- All SQL lives in the repository. Services and workflows never construct `select()` statements.
- Input and output types are always SQLModel instances, never raw dicts.
- Register in `RepositoryRegistry` as a `@property` that returns the singleton.
- The `SearchService` owns all hybrid BM25+vector retrieval. `NoteRepository.get_similar_notes()`
  is deprecated — do not add new callers; migrate existing calls to `search_service`.

---

## 3. Service singleton pattern

Services own a single, well-scoped capability orthogonal to any domain model.

### Mandatory structure

```python
# src/services/thing_service.py
class ThingService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def initialize(self) -> None:
        if self._initialized:
            return
        # one-time setup (load model, open connection, etc.)
        self._initialized = True

    def health_check(self) -> bool:
        return self._initialized

    def do_thing(self, input: str) -> str:
        if not self._initialized:
            raise RuntimeError("ThingService not initialized.")
        ...

thing_service = ThingService()
```

### Rules

- Register `initialize` and `health_check` in `ServiceRegistry` under the service name
  matching the key in `config/settings.yaml`.
- Services return primitive types or plain dicts, never SQLModel objects.
- Services never import from `src/repository/` — data retrieval is the repository's job.

---

## 4. FastAPI router pattern

### Mandatory structure

```python
# src/api/routers/things.py
from fastapi import APIRouter, Depends, HTTPException
from src.api.dependencies import get_thing_repo
from shared.schemas.api.things import ThingResponse, ThingCreateRequest
from src.repository.thing_repository import ThingRepository

router = APIRouter(prefix="/things", tags=["things"])

@router.get("/{thing_id}", response_model=ThingResponse)
def get_thing(
    thing_id: int,
    repo: ThingRepository = Depends(get_thing_repo),
) -> ThingResponse:
    """Return a single thing by ID."""
    thing = repo.get_by_id(thing_id)
    if not thing:
        raise HTTPException(status_code=404, detail="Thing not found.")
    return ThingResponse.model_validate(thing)

@router.post("", response_model=ThingResponse, status_code=201)
def create_thing(
    body: ThingCreateRequest,
    repo: ThingRepository = Depends(get_thing_repo),
) -> ThingResponse:
    """Create a new thing and return it."""
    ...
```

### Rules

- Router file is named after the resource (plural noun): `things.py`.
- All dependencies injected via `Depends(get_*)` from `src/api/dependencies.py`.
- Request/response types defined in `src/api/schemas.py` — never use SQLModel table
  classes as response models in routers.
- No business logic inside router functions. For operations beyond a single repo call,
  invoke a workflow: `result = ingest_graph.invoke(state)`.
- Register the router in `src/api/main.py` with `app.include_router(router)`.

---

## 5. LangGraph workflow pattern

### Mandatory structure

```python
# src/workflows/thing_workflow.py
from langgraph.graph import StateGraph, END
from shared.schemas.workflow.thing import ThingState
from src.agents.step_one_agent import StepOneAgent
from src.agents.step_two_agent import StepTwoAgent

_step_one = StepOneAgent()
_step_two = StepTwoAgent()

def step_one_node(state: dict) -> dict:
    return _step_one.run(state)

def step_two_node(state: dict) -> dict:
    return _step_two.run(state)

def _route_after_step_one(state: dict) -> str:
    if state.get("skip"):
        return END
    return "step_two"

_graph = StateGraph(ThingState)
_graph.add_node("step_one", step_one_node)
_graph.add_node("step_two", step_two_node)
_graph.set_entry_point("step_one")
_graph.add_conditional_edges("step_one", _route_after_step_one)
_graph.add_edge("step_two", END)

thing_graph = _graph.compile()
```

### Rules

- One compiled `StateGraph` per workflow file, exported as `<name>_graph`.
- State model is a Pydantic `BaseModel` (never `TypedDict`) in
  `shared/schemas/workflow/<name>.py`.
- Node functions are module-level functions, not methods. Agent instances are
  module-level singletons prefixed with `_`.
- Conditional routing logic lives in a dedicated `_route_after_<node>()` function,
  never inline in `add_conditional_edges`.
- Workflow topology changes (adding/removing nodes) require `architect_agent` review.

---

## 6. WebSocket transcription protocol

The `/ws/transcription` endpoint follows a strict frame protocol:

```
Client → Server: raw PCM audio bytes (streaming)
Server → Client: {"type": "partial", "text": "..."}   (incremental)
Server → Client: {"type": "final", "text": "..."}     (segment complete)
Client → Server: {"type": "stop"}                     (end of recording)
Server → Client: {"type": "done", "transcription": "...", "note_id": 1, ...}
```

- The server runs `transcription_workflow` on receipt of the `stop` signal.
- The CLI's `ws_client.py` owns the client side; do not duplicate this logic.
- `TranscriptionEnhancementState` must be a Pydantic `BaseModel` (see Rule 7 in
  `copilot-instructions.md`). The current `TypedDict` definition is a known debt item.
