from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, DateTime, String, Text
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Record last update timestamp"
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    is_deleted = Column(
        Integer,  # Using Integer instead of Boolean for better MySQL compatibility
        nullable=False,
        default=0,
        server_default="0",
        comment="Soft delete flag: 0=active, 1=deleted"
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        comment="Soft delete timestamp"
    )
    deleted_by = Column(
        Integer,
        nullable=True,
        comment="User ID who deleted this record"
    )


# Import all models for Alembic discovery
from app.models.user import User, UserRole
from app.models.station import Station
from app.models.hotel import Hotel
from app.models.layover import Layover, LayoverStatus, LayoverReason
from app.models.crew_member import CrewMember, CrewRank
from app.models.layover_crew import LayoverCrew, NotificationStatus as CrewNotificationStatus
from app.models.confirmation_token import ConfirmationToken, TokenType
from app.models.layover_note import LayoverNote
from app.models.file_attachment import FileAttachment, ScanStatus
from app.models.audit_log import AuditLog
from app.models.notification import Notification, NotificationType, NotificationChannel, NotificationStatus

__all__ = [
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "User",
    "UserRole",
    "Station",
    "Hotel",
    "Layover",
    "LayoverStatus",
    "LayoverReason",
    "CrewMember",
    "CrewRank",
    "LayoverCrew",
    "CrewNotificationStatus",
    "ConfirmationToken",
    "TokenType",
    "LayoverNote",
    "FileAttachment",
    "ScanStatus",
    "AuditLog",
    "Notification",
    "NotificationType",
    "NotificationChannel",
    "NotificationStatus",
]