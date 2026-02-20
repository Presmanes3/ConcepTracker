from typing import List, Optional
from sqlmodel import select, text
from src.utils.db import get_session
from shared.schemas.models.archipelago import Archipelago
from shared.schemas.models.note import Note


class ArchipelagoRepository:
    """Repository for managing Archipelago and Continent lifecycle."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def save_archipelago(self, archipelago: Archipelago) -> Archipelago:
        """Persist a new Archipelago or Continent to the database."""
        with get_session() as session:
            session.add(archipelago)
            session.commit()
            session.refresh(archipelago)
            return archipelago

    def assign_note_to_archipelago(self, note_id: int, archipelago_id: int) -> bool:
        """Set the archipelago_id FK on a note and increment the archipelago's dirty counter."""
        REFRESH_THRESHOLD = 5  # mark stale after every 5 new islands

        with get_session() as session:
            note = session.get(Note, note_id)
            if not note:
                return False
            note.archipelago_id = archipelago_id
            session.add(note)

            # Dirty-flag bookkeeping
            arch = session.get(Archipelago, archipelago_id)
            if arch:
                arch.islands_since_refresh += 1
                if arch.islands_since_refresh >= REFRESH_THRESHOLD:
                    arch.needs_refresh = True
                session.add(arch)

            session.commit()
            return True

    def set_continent_parent(self, archipelago_id: int, continent_id: int) -> bool:
        """Attach an Archipelago to a Continent as its parent."""
        with get_session() as session:
            archipelago = session.get(Archipelago, archipelago_id)
            if not archipelago:
                return False
            archipelago.parent_id = continent_id
            session.add(archipelago)
            session.commit()
            return True

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_archipelago_by_id(self, archipelago_id: int) -> Optional[Archipelago]:
        """Retrieve a single Archipelago by ID."""
        with get_session() as session:
            return session.get(Archipelago, archipelago_id)

    def get_archipelago_for_note(self, note_id: int) -> Optional[Archipelago]:
        """Retrieve the Archipelago a note belongs to (if any)."""
        with get_session() as session:
            note = session.get(Note, note_id)
            if not note or note.archipelago_id is None:
                return None
            return session.get(Archipelago, note.archipelago_id)

    def get_notes_in_archipelago(self, archipelago_id: int) -> List[Note]:
        """Get all notes belonging to a given Archipelago."""
        with get_session() as session:
            query = select(Note).where(Note.archipelago_id == archipelago_id)
            return session.exec(query).all()

    def get_all_archipelagos(self, type_filter: Optional[str] = None) -> List[Archipelago]:
        """List all Archipelagos (or Continents) ordered by creation date."""
        with get_session() as session:
            query = select(Archipelago)
            if type_filter:
                query = query.where(Archipelago.type == type_filter)
            query = query.order_by(Archipelago.created_at.asc())
            return session.exec(query).all()

    def get_continent_archipelagos(self, continent_id: int) -> List[Archipelago]:
        """Get all Archipelagos that belong to a Continent."""
        with get_session() as session:
            query = select(Archipelago).where(Archipelago.parent_id == continent_id)
            return session.exec(query).all()

    def count_notes_in_archipelago(self, archipelago_id: int) -> int:
        """Count how many notes are in an archipelago."""
        with get_session() as session:
            result = session.exec(
                select(Note).where(Note.archipelago_id == archipelago_id)
            ).all()
            return len(result)

    def get_orphan_archipelagos(self) -> List[Archipelago]:
        """Return archipelagos (not continents) that have no parent continent yet."""
        with get_session() as session:
            query = (
                select(Archipelago)
                .where(Archipelago.type == "archipelago")
                .where(Archipelago.parent_id == None)  # noqa: E711
            )
            return session.exec(query).all()

    # -------------------------------------------------------------------------
    # Dirty-flag / refresh operations
    # -------------------------------------------------------------------------

    def get_stale_archipelagos(self) -> List[Archipelago]:
        """Return all archipelagos whose needs_refresh flag is True."""
        with get_session() as session:
            query = select(Archipelago).where(Archipelago.needs_refresh == True)  # noqa: E712
            return session.exec(query).all()

    def mark_refreshed(self, archipelago_id: int, new_summary: str) -> bool:
        """Update the summary and reset dirty flags after a refresh."""
        with get_session() as session:
            arch = session.get(Archipelago, archipelago_id)
            if not arch:
                return False
            arch.summary = new_summary
            arch.needs_refresh = False
            arch.islands_since_refresh = 0
            session.add(arch)
            session.commit()
            return True


archipelago_repository = ArchipelagoRepository()
