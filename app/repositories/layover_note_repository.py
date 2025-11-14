"""
Layover Note Repository - Database Access Layer
Handles all database operations for LayoverNote entity.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.layover_note import LayoverNote


class LayoverNoteRepository:
    """
    Repository for LayoverNote model database operations.

    Provides clean separation between business logic and data access.
    All database queries for layover notes go through this repository.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ========================================
    # READ
    # ========================================

    def get_by_id(self, note_id: int) -> Optional[LayoverNote]:
        """
        Get note by ID.

        Args:
            note_id: Note ID

        Returns:
            LayoverNote instance or None if not found
        """
        return self.db.query(LayoverNote).filter(LayoverNote.id == note_id).first()

    def get_by_layover_id(
        self,
        layover_id: int,
        skip: int = 0,
        limit: int = 100,
        internal_only: Optional[bool] = None
    ) -> List[LayoverNote]:
        """
        Get all notes for a specific layover.

        Args:
            layover_id: Layover ID
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            internal_only: Filter by internal flag (None = all)

        Returns:
            List of notes ordered by created_at DESC
        """
        query = self.db.query(LayoverNote).filter(LayoverNote.layover_id == layover_id)

        if internal_only is not None:
            query = query.filter(LayoverNote.is_internal == internal_only)

        return query.order_by(desc(LayoverNote.created_at)).offset(skip).limit(limit).all()

    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[LayoverNote]:
        """
        Get all notes created by a specific user.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of notes ordered by created_at DESC
        """
        return (
            self.db.query(LayoverNote)
            .filter(LayoverNote.created_by == user_id)
            .order_by(desc(LayoverNote.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_tagged_notes(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[LayoverNote]:
        """
        Get all notes where a specific user is tagged.

        Args:
            user_id: User ID to search for in tagged_user_ids
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of notes where user is tagged
        """
        # MySQL JSON search for user ID in array
        return (
            self.db.query(LayoverNote)
            .filter(LayoverNote.tagged_user_ids.contains([user_id]))
            .order_by(desc(LayoverNote.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ========================================
    # CREATE
    # ========================================

    def create(self, note: LayoverNote) -> LayoverNote:
        """
        Create a new layover note.

        Args:
            note: LayoverNote model instance to create

        Returns:
            Created note instance
        """
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    # ========================================
    # DELETE
    # ========================================

    def delete(self, note: LayoverNote) -> None:
        """
        Delete a note.

        Note: Notes are generally immutable, but this allows admin deletion.

        Args:
            note: LayoverNote instance to delete
        """
        self.db.delete(note)
        self.db.commit()

    def delete_by_layover(self, layover_id: int) -> int:
        """
        Delete all notes for a specific layover.

        Used when a layover is deleted (cascade handled by DB).

        Args:
            layover_id: Layover ID

        Returns:
            Number of notes deleted
        """
        count = self.db.query(LayoverNote).filter(LayoverNote.layover_id == layover_id).delete()
        self.db.commit()
        return count

    # ========================================
    # UTILITIES
    # ========================================

    def count_by_layover(self, layover_id: int) -> int:
        """
        Count notes for a specific layover.

        Args:
            layover_id: Layover ID

        Returns:
            Count of notes
        """
        return self.db.query(LayoverNote).filter(LayoverNote.layover_id == layover_id).count()

    def count_by_user(self, user_id: int) -> int:
        """
        Count notes created by a specific user.

        Args:
            user_id: User ID

        Returns:
            Count of notes
        """
        return self.db.query(LayoverNote).filter(LayoverNote.created_by == user_id).count()
