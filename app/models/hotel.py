from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from app.models import Base, TimestampMixin


class Hotel(Base, TimestampMixin):
    """
    Hotel partner model.
    
    Represents hotel properties available at each station.
    Includes contact information and performance metrics.
    """
    __tablename__ = "hotels"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Hotel ID"
    )
    
    # Station Assignment
    station_id = Column(
        Integer,
        ForeignKey('stations.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
        comment="Station where hotel is located"
    )
    
    # Hotel Details
    name = Column(
        String(255),
        nullable=False,
        comment="Hotel name"
    )
    address = Column(
        Text,
        nullable=False,
        comment="Full hotel address"
    )
    city = Column(
        String(100),
        nullable=False,
        comment="City name"
    )
    postal_code = Column(
        String(20),
        nullable=True,
        comment="Postal/ZIP code"
    )
    
    # Contact Information
    phone = Column(
        String(20),
        nullable=True,
        comment="Primary phone number"
    )
    email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Primary contact email"
    )
    secondary_emails = Column(
        JSON,
        nullable=True,
        comment="Array of additional emails for CC"
    )
    
    # WhatsApp (Optional)
    whatsapp_number = Column(
        String(20),
        nullable=True,
        comment="WhatsApp number (if different from phone)"
    )
    whatsapp_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="Enable WhatsApp notifications"
    )
    
    # Contract Information (Future use)
    contract_type = Column(
        String(50),
        nullable=True,
        comment="Contract type: ad_hoc, block_booking, preferred_rate"
    )
    contract_rate = Column(
        Integer,  # Store as cents/minor units
        nullable=True,
        comment="Pre-negotiated rate per room per night (in cents)"
    )
    contract_valid_until = Column(
        String(10),  # Store as YYYY-MM-DD string
        nullable=True,
        comment="Contract expiry date"
    )
    
    # Internal Notes
    notes = Column(
        Text,
        nullable=True,
        comment="Internal notes about hotel (e.g., preferences, issues)"
    )
    
    # Performance Metrics (Updated Periodically)
    performance_metrics = Column(
    JSON,
    nullable=True,
    comment="Cached performance statistics"
)
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
        comment="Hotel active status"
    )
    
    # Audit
    created_by = Column(
        Integer,
        nullable=True,
        comment="User ID of creator"
    )
    
    # Relationships
    station = relationship(
        "Station",
        back_populates="hotels"
    )
    layovers = relationship(
        "Layover",
        back_populates="hotel",
        lazy="dynamic"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_hotel_station', 'station_id'),
        Index('idx_hotel_active', 'is_active'),
        Index('idx_hotel_email', 'email'),
        Index('idx_hotel_station_active', 'station_id', 'is_active'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<Hotel(id={self.id}, name='{self.name}', station_id={self.station_id})>"
    

    @property
    def get_performance_metrics(self):
        """Get performance metrics with defaults if None."""
        if self.performance_metrics:
            return self.performance_metrics
        
        return {
            "total_requests": 0,
            "confirmed_count": 0,
            "declined_count": 0,
            "avg_response_hours": 0.0,
            "last_updated": None
        }