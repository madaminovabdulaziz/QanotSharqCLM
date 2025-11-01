from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Date, ForeignKey, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func
from datetime import date
from app.models import Base


class AuditLog(Base):
    """
    Immutable audit trail model.
    
    Logs all system actions for compliance and forensics.
    No updates or deletes allowed (immutable).
    """
    __tablename__ = "audit_logs"
    
    # Primary Key (BigInteger for high volume)
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Audit log ID"
    )
    
    # Who & When
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment="User ID (NULL = system action)"
    )
    user_role = Column(
        String(50),
        nullable=True,
        comment="User role at time of action"
    )
    timestamp = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Action timestamp"
    )
    
    # What
    action_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Action type: created, updated, status_changed, confirmed, etc."
    )
    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Entity type: layover, user, hotel, note, etc."
    )
    entity_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Entity ID"
    )
    
    # Details
    details = Column(
        JSON,
        nullable=True,
        comment='Details JSON: {"before": {...}, "after": {...}, "note": "..."}'
    )
    
    # Security Metadata
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IPv4 or IPv6 address"
    )
    user_agent = Column(
        Text,
        nullable=True,
        comment="Browser user agent"
    )
    
    # Partitioning Key (for future performance)
    # Note: Default will be set in application code during log creation
    log_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date for partition pruning"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_action', 'action_type'),
        Index('idx_audit_date', 'log_date'),
        Index('idx_audit_entity_time', 'entity_type', 'entity_id', 'timestamp'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action_type}', entity='{self.entity_type}:{self.entity_id}')>"
    
    def __init__(self, **kwargs):
        """Initialize audit log with auto log_date if not provided"""
        if 'log_date' not in kwargs:
            kwargs['log_date'] = date.today()
        super().__init__(**kwargs)