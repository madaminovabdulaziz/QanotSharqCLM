"""
Audit Log Repository
Handles database operations for audit trail (immutable logs)
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.audit_log import AuditLog


class AuditRepository:
    """Repository for audit log database operations"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: Optional[int],
        user_role: Optional[str],
        action_type: str,
        entity_type: str,
        entity_id: int,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an immutable audit log entry
        
        Args:
            user_id: ID of user who performed action (None for system actions)
            user_role: Role of user at time of action
            action_type: Type of action (created, updated, status_changed, etc.)
            entity_type: Type of entity affected (layover, user, hotel, etc.)
            entity_id: ID of the entity
            details: JSON dict with before/after values, notes, metadata
            ip_address: IP address of user
            user_agent: User agent string
        
        Returns:
            AuditLog: Created audit log entry
        """
        audit_log = AuditLog(
            user_id=user_id,
            user_role=user_role,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            log_date=datetime.utcnow().date(),
        )

        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log

    def get_by_entity(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit trail for a specific entity
        
        Args:
            entity_type: Type of entity (layover, user, hotel, etc.)
            entity_id: ID of the entity
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries, newest first
        """
        return (
            self.db.query(AuditLog)
            .filter(
                and_(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id,
                )
            )
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .all()
        )

    def get_by_user(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get all actions performed by a specific user
        
        Args:
            user_id: ID of the user
            start_date: Filter from this date
            end_date: Filter to this date
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries, newest first
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return query.order_by(desc(AuditLog.timestamp)).limit(limit).all()

    def get_system_actions(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get all system-generated actions (user_id is NULL)
        
        Args:
            start_date: Filter from this date
            end_date: Filter to this date
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries for system actions
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id.is_(None))

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return query.order_by(desc(AuditLog.timestamp)).limit(limit).all()

    def get_by_action_type(
        self,
        action_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get all logs of a specific action type
        
        Args:
            action_type: Type of action to filter by
            start_date: Filter from this date
            end_date: Filter to this date
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries
        """
        query = self.db.query(AuditLog).filter(AuditLog.action_type == action_type)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return query.order_by(desc(AuditLog.timestamp)).limit(limit).all()

    def get_recent_activity(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get recent activity across all entities
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of records to return
        
        Returns:
            List of recent AuditLog entries
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.timestamp >= cutoff_time)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .all()
        )

    def count_actions_by_user(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count total actions performed by a user in date range
        
        Args:
            user_id: ID of the user
            start_date: Filter from this date
            end_date: Filter to this date
        
        Returns:
            Count of actions
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)

        return query.count()

    def get_entity_history_summary(
        self,
        entity_type: str,
        entity_id: int,
    ) -> dict:
        """
        Get a summary of key events in an entity's history
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
        
        Returns:
            Dict with key timestamps and counts
        """
        logs = self.get_by_entity(entity_type, entity_id, limit=1000)

        summary = {
            "total_actions": len(logs),
            "created_at": None,
            "last_updated_at": None,
            "unique_users": set(),
            "action_counts": {},
        }

        for log in logs:
            # Track unique users
            if log.user_id:
                summary["unique_users"].add(log.user_id)

            # Count action types
            action = log.action_type
            summary["action_counts"][action] = summary["action_counts"].get(action, 0) + 1

            # Find created timestamp
            if log.action_type == "created" and not summary["created_at"]:
                summary["created_at"] = log.timestamp

        # Last updated is most recent timestamp
        if logs:
            summary["last_updated_at"] = logs[0].timestamp

        summary["unique_users"] = len(summary["unique_users"])

        return summary