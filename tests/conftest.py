"""
conftest.py
───────────
Shared pytest fixtures for ConcepTracker test suite.

Fixtures are scoped to minimise redundant teardown:
  - note_factory / link_factory / archipelago_factory  → function-scoped, return
    the created objects and ids so tests can clean up themselves if needed.
  - clean_db → session-scoped: wipes relevant tables once before integration
    run starts; *not* used by unit tests (they never touch the DB).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import pytest

from shared.schemas.models.note import Note
from shared.schemas.models.link import Link
from shared.schemas.models.archipelago import Archipelago


# ── DB fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_session():
    """
    Integration-only: return a live DB session.
    Importing get_session here is intentional — unit tests never reference
    this fixture so the import (and DB connection) never runs.
    """
    from src.utils.db import get_session
    with get_session() as session:
        yield session


@pytest.fixture(scope="session")
def clean_db():
    """
    Integration-only: truncate notes/links/archipelagos before the session
    so integration tests start from a known blank state.

    Usage: add `clean_db` to the first integration test, or to conftest of the
    integration sub-package.  Unit tests must NOT use this fixture.
    """
    from src.utils.db import db_manager
    with db_manager.engine.connect() as conn:
        conn.execute(__import__("sqlalchemy").text(
            "TRUNCATE TABLE links, notes, archipelagos RESTART IDENTITY CASCADE"
        ))
        conn.commit()
    yield


# ── Object factories ──────────────────────────────────────────────────────────

@pytest.fixture
def note_factory():
    """
    Returns a callable that persists a Note directly (bypassing the full
    ingest pipeline) and returns the saved Note with its DB-assigned id.

    Usage::

        def test_something(note_factory):
            n = note_factory(content="...", summary="...", tags="tag1,tag2")
            assert n.id is not None
    """
    from src.repository.note_repository import note_repository

    created_ids: list[int] = []

    def _make(
        content: str = "Test note content.",
        summary: str = "Test note summary.",
        tags: str = "test",
        archipelago_id: int | None = None,
    ) -> Note:
        note = Note(
            content=content,
            summary=summary,
            tags=tags,
            archipelago_id=archipelago_id,
        )
        saved = note_repository.save_note(note)
        created_ids.append(saved.id)
        return saved

    yield _make

    # teardown: delete created notes
    from src.repository.note_repository import note_repository as nr
    for nid in created_ids:
        nr.delete_note(nid)


@pytest.fixture
def archipelago_factory():
    """
    Returns a callable that persists an Archipelago and returns the saved object.
    """
    from src.repository.archipelago_repository import archipelago_repository

    created_ids: list[int] = []

    def _make(
        name: str = "Test Archipelago",
        summary: str = "A test archipelago.",
        arch_type: str = "archipelago",
    ) -> Archipelago:
        arch = Archipelago(name=name, summary=summary, type=arch_type)
        saved = archipelago_repository.save_archipelago(arch)
        created_ids.append(saved.id)
        return saved

    yield _make

    # teardown
    from src.utils.db import get_session
    import sqlalchemy
    with get_session() as session:
        for aid in created_ids:
            a = session.get(Archipelago, aid)
            if a:
                session.delete(a)
        session.commit()


@pytest.fixture
def link_factory():
    """
    Returns a callable that persists a Link directly and returns the saved object.
    """
    from src.repository.link_repository import link_repository

    created_ids: list[int] = []

    def _make(
        source_id: int,
        target_id: int,
        relation_type: str = "RELATES",
        reason: str = "Test link.",
    ) -> Link:
        link = Link(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            reason=reason,
        )
        saved = link_repository.save_link(link)
        created_ids.append(saved.id)
        return saved

    yield _make

    from src.utils.db import get_session
    with get_session() as session:
        for lid in created_ids:
            lnk = session.get(Link, lid)
            if lnk:
                session.delete(lnk)
        session.commit()
