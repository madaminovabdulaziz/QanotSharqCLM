from sqlalchemy import Column, Integer, String, Boolean, Text, Date, Time, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin


class LayoverStatus(str, enum.Enum):
    """Layover request status enumeration"""
    DRAFT = "DRAFT"
    SENT = "SENT"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ON_HOLD = "ON_HOLD"
    AMENDED = "AMENDED"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LayoverReason(str, enum.Enum):
    """Layover reason enumeration"""
    SCHEDULED_REST = "scheduled_rest"
    POSITIONING = "positioning"
    TRAINING = "training"
    STANDBY = "standby"
    IRREGULAR_OPS = "irregular_ops"
    OTHER = "other"


class Layover(Base, TimestampMixin):
    """
    Layover accommodation request model.
    
    Core entity representing a crew layover with complete lifecycle tracking.
    Supports operational, positioning, training, and irregular ops layovers.
    """
    __tablename__ = "layovers"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Layover ID (internal)"
    )
    
    # External-Facing UUID
    uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="UUID for external references (URLs, exports)"
    )
    
    # Route & Station
    origin_station_code = Column(
        String(10),
        nullable=True,  # Nullable for positioning/training layovers
        comment="Departure airport code"
    )
    destination_station_code = Column(
        String(10),
        nullable=True,  # Nullable for positioning/training layovers
        comment="Arrival airport code"
    )
    station_id = Column(
        Integer,
        ForeignKey('stations.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
        comment="Station handling this layover"
    )
    hotel_id = Column(
        Integer,
        ForeignKey('hotels.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
        comment="Assigned hotel"
    )
    
    # Layover Type & Context
    layover_reason = Column(
        SQLEnum(LayoverReason),
        nullable=False,
        default=LayoverReason.SCHEDULED_REST,
        server_default='scheduled_rest',
        index=True,
        comment="Reason for layover"
    )
    operational_flight_number = Column(
        String(20),
        nullable=True,
        comment="Flight number if operational (e.g., QS100)"
    )
    positioning_flight_number = Column(
        String(20),
        nullable=True,
        comment="Flight number if positioning/deadheading (e.g., BA112)"
    )
    
    # Trip Grouping
    trip_id = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Groups related layovers (e.g., QS-JAN25-P001)"
    )
    trip_sequence = Column(
        Integer,
        nullable=True,
        comment="Order in trip: 1, 2, 3..."
    )
    is_positioning = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="True if crew deadheading"
    )
    
    # Dates & Times
    check_in_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Check-in date"
    )
    check_in_time = Column(
        Time,
        nullable=False,
        comment="Check-in time"
    )
    check_out_date = Column(
        Date,
        nullable=False,
        comment="Check-out date"
    )
    check_out_time = Column(
        Time,
        nullable=False,
        comment="Check-out time"
    )
    
    # Crew Information
    crew_count = Column(
        Integer,
        nullable=False,
        comment="Total number of crew members"
    )
    room_breakdown = Column(
        JSON,
        nullable=True,
        comment='Room breakdown JSON: {"singles": 3, "doubles": 1, "suites": 0}'
    )
    
    # Special Requirements
    special_requirements = Column(
        Text,
        nullable=True,
        comment="Special requirements or notes"
    )
    transport_required = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Transport required flag"
    )
    transport_details = Column(
        Text,
        nullable=True,
        comment="Transport details if required"
    )
    
    # Workflow Status
    status = Column(
        SQLEnum(LayoverStatus),
        nullable=False,
        default=LayoverStatus.DRAFT,
        server_default='DRAFT',
        index=True,
        comment="Current workflow status"
    )
    
    # Status Timestamps (for SLA tracking)
    sent_at = Column(DateTime, nullable=True, comment="When sent to hotel")
    pending_at = Column(DateTime, nullable=True, comment="When marked pending")
    confirmed_at = Column(DateTime, nullable=True, comment="When hotel confirmed")
    declined_at = Column(DateTime, nullable=True, comment="When hotel declined")
    escalated_at = Column(DateTime, nullable=True, comment="When escalated")
    completed_at = Column(DateTime, nullable=True, comment="When completed")
    
    # ON_HOLD Status Fields
    on_hold_at = Column(DateTime, nullable=True, comment="When put on hold")
    on_hold_reason = Column(String(255), nullable=True, comment="Reason for hold")
    on_hold_by = Column(Integer, nullable=True, comment="User ID who put on hold")
    
    # AMENDED Status Fields
    amendment_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of amendments after confirmation"
    )
    last_amended_at = Column(DateTime, nullable=True, comment="Last amendment timestamp")
    amendment_reason = Column(Text, nullable=True, comment="Reason for amendment")
    hotel_notified_of_amendment = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Hotel notified of changes flag"
    )
    
    # Hotel Response Metadata
    hotel_response_note = Column(
        Text,
        nullable=True,
        comment="Note from hotel (decline reason, change request)"
    )
    hotel_response_metadata = Column(
        JSON,
        nullable=True,
        comment="IP, user-agent, timestamp from confirmation link"
    )
    
    # Reminder Tracking
    last_reminder_sent_at = Column(
        DateTime,
        nullable=True,
        comment="Last reminder timestamp"
    )
    reminder_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of reminders sent"
    )
    
    # Reminder Pause (for IRROPS)
    reminders_paused = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Reminders paused flag"
    )
    reminders_paused_reason = Column(
        String(255),
        nullable=True,
        comment="Reason for pausing reminders"
    )
    reminders_paused_at = Column(
        DateTime,
        nullable=True,
        comment="When reminders paused"
    )
    reminders_paused_by = Column(
        Integer,
        nullable=True,
        comment="User ID who paused reminders"
    )
    
    # Confirmation Details
    hotel_confirmation_number = Column(
        String(100),
        nullable=True,
        comment="Hotel confirmation number"
    )
    
    # Cost Tracking (Optional for MVP)
    estimated_cost = Column(
        Integer,  # Store in cents
        nullable=True,
        comment="Estimated cost in cents"
    )
    actual_cost = Column(
        Integer,  # Store in cents
        nullable=True,
        comment="Actual cost in cents"
    )
    currency = Column(
        String(3),
        nullable=False,
        default='USD',
        server_default='USD',
        comment="Currency code (ISO 4217)"
    )
    
    # Audit
    created_by = Column(
        Integer,
        nullable=False,
        index=True,
        comment="User ID of creator"
    )

        # --- Cancellation Tracking ---
    cancelled_at = Column(DateTime, nullable=True, comment="When cancellation recorded")
    cancellation_reason = Column(Text, nullable=True, comment="Reason for cancellation")
    cancellation_notice_hours = Column(Integer, nullable=True, comment="Hours between cancel time and check-in")

    # Airline-style charge metadata
    cancellation_charge_applies = Column(Boolean, nullable=False, default=False, server_default="0",
                                        comment="Whether any cancellation charge applies")
    cancellation_charge_policy = Column(String(50), nullable=True,
                                        comment="Tier label (e.g., 'no_charge', '24_48h_50', 'lt_24h_100')")
    cancellation_charge_percent = Column(Integer, nullable=True,
                                        comment="Percent of charge applied (e.g., 50, 100)")
    cancellation_fee_cents = Column(Integer, nullable=True,
                                    comment="Computed fee (if available) in cents")

    
    # Relationships
    station = relationship("Station", back_populates="layovers")
    hotel = relationship("Hotel", back_populates="layovers")
    crew_assignments = relationship("LayoverCrew", back_populates="layover", cascade="all, delete-orphan")
    notes = relationship("LayoverNote", back_populates="layover", cascade="all, delete-orphan")
    files = relationship("FileAttachment", back_populates="layover", cascade="all, delete-orphan")
    tokens = relationship("ConfirmationToken", back_populates="layover", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "(layover_reason != 'scheduled_rest') OR (origin_station_code IS NOT NULL AND destination_station_code IS NOT NULL)",
            name='chk_route_required_for_scheduled'
        ),
        CheckConstraint('crew_count > 0 AND crew_count <= 100', name='chk_crew_count'),
        Index('idx_layover_uuid', 'uuid'),
        Index('idx_layover_station', 'station_id'),
        Index('idx_layover_hotel', 'hotel_id'),
        Index('idx_layover_status', 'status'),
        Index('idx_layover_check_in', 'check_in_date'),
        Index('idx_layover_created_by', 'created_by'),
        Index('idx_layover_station_status', 'station_id', 'status'),
        Index('idx_layover_status_sent', 'status', 'sent_at'),
        Index('idx_layover_trip', 'trip_id', 'trip_sequence'),
        Index('idx_layover_reason', 'layover_reason'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<Layover(id={self.id}, uuid='{self.uuid}', status='{self.status}')>"