from typing import List, Dict, Any, Optional
from langchain_aws import BedrockEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from shared.schemas.chunk_embed_agent import ChunkEmbedAgentInput
from shared.schemas.note_chunk import NoteChunk
from shared.schemas.workflow import WorkflowState

class ChunkEmbedAgent:
    """
    Agent responsible for breaking down long notes into smaller chunks 
    and generating vector embeddings for semantic search.
    """
    def __init__(
        self, 
        input_data: ChunkEmbedAgentInput,
        embedding_model: str = "amazon.titan-embed-text-v1",
        region: str = "us-east-1"
    ):
        self.input_data = input_data
        # En BedrockEmbeddings el parámetro es model_id y region_name
        self.embeddings_model = BedrockEmbeddings(
            model_id=embedding_model,
            region_name=region
        )
        # Markdown-aware splitter for cleaner chunks
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=150,
            separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]
        )

    def run(self) -> Dict[str, Any]:
        """
        Executes the chunking and embedding generation pipeline.
        Returns a dictionary for updating the WorkflowState.
        """
        try:
            if not self.input_data.clean_message:
                return {"pipeline_errors": ["No clean_message found for chunking."]}

            # 1. Text Segmentation
            text_chunks = self.splitter.split_text(self.input_data.clean_message)

            # 2. Batch Embedding Generation (Optimized for Bedrock)
            vectors: List[List[float]] = self.embeddings_model.embed_documents(text_chunks)

            # 3. Build NoteChunk objects
            processed_chunks = []
            for i, (content, vector) in enumerate(zip(text_chunks, vectors)):
                processed_chunks.append(
                    NoteChunk(
                        content=content,
                        embedding=vector,
                        index=i
                    ).model_dump()
                )

            return {
                "chunks": processed_chunks,
                "is_indexed": True,  # Processed and ready for a vector DB
                "pipeline_errors": []
            }

        except Exception as e:
            return {
                "is_indexed": False,
                "pipeline_errors": [f"Error in ChunkEmbedAgent: {str(e)}"]
            }
