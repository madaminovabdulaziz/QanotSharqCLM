from sqlalchemy import Column, Integer, Text, ForeignKey, Boolean, Index
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship
from app.models import Base, TimestampMixin


class LayoverNote(Base, TimestampMixin):
    """
    Internal notes/comments on layover requests.
    
    Immutable notes for internal communication between ops and station users.
    Supports user tagging (@mentions).
    """
    __tablename__ = "layover_notes"
    
    # Primary Key
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Note ID"
    )
    
    # Linkage
    layover_id = Column(
        Integer,
        ForeignKey('layovers.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Associated layover"
    )
    
    # Content
    note_text = Column(
        Text,
        nullable=False,
        comment="Note content"
    )
    
    # User Tagging
    tagged_user_ids = Column(
        JSON,
        nullable=True,
        comment="Array of user IDs mentioned in note"
    )
    
    # Visibility
    is_internal = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        comment="True = internal only, False = visible to hotel"
    )
    
    # Audit (immutable - no updates allowed)
    created_by = Column(
        Integer,
        ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
        comment="User ID of note author"
    )
    
    # Relationships
    layover = relationship("Layover", back_populates="notes")
    
    # Indexes
    __table_args__ = (
        Index('idx_note_layover', 'layover_id'),
        Index('idx_note_created_by', 'created_by'),
        Index('idx_note_created_at', 'created_at'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<LayoverNote(id={self.id}, layover_id={self.layover_id}, created_by={self.created_by})>"