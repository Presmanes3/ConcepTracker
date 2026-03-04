# LangGraph & LangChain Workflow Patterns

This skill encodes the canonical patterns for designing, implementing, and exposing
LangGraph/LangChain workflows in ConcepTracker. Read this before creating or modifying
any prompt, agent, workflow, service, or API endpoint in this project.

---

## Architecture overview

```
shared/prompts/<name>.py          → ChatPromptTemplate (LangChain)
        │
        ▼
shared/schemas/agents/<name>.py   → Pydantic I/O models (input/output_schema)
        │
        ▼
src/agents/<name>_agent.py        → BaseAgent subclass (LangGraph node)
        │
        ▼
shared/schemas/workflow/<name>.py → Pydantic state model (StateGraph schema)
        │
        ▼
src/workflows/<name>_workflow.py  → compiled StateGraph (exported as <name>_graph)
        │
        ▼
src/services/<name>_service.py    → thin singleton wrapper (optional, for reuse)
        │
        ▼
src/api/routers/<resource>.py     → FastAPI route calling graph.invoke() or service
```

---

## Step-by-step implementation checklist

When building a new workflow vertical slice, follow this order:

1. Define the workflow state schema (`shared/schemas/workflow/`).
2. Define any new agent I/O schemas (`shared/schemas/agents/`).
3. Write prompts (`shared/prompts/`).
4. Implement agent class(es) (`src/agents/`).
5. Register agent(s) in `AgentRegistry._load_defaults()`.
6. Write the workflow file (`src/workflows/`), wiring agents as nodes.
7. Wrap in a service singleton (`src/services/`) when the graph must be reused across multiple routes or callers.
8. Add the FastAPI endpoint (`src/api/routers/`), wrapping `graph.invoke()` in `asyncio.to_thread`.
9. Define `shared/schemas/api/` request/response models for the new endpoint.
10. Update `config/settings.yaml` if the new service needs an enable/disable switch.

---

## 1. Prompt files

**Location:** `shared/prompts/<agent_name>.py`

```python
# shared/prompts/my_agent.py
"""Prompt template for MyAgent: <one-line role description>."""
from langchain_core.prompts import ChatPromptTemplate

MY_SYSTEM_PROMPT = """\
<role definition>

### Rules
| Rule | Description |
|------|-------------|
| R1   | ...         |

### Output format
Return a JSON object matching the MyOutput schema.
"""

MY_HUMAN_PROMPT = """\
## Input field A
{field_a}

## Input field B
{field_b}
"""

MY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", MY_SYSTEM_PROMPT),
    ("human", MY_HUMAN_PROMPT),
])
```

**Rules:**
- Export a module-level `*_PROMPT` constant; the sub-constants are for readability only.
- Use `{{...}}` to escape literal braces inside f-string-like system prompts.
- Structure the human prompt with `## Section` headers to delimit logical inputs.
- Describe the expected output schema in the system prompt; align it with the Pydantic `output_schema` class.

---

## 2. Agent I/O schemas

**Location:** `shared/schemas/agents/<agent_name>.py`

```python
# shared/schemas/agents/my_agent.py
"""Pydantic I/O schemas for MyAgent."""
from typing import Literal
from pydantic import BaseModel, Field


class MyOutput(BaseModel):
    """Structured output produced by MyAgent."""

    result: str = Field(..., description="Primary processed output text.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score (0–1).")
    action: Literal["CREATE", "UPDATE", "SKIP"] = Field(
        ..., description="Routing decision for downstream nodes."
    )
```

**Rules:**
- All fields use `Field(description=...)` — no plain type hints.
- Input schemas are optional when the agent consumes a `*State` model directly.
- Validation constraints (`ge`, `le`, `Literal`, `min_length`) are strongly encouraged.
- Output schemas are the `output_schema` argument to `BaseAgent._call_llm()`.

---

## 3. Workflow state schemas

**Location:** `shared/schemas/workflow/<name>.py`

```python
# shared/schemas/workflow/my_workflow.py
"""State model for the MyWorkflow LangGraph pipeline."""
from typing import Optional, List
from pydantic import BaseModel, Field


class MyWorkflowState(BaseModel):
    """Carries all data through the MyWorkflow pipeline."""

    # ── Input ──────────────────────────────────────────────────────────────
    content: str = Field(..., description="Raw content to process.")
    user_id: int = Field(..., description="Owner user ID.")

    # ── Intermediate ───────────────────────────────────────────────────────
    embedding: Optional[List[float]] = Field(
        None, description="Vector representation produced by the embed node."
    )

    # ── Decision ───────────────────────────────────────────────────────────
    action: str = Field(default="CREATE", description="Routing decision: CREATE, MERGE, or SKIP.")

    # ── Output ─────────────────────────────────────────────────────────────
    result_id: Optional[int] = Field(None, description="Persisted entity ID.")
```

**Rules:**
- Always use Pydantic `BaseModel`, never `TypedDict` for new schemas.
- Group fields by lifecycle stage with `# ── Stage ──` comments.
- Provide sensible defaults for optional/intermediate fields so the state can be constructed from input-only data.
- Only `architect_agent` can change the shape (add/rename/remove fields) of an existing state model used by a production workflow.

---

## 4. BaseAgent subclass

**Location:** `src/agents/<name>_agent.py`

```python
# src/agents/my_agent.py
"""MyAgent: <one-line role description>."""
from typing import Any, Dict

from src.agents.base_agent import BaseAgent
from src.registry import agent_registry
from shared.schemas.agents.my_agent import MyOutput
from shared.schemas.workflow.my_workflow import MyWorkflowState
from shared.prompts.my_agent import MY_PROMPT


@agent_registry.register("my_agent")
class MyAgent(BaseAgent[MyWorkflowState, MyOutput]):
    """Run <one-line description of what this agent does>."""

    def __init__(self) -> None:
        super().__init__(task_name="my_agent_task")

    def run(self, state: MyWorkflowState) -> Dict[str, Any]:
        """Process state.content and return {result, action}.

        Consumes:
            state.content     – raw input text
            state.user_id     – owner identifier

        Returns:
            result    – processed output text
            action    – CREATE | MERGE | SKIP routing decision
        """
        messages = MY_PROMPT.format_messages(
            field_a=state.content,
            field_b=state.user_id,
        )
        output: MyOutput = self._call_llm(messages, output_schema=MyOutput)
        return {
            "result": output.result,
            "action": output.action,
        }
```

**`BaseAgent._call_llm()` contract:**

| Call form | What `_call_llm` does | Returns |
|---|---|---|
| `_call_llm(messages, output_schema=MyModel)` | `llm.with_structured_output(MyModel, include_raw=True)` | Validated `MyModel` instance |
| `_call_llm(messages)` | `llm.invoke(messages)` | Raw `AIMessage` |

- **Never** call `self.llm.invoke()` directly inside a subclass.
- For Nova Micro: `_call_llm` automatically picks the last `tool_use` block from multi-block responses — no special handling required in subclasses.
- Cost is logged automatically via `cost_service.log_inference(...)`.

**Registration:**
After defining the class, add the module to `AgentRegistry._load_defaults()` in
`src/registry/agent_registry.py`:

```python
# src/registry/agent_registry.py — inside _load_defaults()
"my_agent": lambda: __import__("src.agents.my_agent", fromlist=["MyAgent"]),
```

---

## 5. LangGraph workflow file

**Location:** `src/workflows/<name>_workflow.py`

```python
# src/workflows/my_workflow.py
"""MyWorkflow: <one-sentence description of the pipeline>."""
from langgraph.graph import END, START, StateGraph

from shared.schemas.workflow.my_workflow import MyWorkflowState
from src.agents.my_agent import MyAgent
from src.agents.another_agent import AnotherAgent

# ── Module-level agent singletons ───────────────────────────────────────────
_my_agent = MyAgent()
_another_agent = AnotherAgent()


# ── Node functions (module-level, NOT methods) ───────────────────────────────
def node_my(state: MyWorkflowState) -> dict:
    """Invoke MyAgent: consume content, return result and action."""
    return _my_agent.run(state)


def node_another(state: MyWorkflowState) -> dict:
    """Invoke AnotherAgent: finalise the result."""
    return _another_agent.run(state)


# ── Conditional router ────────────────────────────────────────────────────────
def _route_after_my(state: MyWorkflowState) -> str:
    if state.action == "SKIP":
        return END
    return "node_another"


# ── Graph construction ────────────────────────────────────────────────────────
_graph = StateGraph(MyWorkflowState)

_graph.add_node("node_my", node_my)
_graph.add_node("node_another", node_another)

_graph.add_edge(START, "node_my")
_graph.add_conditional_edges("node_my", _route_after_my)
_graph.add_edge("node_another", END)

my_workflow_graph = _graph.compile()
```

**Naming conventions:**

| Artifact | Pattern | Example |
|---|---|---|
| Agent singletons | `_<agent_name>` (underscore prefix) | `_my_agent` |
| Node functions | `node_<role>` | `node_my` |
| Conditional router | `_route_after_<node>` | `_route_after_my` |
| Internal builder | `_graph` (never exported) | `_graph` |
| Exported compiled graph | `<name>_workflow_graph` or `<name>_graph` | `my_workflow_graph` |

**Hard rules:**
- Exactly one compiled `StateGraph` per file.
- Node functions must be module-level — never methods on a class.
- Return only the keys you want to update; LangGraph merges the dict into the state.
- `_graph` (the builder) is private; only the compiled result is exported.
- Topology changes (node wiring, conditional routing structure) require `architect_agent` review.

---

## 6. Topology design patterns

### Linear chain

Use when each node produces output that the next node depends on.

```
START → A → B → C → END
```

```python
_graph.add_edge(START, "a")
_graph.add_edge("a", "b")
_graph.add_edge("b", "c")
_graph.add_edge("c", END)
```

### Conditional fan-out (routing)

Use when an early node makes a classification decision that gates
which downstream path executes.

```
START → classify
             │
   ┌─────────┼──────────┐
 CREATE     MERGE      SKIP
   │          │          │
  save     update       END
   │          │
  END        END
```

```python
_graph.add_conditional_edges(
    "classify",
    _route_after_classify,
    {"CREATE": "save", "MERGE": "update", "SKIP": END},
)
```

### Sub-workflow bridge

Use when a contained sub-problem is reusable and complex enough to
warrant its own StateGraph (e.g., `geo_workflow` called from `ingest_workflow`).

```python
# In parent workflow file
from src.workflows.sub_workflow import sub_graph

def node_bridge_sub(state: ParentState) -> dict:
    """Delegate to sub_graph; map parent state into sub-state."""
    sub_state = SubState(field=state.some_field)
    result = sub_graph.invoke(sub_state)
    return {"parent_output": result["sub_output"]}
```

### Parallel fan-out (simulated)

LangGraph does not natively parallelise Python nodes in the same thread. Simulate
parallel retrieval by running both inside a single node function:

```python
def node_retrieve(state: SearchState) -> dict:
    """Retrieve from both vector store and BM25 index."""
    vector_hits = _embed_retriever.run(state)["vector_hits"]
    bm25_hits   = _bm25_retriever.run(state)["bm25_hits"]
    return {"vector_hits": vector_hits, "bm25_hits": bm25_hits}
```

---

## 7. Decision guide — when to create a new workflow

| Situation | Recommendation |
|---|---|
| New multi-step AI pipeline with ≥ 2 LLM calls | New workflow file |
| Single LLM call needed by an existing endpoint | Add a node to an existing workflow or call the agent directly from the router |
| Existing workflow needs an optional branch | Add conditional edge + new node to existing workflow (architect review required) |
| Reusable sub-problem already modeled elsewhere | Sub-workflow bridge pattern |
| CPU-only transformation (no LLM) | Plain utility function in `src/utils/`; node wraps it |
| Heavy retrieval with no LLM | Service method; router calls service directly |

---

## 8. Service wrapper

When a workflow graph needs to be invoked from multiple routes or callers, wrap it
in a service singleton. For single-use workflows, call `graph.invoke()` directly in
the router.

```python
# src/services/my_workflow_service.py
"""Service wrapper for MyWorkflow graph."""
import threading
from typing import Any

from src.workflows.my_workflow import my_workflow_graph
from shared.schemas.workflow.my_workflow import MyWorkflowState


class MyWorkflowService:
    """Expose MyWorkflow as a reusable singleton."""

    _instance: "MyWorkflowService | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "MyWorkflowService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = True
        return cls._instance

    def health_check(self) -> bool:
        """Return True if the service is ready."""
        return getattr(self, "_initialized", False)

    def run(self, content: str, user_id: int) -> dict[str, Any]:
        """Invoke the workflow and return the final state as a dict."""
        state = MyWorkflowState(content=content, user_id=user_id)
        return my_workflow_graph.invoke(state)


my_workflow_service = MyWorkflowService()
```

**Registration in `ServiceRegistry`:**

```python
# src/registry/service_registry.py — inside _load_defaults()
"my_workflow_service": {
    "init":   lambda: my_workflow_service.health_check(),
    "health": my_workflow_service.health_check,
},
```

Add the `my_workflow_service` import at the top of `service_registry.py` once the
service file exists.

---

## 9. FastAPI endpoint

**Rules (from Rule 8 of copilot-instructions.md):**
- Router function validates input (Pydantic does this), delegates to the graph or service,
  returns a typed `shared/schemas/api/` response.
- No business logic in the router.
- LangGraph `invoke()` is synchronous — always wrap in `asyncio.to_thread` inside an
  async route.

```python
# src/api/routers/my_resource.py
"""Router for MyResource: exposes the MyWorkflow pipeline."""
import asyncio
from fastapi import APIRouter

from shared.schemas.api.my_resource import MyResourceRequest, MyResourceResponse
from src.workflows.my_workflow import my_workflow_graph
from shared.schemas.workflow.my_workflow import MyWorkflowState

router = APIRouter(prefix="/my-resource", tags=["my-resource"])


@router.post("/process", response_model=MyResourceResponse)
async def process_my_resource(body: MyResourceRequest) -> MyResourceResponse:
    """Run the MyWorkflow pipeline on the supplied content."""
    state = MyWorkflowState(content=body.content, user_id=body.user_id)
    final: dict = await asyncio.to_thread(my_workflow_graph.invoke, state)
    return MyResourceResponse(result=final["result"], result_id=final.get("result_id"))
```

Register the router in `src/api/main.py`:

```python
from src.api.routers.my_resource import router as my_resource_router
app.include_router(my_resource_router)
```

---

## 10. API request/response schemas

**Location:** `shared/schemas/api/<resource>.py`

```python
# shared/schemas/api/my_resource.py
"""Wire-format schemas for the /my-resource API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


class MyResourceRequest(BaseModel):
    """Request body for POST /my-resource/process."""

    content: str = Field(..., description="Raw text content to process.")
    user_id: int = Field(..., description="ID of the owning user.")


class MyResourceResponse(BaseModel):
    """Response body for POST /my-resource/process."""

    result: str = Field(..., description="Processed output text.")
    result_id: Optional[int] = Field(None, description="Persisted entity ID, if created.")
```

---

## 11. Quick-reference: LangGraph/LangChain conventions in this project

| Topic | Convention |
|---|---|
| LLM backend | `ChatBedrock` via `langchain_aws` (AWS Bedrock) |
| Default model | `config_repository.get_active_model_id()` (set in `config/settings.yaml`) |
| Embeddings | `BedrockEmbeddings` (Titan Embeddings v2, 1024 dims) |
| Prompt template | `ChatPromptTemplate.from_messages([("system", ...), ("human", ...)])` |
| Structured output | `llm.with_structured_output(Schema, include_raw=True)` |
| Token tracking | `raw_message.usage_metadata` → `{"input_tokens": N, "output_tokens": N}` |
| Cost logging | Handled inside `BaseAgent._call_llm()` — do not duplicate |
| Nova Micro quirk | Multiple `tool_use` blocks — `_call_llm` picks the last one automatically |
| Graph state type | `StateGraph(MyState)` — Pydantic `BaseModel` passed as schema |
| Node return value | `dict` with only the keys to update (LangGraph merges) |
| Async in FastAPI | `await asyncio.to_thread(graph.invoke, state)` — never `await graph.ainvoke` |
| Sub-workflow call | Synchronous bridge node; no special LangGraph nesting required |

---

## 12. Common mistakes to avoid

| Mistake | Correct approach |
|---|---|
| `self.llm.invoke()` directly in a subclass | Use `self._call_llm(messages, ...)` |
| `TypedDict` for a new workflow state | Use Pydantic `BaseModel` |
| Business logic in a router function | Move logic to a workflow node or service method |
| Node function as a class method | Module-level function only |
| Exporting `_graph` (the builder) | Export only `<name>_graph` (the compiled result) |
| `import rich` or `import textual` in backend | Frontend-only; forbidden in `src/` except `src/cli/` |
| Instantiating a repo/service with `ClassName()` in non-test code | Use `src/registry` singletons |
| Calling `graph.invoke()` directly in an `async def` route | Wrap with `asyncio.to_thread` |
| Pinning a model ID in an agent class | Use `config_repository.get_active_model_id()` |
| Missing `description` on a Pydantic `Field` | All `Field(...)` calls must include `description=` |
