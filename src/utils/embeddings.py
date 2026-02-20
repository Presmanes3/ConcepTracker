import os
from langchain_aws import BedrockEmbeddings
from dotenv import load_dotenv

from shared.config.embedding_config import EMBEDDING_MODEL_ID, EMBEDDING_DIMENSIONS  # noqa: F401 — re-exported for callers

load_dotenv()


# ── Similarity tier helper ────────────────────────────────────────────────────
# Converts a pgvector cosine distance (0 = identical, 2 = opposite) to a
# human-readable tier used as in-context signal for the LinkerAgent prompt.
# Empirically calibrated for Titan v2 (1024-dim) on PKM-domain notes.

DISTANCE_TIERS = [
    (0.55, "High similarity"),       # very likely related
    (0.75, "Moderate similarity"),    # strong evidence of relationship
    (0.95, "Weak topical connection"), # link only if clearly articulable
]  # ≥ 0.95 → "Distant"  (excluded from LinkerAgent prompt)


def similarity_tier(distance: float) -> str:
    """
    Map a cosine distance to a qualitative similarity tier.

    Tiers:
      < 0.55  → 'High similarity'          (MUST decide)
      < 0.75  → 'Moderate similarity'      (SHOULD decide)
      < 0.95  → 'Weak topical connection'  (decide only if clear)
      ≥ 0.95  → 'Distant'                 (excluded from prompt)
    """
    for threshold, label in DISTANCE_TIERS:
        if distance < threshold:
            return label
    return "Distant"


# ── Threshold constants (single source of truth) ─────────────────────────────
# Exported so ingest_workflow and the linker can share the same values.
DISTANCE_LINKING_CUTOFF = 0.95   # candidates with dist >= this are excluded
DISTANCE_DEDUP_CUTOFF   = 0.35   # gatekeeper pre-save: only near-identical notes (> 0.825 cosine sim)

def get_embeddings_client():
    load_dotenv()
    # Prioritizing environment variables if they are set (from `ct auth`)
    # Otherwise, fallback to `AWS_PROFILE` or default AWS behavior
    profile = os.getenv("AWS_PROFILE") or None
    ak = os.getenv("AWS_ACCESS_KEY_ID") or None
    sk = os.getenv("AWS_SECRET_ACCESS_KEY") or None
    region = os.getenv("AWS_REGION", "eu-west-1")

    return BedrockEmbeddings(
        model_id=EMBEDDING_MODEL_ID,
        region_name=region,
        credentials_profile_name=profile,
        aws_access_key_id=ak,
        aws_secret_access_key=sk
    )

def get_embedding(text: str):
    try:
        client = get_embeddings_client()
        return client.embed_query(text)
    except Exception:
        # Silencing LangChain internal traces by re-raising a clean exception
        raise RuntimeError("Unable to connect to AWS Bedrock. Check your credentials.")

if __name__ == "__main__":
    test_text = "This is a test for ConcepTracker"
    vec = get_embedding(test_text)
    print(f"Embedding length: {len(vec)}")
