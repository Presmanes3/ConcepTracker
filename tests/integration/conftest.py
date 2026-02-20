"""
tests/integration/conftest.py
──────────────────────────────────────────────────────────────────
Session-scoped DB reset for integration tests.

Why needed:
  • Integration tests ingest real notes into the DB. If a previous run
    crashed before cleanup, orphaned notes remain and contaminate the
    next run (false MERGEs, stale links, wrong F1 scores).
  • The notes table schema may have changed (e.g. new `domain`,
    `domain_family` columns) — reset ensures the schema is current.

Effect: drops and recreates all tables before the integration test
session starts.  All data is lost — do NOT run against a DB with
data you want to keep.

Opt-out: set the env var SKIP_INTEGRATION_RESET=1 to skip the reset
(e.g. when debugging a single test without wanting a full wipe).
"""
import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def reset_db_before_integration_suite():
    """Drop and recreate all tables once before the full integration session."""
    if os.getenv("SKIP_INTEGRATION_RESET", "0") == "1":
        print("\n[conftest] SKIP_INTEGRATION_RESET=1 — skipping DB reset.")
        yield
        return

    print("\n[conftest] Resetting DB before integration suite…")

    from sqlmodel import SQLModel, create_engine
    from dotenv import load_dotenv

    # Import all models so SQLModel registers them before create_all
    import shared.schemas.models.note          # noqa: F401
    import shared.schemas.models.link          # noqa: F401
    import shared.schemas.models.inference_log # noqa: F401

    # Archipelago may not exist yet in all environments — import defensively
    try:
        import shared.schemas.models.archipelago  # noqa: F401
    except ImportError:
        pass

    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set — skipping integration tests.")

    engine = create_engine(db_url)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    print("[conftest] DB reset complete — fresh schema ready.\n")

    yield

    # No teardown needed: individual tests call _cleanup() themselves.
