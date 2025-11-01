from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLEnum, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin


class CrewRank(str, enum.Enum):
    """Crew rank enumeration"""
    CAPTAIN = "captain"
    FIRST_OFFICER = "first_officer"
    SECOND_OFFICER = "second_officer"
    PURSER = "purser"
    CABIN_SERVICE_MANAGER = "cabin_service_manager"
    SENIOR_FLIGHT_ATTENDANT = "senior_flight_attendant"
    FLIGHT_ATTENDANT = "flight_attendant"


class CrewMember(Base, TimestampMixin):
    """
    Crew member profile model.
    
    Stores crew member information including rank and preferences.
    """
    __tablename__ = "crew_members"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Crew member ID"
    )
    
    # Identification
    employee_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Airline employee ID"
    )
    
    # Profile
    first_name = Column(
        String(100),
        nullable=False,
        comment="First name"
    )
    last_name = Column(
        String(100),
        nullable=False,
        comment="Last name"
    )
    email = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Email address"
    )
    phone = Column(
        String(20),
        nullable=True,
        comment="Phone number"
    )
    
    # Rank & Role
    crew_rank = Column(
        SQLEnum(CrewRank),
        nullable=False,
        index=True,
        comment="Crew rank/position"
    )
    seniority_number = Column(
        Integer,
        nullable=True,
        comment="Seniority number (lower = more senior)"
    )
    
    # Preferences
    accommodation_preferences = Column(
        JSON,
        nullable=True,
        comment='Preferences JSON: {"floor": "ground", "diet": "vegetarian"}'
    )
    medical_restrictions = Column(
        String(500),
        nullable=True,
        comment="Medical restrictions or requirements"
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
        comment="Active crew member flag"
    )
    
    # Relationships
    layover_assignments = relationship(
        "LayoverCrew",
        back_populates="crew_member",
        lazy="dynamic"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_crew_employee_id', 'employee_id'),
        Index('idx_crew_email', 'email'),
        Index('idx_crew_active', 'is_active'),
        Index('idx_crew_rank', 'crew_rank'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<CrewMember(id={self.id}, employee_id='{self.employee_id}', rank='{self.crew_rank}')>"
    
    @property
    def full_name(self):
        """Get crew member's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_pilot(self):
        """Check if crew member is flight crew"""
        return self.crew_rank in [
            CrewRank.CAPTAIN,
            CrewRank.FIRST_OFFICER,
            CrewRank.SECOND_OFFICER
        ]