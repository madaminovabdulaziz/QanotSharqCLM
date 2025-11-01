from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin


class TokenType(str, enum.Enum):
    """Token type enumeration"""
    HOTEL_CONFIRMATION = "hotel_confirmation"
    CREW_PORTAL = "crew_portal"
    PASSWORD_RESET = "password_reset"


class ConfirmationToken(Base, TimestampMixin):
    """
    Tokenized confirmation links model.
    
    Stores secure tokens for hotel confirmations, crew portal access,
    and password resets. Tracks usage and expiry.
    """
    __tablename__ = "confirmation_tokens"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Token ID"
    )
    
    # Token
    token = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="UUID token for URL"
    )
    token_type = Column(
        SQLEnum(TokenType),
        nullable=False,
        index=True,
        comment="Token type"
    )
    
    # Linkage
    layover_id = Column(
        Integer,
        ForeignKey('layovers.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Associated layover"
    )
    hotel_id = Column(
        Integer,
        ForeignKey('hotels.id', ondelete='CASCADE'),
        nullable=True,
        comment="For hotel_confirmation type"
    )
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        comment="For crew_portal or password_reset type"
    )
    
    # Expiry & Usage
    expires_at = Column(
        DateTime,
        nullable=False,
        index=True,
        comment="Token expiry timestamp"
    )
    used_at = Column(
        DateTime,
        nullable=True,
        comment="When token was used"
    )
    is_valid = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
        comment="Token validity flag"
    )
    
    # Response Metadata (when used)
    response_metadata = Column(
        JSON,
        nullable=True,
        comment='Metadata JSON: {"ip": "...", "user_agent": "...", "action": "..."}'
    )
    
    # Relationships
    layover = relationship("Layover", back_populates="tokens")
    
    # Indexes
    __table_args__ = (
        Index('idx_token', 'token'),
        Index('idx_token_layover', 'layover_id'),
        Index('idx_token_expires', 'expires_at'),
        Index('idx_token_valid', 'is_valid'),
        Index('idx_token_validation', 'token', 'is_valid', 'expires_at'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<ConfirmationToken(id={self.id}, token='{self.token[:8]}...', type='{self.token_type}')>"
    
    @property
    def is_expired(self):
        """Check if token is expired"""
        from datetime import datetime
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_usable(self):
        """Check if token can be used"""
        return self.is_valid and not self.is_expired and self.used_at is None