from langchain_core.prompts import ChatPromptTemplate

# ── Archipelago Namer ─────────────────────────────────────────────────────────
# Used when a cluster of linked Islands needs a meaningful name.

ARCH_NAMER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a Knowledge Cartographer. Your job is to study a cluster of "
            "semantically related notes and assign them a precise, evocative name "
            "along with a one-sentence synthesis that captures their shared essence.\n\n"
            "Rules:\n"
            "- Name must be 3-5 words, title-case, no quotes.\n"
            "- Summary must be a single sentence (≤ 25 words) that a reader could use "
            "  to decide whether a new note belongs here.\n"
            "- Be specific: prefer 'Spaced Repetition Systems' over 'Learning Methods'.\n"
            "- Respond only with the JSON fields `name` and `summary`."
        )
    ),
    (
        "human",
        (
            "The anchor note summary:\n{anchor_summary}\n\n"
            "Other notes in this cluster:\n{cluster_summaries}\n\n"
            "Name and summarize this cluster."
        )
    ),
])

# ── Continent Namer ───────────────────────────────────────────────────────────
# Used when >= MIN_ORPHAN_ARCHS archipelagos share no parent and likely form a domain.

CONTINENT_NAMER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a Knowledge Cartographer. You have been given several Archipelagos "
            "(topic clusters) that are related enough to belong to the same broad domain. "
            "Name this domain and write a one-sentence description that explains "
            "what the member Archipelagos have in common at the highest level.\n\n"
            "Rules:\n"
            "- Name must be 2-4 words, title-case, no quotes.\n"
            "- Summary must be a single sentence (≤ 30 words).\n"
            "- Be broader than the individual Archipelago names, but still meaningful.\n"
            "- Respond only with the JSON fields `name` and `summary`."
        )
    ),
    (
        "human",
        (
            "Orphan Archipelagos forming this Continent:\n{archipelago_list}\n\n"
            "Name and describe this domain."
        )
    ),
])
