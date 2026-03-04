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

    def update_note(
        self,
        note_id: int,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        tags: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        domain: Optional[str] = None,
        domain_family: Optional[str] = None,
    ) -> Optional[Note]:
        """Updates an existing note's editable and AI-generated fields."""
        with get_session() as session:
            note = session.get(Note, note_id)
            if not note:
                return None
            if content is not None:
                note.content = content
            if summary is not None:
                note.summary = summary
            if tags is not None:
                note.tags = tags
            if embedding is not None:
                note.embedding = embedding
            if domain is not None:
                note.domain = domain
            if domain_family is not None:
                note.domain_family = domain_family
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

    def get_all_unique_tags(self) -> List[str]:
        """Retrieves a sorted list of all unique tags used across all notes."""
        with get_session() as session:
            query = select(Note.tags).where(Note.tags != None).where(Note.tags != "")
            results = session.exec(query).all()
            
            unique_tags = set()
            for tag_string in results:
                tags = [t.strip() for t in tag_string.split(",") if t.strip()]
                unique_tags.update(tags)
                
            return sorted(list(unique_tags))

    def get_notes_by_ids(self, note_ids: List[int]) -> List[Note]:
        """Retrieves multiple notes by their primary IDs, sorted by date."""
        with get_session() as session:
            query = select(Note).where(Note.id.in_(note_ids)).order_by(Note.created_at.asc())
            return session.exec(query).all()

    def get_recent_notes(self, limit: int = 3, exclude_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves the most recently created notes for temporal context linking."""
        with get_session() as session:
            query = select(Note)
            if exclude_id is not None:
                query = query.where(Note.id != exclude_id)
            query = query.order_by(Note.created_at.desc()).limit(limit)
            notes = session.exec(query).all()
            
            return [
                {
                    "id": n.id,
                    "content": n.content,
                    "summary": n.summary,
                    "distance": 0.0, # Temporal notes don't have a semantic distance
                    "domain": n.domain,
                    "domain_family": n.domain_family,
                    "is_recent": True
                }
                for n in notes
            ]

    def get_similar_notes(self, current_id: Optional[int], embedding: List[float], query_text: Optional[str] = None, limit: int = 5, threshold: float = 1.0, language: str = "simple") -> List[Dict[str, Any]]:
        """Hybrid search: Vector-based nearest neighbors (pgvector) + Lexical search (BM25)."""
        with get_session() as session:
            if query_text:
                # Hybrid search: Semantic + Lexical
                query = text(f"""
                    WITH semantic AS (
                        SELECT id, content, summary, domain, domain_family,
                               (embedding <=> CAST(:vec AS vector)) as distance
                        FROM notes
                        WHERE (id != :current_id OR :current_id IS NULL)
                          AND (embedding <=> CAST(:vec AS vector)) < :threshold
                    ),
                    lexical AS (
                        SELECT id,
                               ts_rank_cd(to_tsvector('{language}', content), plainto_tsquery('{language}', :query_text)) as lexical_score
                        FROM notes
                        WHERE (id != :current_id OR :current_id IS NULL)
                          AND plainto_tsquery('{language}', :query_text) @@ to_tsvector('{language}', content)
                    )
                    SELECT s.id, s.content, s.summary, s.distance, s.domain, s.domain_family,
                           COALESCE(l.lexical_score, 0) as lexical_score,
                           (s.distance - (COALESCE(l.lexical_score, 0) * 0.1)) as hybrid_score
                    FROM semantic s
                    LEFT JOIN lexical l ON s.id = l.id
                    ORDER BY hybrid_score ASC
                    LIMIT :limit
                """)
                params = {
                    "current_id": current_id, 
                    "vec": str(embedding), 
                    "query_text": query_text,
                    "limit": limit,
                    "threshold": threshold
                }
            else:
                # Pure semantic search
                query = text("""
                    SELECT id, content, summary,
                           (embedding <=> CAST(:vec AS vector)) as distance,
                           domain, domain_family,
                           0.0 as lexical_score,
                           (embedding <=> CAST(:vec AS vector)) as hybrid_score
                    FROM notes 
                    WHERE (id != :current_id OR :current_id IS NULL)
                    AND (embedding <=> CAST(:vec AS vector)) < :threshold
                    ORDER BY distance ASC
                    LIMIT :limit
                """)
                params = {
                    "current_id": current_id, 
                    "vec": str(embedding), 
                    "limit": limit,
                    "threshold": threshold
                }
                
            results = session.execute(query, params).fetchall()
            return [
                {
                    "id": r[0],
                    "content": r[1],
                    "summary": r[2],
                    "distance": float(r[3]),
                    "domain": r[4],
                    "domain_family": r[5],
                    "is_recent": False
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

