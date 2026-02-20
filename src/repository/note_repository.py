from sqlmodel import select, text
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.utils.db import get_session

# New modular schema imports
from shared.schemas.models.note import Note

class NoteRepository:
    """
    Core repository for managing the lifecycle of Notes.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NoteRepository, cls).__new__(cls)
        return cls._instance

    def save_note(self, note: Note) -> Note:
        """Persists a new note to the graph database."""
        with get_session() as session:
            session.add(note)
            session.commit()
            session.refresh(note)
            return note

    def update_note(self, note_id: int, content: Optional[str] = None, summary: Optional[str] = None) -> Optional[Note]:
        """Updates an existing note's editable fields."""
        with get_session() as session:
            note = session.get(Note, note_id)
            if not note:
                return None
            if content:
                note.content = content
            if summary:
                note.summary = summary
            session.add(note)
            session.commit()
            session.refresh(note)
            return note

    def get_note_by_id(self, note_id: int) -> Optional[Note]:
        """Retrieves a single note by its primary ID."""
        with get_session() as session:
            return session.get(Note, note_id)

    def delete_note(self, note_id: int) -> bool:
        """Deletes a note from the system."""
        with get_session() as session:
            note = session.get(Note, note_id)
            if not note:
                return False
            session.delete(note)
            session.commit()
            return True

    def get_all_notes(self, limit: int = 20, tag: Optional[str] = None) -> List[Note]:
        """Lists notes for CLI display, filtered by tag if provided."""
        with get_session() as session:
            query = select(Note)
            if tag:
                # SQLModel filtering for tags (assuming comma separated string)
                query = query.where(Note.tags.like(f"%{tag}%"))
            query = query.order_by(Note.created_at.desc()).limit(limit)
            return session.exec(query).all()

    def get_notes_by_ids(self, note_ids: List[int]) -> List[Note]:
        """Retrieves multiple notes by their primary IDs, sorted by date."""
        with get_session() as session:
            query = select(Note).where(Note.id.in_(note_ids)).order_by(Note.created_at.asc())
            return session.exec(query).all()

    def get_similar_notes(self, current_id: Optional[int], embedding: List[float], limit: int = 5, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """Vector-based search for nearest neighbors using pgvector."""
        with get_session() as session:
            query = text("""
                SELECT id, content, summary,
                       (embedding <=> CAST(:vec AS vector)) as distance,
                       domain, domain_family
                FROM notes 
                WHERE (id != :current_id OR :current_id IS NULL)
                AND (embedding <=> CAST(:vec AS vector)) < :threshold
                ORDER BY distance ASC
                LIMIT :limit
            """)
            vec_str = str(embedding)
            results = session.execute(query, {
                "current_id": current_id, 
                "vec": vec_str, 
                "limit": limit,
                "threshold": threshold
            }).fetchall()
            return [
                {
                    "id": r[0],
                    "content": r[1],
                    "summary": r[2],
                    "distance": float(r[3]),
                    "domain": r[4],
                    "domain_family": r[5],
                }
                for r in results
            ]

    def semantic_search(self, embedding: List[float], limit: int = 5) -> List[tuple[Note, float]]:
        """Vector-based search returning Note objects and their similarity scores."""
        with get_session() as session:
            # Using cosine distance directly for semantic ranking
            distance = Note.embedding.cosine_distance(embedding)
            query = select(Note, distance).order_by(distance).limit(limit)
            return session.exec(query).all()

# Singleton global instance
repository = NoteRepository()
note_repository = repository # Alias for consistency

