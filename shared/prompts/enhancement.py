from langchain_core.prompts import ChatPromptTemplate

ENHANCEMENT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a professional knowledge management assistant. "
                "Refactor the user's note based on their instruction. "
                "Use the provided context from related notes to ensure semantic consistency. "
                "Maintain valid Markdown formatting."
            ),
        ),
        (
            "human",
            (
                "Instruction: {user_instruction}\n\n"
                "Current Note Content:\n{current_content}\n\n"
                "{context_block}"
                "Produce the refactored Markdown content and suggested tags."
            ),
        ),
    ]
)
