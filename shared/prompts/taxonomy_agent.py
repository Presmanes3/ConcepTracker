"""
shared/prompts/taxonomy_agent.py
──────────────────────────────────
Prompt for the ConceptTaxonomyAgent.

Design goals:
  • Fast: 1 LLM call on Nova Micro, structured output only
  • Deterministic: few-shot examples anchor consistent domain slugs
  • Domain-stable: same concept produces the same domain slug every time
"""
from langchain_core.prompts import ChatPromptTemplate

TAXONOMY_SYSTEM_PROMPT = """\
You are a concept classification expert. Given a note, extract its semantic
fingerprint as a structured taxonomy object.

Your output will be used as a hard signal by downstream agents:
- Notes from different domains will NEVER be merged.
- Sub-concepts (is_component_of set) will always be created as separate notes.

### Domain naming rules (use exactly these slugs — do not invent new ones)
| Domain slug           | Examples of concepts                                      |
|-----------------------|-----------------------------------------------------------|
| pkm                   | Zettelkasten, evergreen notes, atomic notes, PARA         |
| devops                | Docker, Kubernetes, CI/CD, Terraform, IaC                 |
| software_engineering  | algorithms, design patterns, APIs, databases (general)    |
| machine_learning      | neural networks, embeddings, transformers, RAG            |
| psychology            | flow state, cognitive load, habits, motivation            |
| nutrition             | intermittent fasting, ketosis, gut microbiome             |
| biology               | cells, DNA, evolution, neuroscience (unless psychology)   |
| productivity          | GTD, time-blocking, Pomodoro (NOT the same as pkm)        |
| psychology            | habits, motivation, cognitive load, flow state, mindset — even when framed as methods |
| finance               | investing, budgeting, compound interest                   |
| history               | historical events, historical figures                     |
| philosophy            | ethics, epistemology, logic                               |
| other                 | anything that does not fit the above                      |

Use the MOST SPECIFIC matching slug. If unsure between two, pick the more specific.

### Few-shot examples
# Pattern 1 — sub-concept with is_component_of (knowledge_work)
Input: "The inbox is the first capture area in the GTD system where every new task and idea lands before being processed."
Output: concept_name="GTD inbox", concept_type="practice", domain="productivity",
        domain_family="knowledge_work", sub_domain="task_capture", is_component_of="GTD"

# Pattern 2 — tool in devops (technology family)
Input: "Terraform provisions and manages cloud infrastructure using declarative HCL configuration files that can be version-controlled."
Output: concept_name="Terraform", concept_type="tool", domain="devops",
        domain_family="technology", sub_domain="cloud_infrastructure", is_component_of=null

# Pattern 3 — phenomenon in life_sciences (not psychology, not nutrition)
Input: "The circadian rhythm is the internal 24-hour biological clock that regulates sleep, hormone release and metabolism."
Output: concept_name="circadian rhythm", concept_type="phenomenon", domain="biology",
        domain_family="life_sciences", sub_domain="chronobiology", is_component_of=null

# Pattern 4 — software_engineering vs devops (same domain_family, different domain slug)
Input: "GraphQL is a query language for APIs that lets clients request exactly the data they need."
Output: concept_name="GraphQL", concept_type="tool", domain="software_engineering",
        domain_family="technology", sub_domain="api_design", is_component_of=null

# Pattern 5 — methodology in knowledge_work without parent
Input: "The PARA method organises all digital information into four top-level categories: Projects, Areas, Resources and Archives."
Output: concept_name="PARA method", concept_type="methodology", domain="pkm",
        domain_family="knowledge_work", sub_domain="information_organisation", is_component_of=null

# Pattern 6 — psychology ≠ productivity: habit change is life_sciences even when framed as a system
Input: "The habit loop is a neurological cycle of cue, routine and reward that encodes automatic behaviours in the basal ganglia."
Output: concept_name="habit loop", concept_type="phenomenon", domain="psychology",
        domain_family="life_sciences", sub_domain="behavioral_psychology", is_component_of=null
"""

TAXONOMY_HUMAN_PROMPT = """\
## Note to classify
{content}

Classify this note. Use a consistent domain slug from the table.
"""

TAXONOMY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", TAXONOMY_SYSTEM_PROMPT),
    ("human", TAXONOMY_HUMAN_PROMPT),
])
