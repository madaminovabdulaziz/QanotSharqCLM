from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin, SoftDeleteMixin


class ScanStatus(str, enum.Enum):
    """Virus scan status enumeration"""
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    FAILED = "failed"


class FileAttachment(Base, TimestampMixin, SoftDeleteMixin):
    """
    File attachments for layover requests.
    
    Stores metadata for uploaded files (rooming lists, hotel quotes, etc.).
    Supports soft delete and virus scanning.
    """
    __tablename__ = "file_attachments"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="File ID"
    )
    
    # Linkage
    layover_id = Column(
        Integer,
        ForeignKey('layovers.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Associated layover"
    )
    
    # File Metadata
    file_name = Column(
        String(255),
        nullable=False,
        comment="Original file name"
    )
    file_size = Column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )
    file_type = Column(
        String(100),
        nullable=False,
        comment="MIME type"
    )
    storage_key = Column(
        String(500),
        nullable=False,
        comment="S3/MinIO object key or file path"
    )
    
    # Virus Scan
    scan_status = Column(
        SQLEnum(ScanStatus),
        nullable=False,
        default=ScanStatus.PENDING,
        server_default='pending',
        index=True,
        comment="Virus scan status"
    )
    scanned_at = Column(
        DateTime,
        nullable=True,
        comment="When file was scanned"
    )
    
    # Audit
    uploaded_by = Column(
        Integer,
        ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
        comment="User ID of uploader"
    )
    
    # Relationships
    layover = relationship("Layover", back_populates="files")
    
    # Indexes
    __table_args__ = (
        Index('idx_file_layover', 'layover_id'),
        Index('idx_file_uploaded_by', 'uploaded_by'),
        Index('idx_file_deleted', 'is_deleted'),
        Index('idx_file_scan', 'scan_status'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<FileAttachment(id={self.id}, file_name='{self.file_name}', layover_id={self.layover_id})>"
    
    @property
    def file_size_mb(self):
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)