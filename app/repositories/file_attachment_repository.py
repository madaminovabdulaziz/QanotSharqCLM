"""
File Attachment Repository - Database Access Layer
Handles all database operations for FileAttachment entity.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from app.models.file_attachment import FileAttachment, ScanStatus


class FileAttachmentRepository:
    """
    Repository for FileAttachment model database operations.

    Provides clean separation between business logic and data access.
    All database queries for file attachments go through this repository.
    Supports soft delete pattern.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ========================================
    # READ
    # ========================================

    def get_by_id(self, file_id: int, include_deleted: bool = False) -> Optional[FileAttachment]:
        """
        Get file attachment by ID.

        Args:
            file_id: File ID
            include_deleted: Include soft-deleted files

        Returns:
            FileAttachment instance or None if not found
        """
        query = self.db.query(FileAttachment).filter(FileAttachment.id == file_id)

        if not include_deleted:
            query = query.filter(FileAttachment.is_deleted == False)

        return query.first()

    def get_by_layover_id(
        self,
        layover_id: int,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[FileAttachment]:
        """
        Get all file attachments for a specific layover.

        Args:
            layover_id: Layover ID
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            include_deleted: Include soft-deleted files

        Returns:
            List of file attachments ordered by created_at DESC
        """
        query = self.db.query(FileAttachment).filter(FileAttachment.layover_id == layover_id)

        if not include_deleted:
            query = query.filter(FileAttachment.is_deleted == False)

        return query.order_by(desc(FileAttachment.created_at)).offset(skip).limit(limit).all()

    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[FileAttachment]:
        """
        Get all file attachments uploaded by a specific user.

        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Include soft-deleted files

        Returns:
            List of file attachments ordered by created_at DESC
        """
        query = self.db.query(FileAttachment).filter(FileAttachment.uploaded_by == user_id)

        if not include_deleted:
            query = query.filter(FileAttachment.is_deleted == False)

        return (
            query
            .order_by(desc(FileAttachment.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_scan_status(
        self,
        scan_status: ScanStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[FileAttachment]:
        """
        Get all files with a specific scan status.

        Useful for finding pending scans or infected files.

        Args:
            scan_status: Virus scan status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of file attachments
        """
        return (
            self.db.query(FileAttachment)
            .filter(
                FileAttachment.scan_status == scan_status,
                FileAttachment.is_deleted == False
            )
            .order_by(FileAttachment.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ========================================
    # CREATE
    # ========================================

    def create(self, file_attachment: FileAttachment) -> FileAttachment:
        """
        Create a new file attachment record.

        Args:
            file_attachment: FileAttachment model instance to create

        Returns:
            Created file attachment instance
        """
        self.db.add(file_attachment)
        self.db.commit()
        self.db.refresh(file_attachment)
        return file_attachment

    # ========================================
    # UPDATE
    # ========================================

    def update(self, file_attachment: FileAttachment) -> FileAttachment:
        """
        Update an existing file attachment.

        Args:
            file_attachment: FileAttachment model instance with updated fields

        Returns:
            Updated file attachment instance
        """
        self.db.commit()
        self.db.refresh(file_attachment)
        return file_attachment

    def update_scan_status(
        self,
        file_id: int,
        scan_status: ScanStatus
    ) -> Optional[FileAttachment]:
        """
        Update virus scan status for a file.

        Args:
            file_id: File ID
            scan_status: New scan status

        Returns:
            Updated file attachment or None if not found
        """
        file_attachment = self.get_by_id(file_id)
        if not file_attachment:
            return None

        file_attachment.scan_status = scan_status
        file_attachment.scanned_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(file_attachment)
        return file_attachment

    # ========================================
    # DELETE
    # ========================================

    def soft_delete(self, file_id: int, deleted_by: int) -> Optional[FileAttachment]:
        """
        Soft delete a file attachment.

        Args:
            file_id: File ID to delete
            deleted_by: User ID who is deleting the file

        Returns:
            Soft-deleted file attachment or None if not found
        """
        file_attachment = self.get_by_id(file_id)
        if not file_attachment:
            return None

        file_attachment.is_deleted = True
        file_attachment.deleted_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(file_attachment)
        return file_attachment

    def hard_delete(self, file_attachment: FileAttachment) -> None:
        """
        Permanently delete a file attachment.

        Note: This permanently removes the record from the database.
        Consider using soft_delete() instead to preserve audit trail.

        Args:
            file_attachment: FileAttachment instance to delete
        """
        self.db.delete(file_attachment)
        self.db.commit()

    def delete_by_layover(self, layover_id: int) -> int:
        """
        Soft delete all files for a specific layover.

        Used when a layover is deleted.

        Args:
            layover_id: Layover ID

        Returns:
            Number of files soft-deleted
        """
        files = self.get_by_layover_id(layover_id, include_deleted=False)
        count = 0
        now = datetime.utcnow()

        for file_attachment in files:
            file_attachment.is_deleted = True
            file_attachment.deleted_at = now
            count += 1

        self.db.commit()
        return count

    # ========================================
    # UTILITIES
    # ========================================

    def count_by_layover(self, layover_id: int, include_deleted: bool = False) -> int:
        """
        Count file attachments for a specific layover.

        Args:
            layover_id: Layover ID
            include_deleted: Include soft-deleted files

        Returns:
            Count of file attachments
        """
        query = self.db.query(FileAttachment).filter(FileAttachment.layover_id == layover_id)

        if not include_deleted:
            query = query.filter(FileAttachment.is_deleted == False)

        return query.count()

    def count_by_user(self, user_id: int, include_deleted: bool = False) -> int:
        """
        Count file attachments uploaded by a specific user.

        Args:
            user_id: User ID
            include_deleted: Include soft-deleted files

        Returns:
            Count of file attachments
        """
        query = self.db.query(FileAttachment).filter(FileAttachment.uploaded_by == user_id)

        if not include_deleted:
            query = query.filter(FileAttachment.is_deleted == False)

        return query.count()

    def get_total_size_by_layover(self, layover_id: int) -> int:
        """
        Get total file size for a layover in bytes.

        Args:
            layover_id: Layover ID

        Returns:
            Total size in bytes
        """
        files = self.get_by_layover_id(layover_id, include_deleted=False)
        return sum(f.file_size for f in files)

    def count_pending_scans(self) -> int:
        """
        Count files pending virus scan.

        Returns:
            Count of files with scan_status = PENDING
        """
        return (
            self.db.query(FileAttachment)
            .filter(
                FileAttachment.scan_status == ScanStatus.PENDING,
                FileAttachment.is_deleted == False
            )
            .count()
        )
