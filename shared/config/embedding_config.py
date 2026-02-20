"""
shared/config/embedding_config.py
───────────────────────────────────
Single source of truth for embedding model configuration.

All of these MUST stay in sync:
  • the Bedrock model used to generate vectors
  • the pgvector column dimension in the Note schema
  • the BedrockEmbeddings client in EmbeddingService
  • the BedrockEmbeddings client in get_embeddings_client()
  • any reset_db / migration script that creates the vector column

Changing the model requires:
  1. Update EMBEDDING_MODEL_ID and EMBEDDING_DIMENSIONS here.
  2. Run `ct init --reset` (drops and recreates the table with the new dimension).
  3. Re-embed all existing notes.
"""

# Available in eu-west-1; 1024-dim output; normalize=True by default in v2.
# titan-embed-text-v1 (1536-dim) is NOT available in eu-west-1 — do not use.
EMBEDDING_MODEL_ID  = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSIONS = 1024
