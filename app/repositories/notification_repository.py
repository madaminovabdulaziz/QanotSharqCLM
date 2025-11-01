"""
Notification Repository
Handles database operations for notification tracking (email, WhatsApp, SMS)
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.notification import Notification


class NotificationRepository:
    """Repository for notification database operations"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        layover_id: Optional[int],
        user_id: Optional[int],
        notification_type: str,
        recipient_email: Optional[str],
        recipient_phone: Optional[str],
        channel: str,
        subject: Optional[str],
        body_text: Optional[str],
        body_html: Optional[str],
        template_name: Optional[str],
    ) -> Notification:
        """
        Create a notification record
        
        Args:
            layover_id: ID of related layover (optional)
            user_id: ID of recipient user (optional, for internal notifications)
            notification_type: Type of notification
            recipient_email: Email address (for email channel)
            recipient_phone: Phone number (for WhatsApp/SMS)
            channel: Delivery channel (email, whatsapp, sms, in_app)
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body
            template_name: Name of template used
        
        Returns:
            Notification: Created notification object
        """
        notification = Notification(
            layover_id=layover_id,
            user_id=user_id,
            notification_type=notification_type,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            channel=channel,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            template_name=template_name,
            status="pending",
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_as_sent(
        self,
        notification_id: int,
        external_id: Optional[str] = None,
    ) -> Notification:
        """
        Mark notification as sent
        
        Args:
            notification_id: ID of the notification
            external_id: External service message ID (e.g., SendGrid message ID)
        
        Returns:
            Updated Notification
        """
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()

        if notification:
            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
            notification.external_id = external_id
            self.db.commit()
            self.db.refresh(notification)

        return notification

    def mark_as_delivered(self, notification_id: int) -> Notification:
        """
        Mark notification as delivered (e.g., webhook from email service)
        
        Args:
            notification_id: ID of the notification
        
        Returns:
            Updated Notification
        """
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()

        if notification:
            notification.status = "delivered"
            notification.delivered_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(notification)

        return notification

    def mark_as_failed(
        self,
        notification_id: int,
        error_message: str,
    ) -> Notification:
        """
        Mark notification as failed
        
        Args:
            notification_id: ID of the notification
            error_message: Error details
        
        Returns:
            Updated Notification
        """
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()

        if notification:
            notification.status = "failed"
            notification.failed_at = datetime.utcnow()
            notification.error_message = error_message
            notification.retry_count += 1
            self.db.commit()
            self.db.refresh(notification)

        return notification

    def schedule_retry(
        self,
        notification_id: int,
        retry_after_minutes: int = 5,
    ) -> Notification:
        """
        Schedule notification for retry
        
        Args:
            notification_id: ID of the notification
            retry_after_minutes: Minutes to wait before retry
        
        Returns:
            Updated Notification
        """
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()

        if notification:
            notification.next_retry_at = datetime.utcnow() + timedelta(
                minutes=retry_after_minutes
            )
            notification.status = "pending"
            self.db.commit()
            self.db.refresh(notification)

        return notification

    def get_by_id(self, notification_id: int) -> Optional[Notification]:
        """Get notification by ID"""
        return self.db.query(Notification).filter(
            Notification.id == notification_id
        ).first()

    def get_by_layover(self, layover_id: int) -> List[Notification]:
        """
        Get all notifications for a specific layover
        
        Args:
            layover_id: ID of the layover
        
        Returns:
            List of Notification objects
        """
        return (
            self.db.query(Notification)
            .filter(Notification.layover_id == layover_id)
            .order_by(desc(Notification.created_at))
            .all()
        )

    def get_pending_retries(self) -> List[Notification]:
        """
        Get notifications that need to be retried
        
        Returns:
            List of notifications ready for retry
        """
        return (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.status == "pending",
                    Notification.next_retry_at.isnot(None),
                    Notification.next_retry_at <= datetime.utcnow(),
                    Notification.retry_count < 3,  # Max 3 retries
                )
            )
            .all()
        )

    def get_failed_notifications(
        self,
        hours: int = 24,
    ) -> List[Notification]:
        """
        Get recently failed notifications for debugging
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            List of failed notifications
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.status == "failed",
                    Notification.failed_at >= cutoff_time,
                )
            )
            .order_by(desc(Notification.failed_at))
            .all()
        )

    def get_delivery_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Get delivery statistics
        
        Args:
            start_date: Filter from this date
            end_date: Filter to this date
        
        Returns:
            Dict with delivery stats
        """
        query = self.db.query(Notification)

        if start_date:
            query = query.filter(Notification.created_at >= start_date)
        if end_date:
            query = query.filter(Notification.created_at <= end_date)

        notifications = query.all()

        stats = {
            "total": len(notifications),
            "sent": 0,
            "delivered": 0,
            "failed": 0,
            "pending": 0,
            "by_channel": {},
            "by_type": {},
        }

        for notif in notifications:
            # Count by status
            if notif.status == "sent":
                stats["sent"] += 1
            elif notif.status == "delivered":
                stats["delivered"] += 1
            elif notif.status == "failed":
                stats["failed"] += 1
            elif notif.status == "pending":
                stats["pending"] += 1

            # Count by channel
            channel = notif.channel
            stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1

            # Count by type
            notif_type = notif.notification_type
            stats["by_type"][notif_type] = stats["by_type"].get(notif_type, 0) + 1

        return stats

    def cleanup_old_notifications(self, days_old: int = 90) -> int:
        """
        Delete old delivered notifications (housekeeping)
        
        Args:
            days_old: Delete notifications older than this many days
        
        Returns:
            Number of notifications deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        deleted_count = (
            self.db.query(Notification)
            .filter(
                and_(
                    Notification.status == "delivered",
                    Notification.delivered_at < cutoff_date,
                )
            )
            .delete(synchronize_session=False)
        )
        
        self.db.commit()
        return deleted_count