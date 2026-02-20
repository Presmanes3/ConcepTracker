from typing import List
from sqlmodel import select, delete
from src.utils.db import get_session

# Modular Schema Import
from shared.schemas.models.link import Link

class LinkRepository:
    """
    Independent repository for managing semantic connections (Links) between notes.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LinkRepository, cls).__new__(cls)
        return cls._instance

    def save_link(self, link: Link) -> Link:
        """Persists a new directed semantic link."""
        with get_session() as session:
            session.add(link)
            session.commit()
            session.refresh(link)
            return link

    def get_links_by_source(self, source_id: int) -> List[Link]:
        """Retrieves all semantic links originating from this note."""
        with get_session() as session:
            query = select(Link).where(Link.source_id == source_id)
            return session.exec(query).all()

    def get_links_by_target(self, target_id: int) -> List[Link]:
        """Retrieves all semantic links pointing to this note."""
        with get_session() as session:
            query = select(Link).where(Link.target_id == target_id)
            return session.exec(query).all()

    def delete_links_for_note(self, note_id: int) -> int:
        """Removes all links (incoming/outgoing) for a note."""
        with get_session() as session:
            stmt = delete(Link).where((Link.source_id == note_id) | (Link.target_id == note_id))
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

link_repository = LinkRepository()
