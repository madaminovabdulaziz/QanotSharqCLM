from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
import enum
from app.models import Base, TimestampMixin


class NotificationType(str, enum.Enum):
    """Notification type enumeration"""
    HOTEL_REQUEST = "hotel_request"
    HOTEL_REMINDER = "hotel_reminder"
    OPS_CONFIRMATION = "ops_confirmation"
    OPS_DECLINE = "ops_decline"
    OPS_ESCALATION = "ops_escalation"
    CREW_NOTIFICATION = "crew_notification"
    AMENDMENT_NOTIFICATION = "amendment_notification"
    PASSWORD_RESET = "password_reset"


class NotificationChannel(str, enum.Enum):
    """Notification channel enumeration"""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    IN_APP = "in_app"


class NotificationStatus(str, enum.Enum):
    """Notification delivery status enumeration"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class Notification(Base, TimestampMixin):
    """
    Notification delivery tracking model.
    
    Tracks all outbound notifications (email, WhatsApp, SMS) for
    debugging and resending failed notifications.
    """
    __tablename__ = "notifications"
    
    # Primary Key (BigInteger for high volume)
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="Notification ID"
    )
    
    # Linkage
    layover_id = Column(
        Integer,
        ForeignKey('layovers.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment="Associated layover (if applicable)"
    )
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment="Recipient user (if internal)"
    )
    
    # Notification Details
    notification_type = Column(
        SQLEnum(NotificationType),
        nullable=False,
        index=True,
        comment="Notification type"
    )
    
    # Recipient
    recipient_email = Column(
        String(255),
        nullable=True,
        comment="Recipient email address"
    )
    recipient_phone = Column(
        String(20),
        nullable=True,
        comment="Recipient phone number"
    )
    
    # Channel
    channel = Column(
        SQLEnum(NotificationChannel),
        nullable=False,
        index=True,
        comment="Delivery channel"
    )
    
    # Content
    subject = Column(
        String(500),
        nullable=True,
        comment="Email subject line"
    )
    body_text = Column(
        Text,
        nullable=True,
        comment="Plain text body"
    )
    body_html = Column(
        Text,
        nullable=True,
        comment="HTML body"
    )
    template_name = Column(
        String(100),
        nullable=True,
        comment="Template used for rendering"
    )
    
    # Delivery Status
    status = Column(
        SQLEnum(NotificationStatus),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default='pending',
        index=True,
        comment="Delivery status"
    )
    sent_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment="When sent"
    )
    delivered_at = Column(
        DateTime,
        nullable=True,
        comment="When delivered (if confirmed)"
    )
    failed_at = Column(
        DateTime,
        nullable=True,
        comment="When failed"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if failed"
    )
    
    # External Service Response
    external_id = Column(
        String(255),
        nullable=True,
        comment="External service message ID (SendGrid, Twilio, etc.)"
    )
    
    # Retry Logic
    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Number of retry attempts"
    )
    next_retry_at = Column(
        DateTime,
        nullable=True,
        comment="Next retry timestamp"
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_notif_layover', 'layover_id'),
        Index('idx_notif_user', 'user_id'),
        Index('idx_notif_status', 'status'),
        Index('idx_notif_type', 'notification_type'),
        Index('idx_notif_sent', 'sent_at'),
        Index('idx_notif_retry', 'next_retry_at', 'status'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )
    
    def __repr__(self):
        return f"<Notification(id={self.id}, type='{self.notification_type}', status='{self.status}')>"