from langchain_core.prompts import ChatPromptTemplate

QUERY_EXPANSION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a query expansion assistant for a personal knowledge base. "
                "Given a search query, generate {expansion_count} semantically distinct "
                "reformulations that preserve the original intent but use different wording, "
                "synonyms, or related terminology. "
                "Return only the reformulations, one per line, without numbering or preamble."
            ),
        ),
        ("human", "{query}"),
    ]
)
