from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin


class NotificationStatus(str, enum.Enum):
    """Crew notification status"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class LayoverCrew(Base, TimestampMixin):
    """
    Junction table linking layovers to crew members.
    
    Tracks crew assignments, room allocations, and notification status.
    """
    __tablename__ = "layover_crew"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Assignment ID"
    )
    
    # Foreign Keys
    layover_id = Column(
        Integer,
        ForeignKey('layovers.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Layover ID"
    )
    crew_member_id = Column(
        Integer,
        ForeignKey('crew_members.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Crew member ID"
    )
    
    # Room Assignment
    room_number = Column(
        String(20),
        nullable=True,
        comment="Hotel room number"
    )
    room_type = Column(
        String(50),
        nullable=True,
        comment="Room type: single, double, suite"
    )
    room_allocation_priority = Column(
        Integer,
        nullable=True,
        comment="Priority for room allocation (based on rank)"
    )
    is_primary_contact = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Primary contact for this layover (Captain/Purser)"
    )
    
    # Notification Status
    notified_at = Column(
        DateTime,
        nullable=True,
        comment="When crew member was notified"
    )
    notification_status = Column(
        SQLEnum(NotificationStatus),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default='pending',
        comment="Notification delivery status"
    )
    acknowledged_at = Column(
        DateTime,
        nullable=True,
        comment="When crew acknowledged receipt"
    )
    acknowledgment_ip = Column(
        String(45),
        nullable=True,
        comment="IP address of acknowledgment"
    )
    
    # Relationships
    layover = relationship("Layover", back_populates="crew_assignments")
    crew_member = relationship("CrewMember", back_populates="layover_assignments")
    
    # Constraints & Indexes
    __table_args__ = (
        UniqueConstraint('layover_id', 'crew_member_id', name='uq_layover_crew'),
        Index('idx_layover_crew_layover', 'layover_id'),
        Index('idx_layover_crew_member', 'crew_member_id'),
        Index('idx_layover_crew_primary', 'layover_id', 'is_primary_contact'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<LayoverCrew(layover_id={self.layover_id}, crew_member_id={self.crew_member_id})>"