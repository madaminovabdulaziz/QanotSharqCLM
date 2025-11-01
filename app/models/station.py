from sqlalchemy import Column, Integer, String, Boolean, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from app.models import Base, TimestampMixin


class Station(Base, TimestampMixin):
    """
    Station (airport/city) model.
    
    Represents airline stations where layovers occur.
    Includes configuration for reminder and escalation rules.
    """
    __tablename__ = "stations"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Station ID"
    )
    
    # Identification
    code = Column(
        String(10),
        unique=True,
        nullable=False,
        index=True,
        comment="IATA/ICAO airport code (e.g., LHR, EGLL)"
    )
    name = Column(
        String(255),
        nullable=False,
        comment="Full station name (e.g., London Heathrow)"
    )
    
    # Location
    city = Column(
        String(100),
        nullable=False,
        index=True,
        comment="City name"
    )
    country = Column(
        String(100),
        nullable=False,
        comment="Country name"
    )
    timezone = Column(
        String(50),
        nullable=False,
        default='UTC',
        server_default='UTC',
        comment="IANA timezone (e.g., Europe/London)"
    )
    
    # Reminder & Escalation Configuration
    # NOTE: JSON columns cannot have server_default in MySQL
    # Default will be set in application code during station creation
    reminder_config = Column(
        JSON,
        nullable=True,
        comment="Station-specific reminder/escalation rules"
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
        comment="Station active status"
    )
    
    # Relationships
    hotels = relationship(
        "Hotel",
        back_populates="station",
        lazy="dynamic"
    )
    layovers = relationship(
        "Layover",
        back_populates="station",
        lazy="dynamic"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_station_code', 'code'),
        Index('idx_station_active', 'is_active'),
        Index('idx_station_city', 'city'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<Station(id={self.id}, code='{self.code}', name='{self.name}')>"
    
    @property
    def get_reminder_config(self):
        """
        Get reminder config with defaults if None.
        
        Returns default configuration if reminder_config is NULL.
        """
        if self.reminder_config:
            return self.reminder_config
        
        # Default configuration
        return {
            "first_reminder_hours": 12,
            "second_reminder_hours": 24,
            "escalation_hours": 36,
            "business_hours_start": "08:00",
            "business_hours_end": "18:00",
            "pause_on_weekends": False
        }