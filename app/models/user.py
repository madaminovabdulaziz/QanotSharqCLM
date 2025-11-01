from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin


class UserRole(str, enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    OPS_COORDINATOR = "ops_coordinator"
    STATION_USER = "station_user"
    SUPERVISOR = "supervisor"
    FINANCE = "finance"
    CREW = "crew"


class User(Base, TimestampMixin):
    """
    User model for authentication and authorization.
    
    Supports role-based access control (RBAC) with station-level permissions
    for station users.
    """
    __tablename__ = "users"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="User ID"
    )
    
    # Authentication
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email (login username)"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    # Profile
    first_name = Column(
        String(100),
        nullable=False,
        comment="User first name"
    )
    last_name = Column(
        String(100),
        nullable=False,
        comment="User last name"
    )
    phone = Column(
        String(20),
        nullable=True,
        comment="Contact phone number"
    )
    
    # Role & Permissions
    role = Column(
        SQLEnum(UserRole),
        nullable=False,
        index=True,
        comment="User role for RBAC"
    )
    station_ids = Column(
        JSON,
        nullable=True,
        comment="Array of station IDs (for station_user role only)"
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
        comment="Account active status"
    )
    last_login_at = Column(
        DateTime,
        nullable=True,
        comment="Last successful login timestamp"
    )
    
    # Audit
    created_by = Column(
        Integer,
        nullable=True,
        comment="User ID of creator"
    )


    created_layovers = relationship(
        "Layover",
        foreign_keys="Layover.created_by",
        back_populates="created_by_user",
        lazy="dynamic"  # Optional: for better performance with many layovers
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_role', 'role'),
        Index('idx_user_active', 'is_active'),
        Index('idx_user_email_active', 'email', 'is_active'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
    
    @property
    def full_name(self):
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"