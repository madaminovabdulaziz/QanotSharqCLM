"""
Layover Crew Repository - Database Access Layer
Handles all database operations for LayoverCrew entity (crew assignments).
"""
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from datetime import datetime
from app.models.layover_crew import LayoverCrew, NotificationStatus


class LayoverCrewRepository:
    """
    Repository for LayoverCrew model database operations.

    Manages the many-to-many relationship between layovers and crew members.
    Tracks crew assignments, room allocations, and notification status.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ========================================
    # READ
    # ========================================

    def get_by_id(self, assignment_id: int, load_relations: bool = False) -> Optional[LayoverCrew]:
        """
        Get crew assignment by ID.

        Args:
            assignment_id: Assignment ID
            load_relations: Load crew_member and layover relationships

        Returns:
            LayoverCrew instance or None if not found
        """
        query = self.db.query(LayoverCrew).filter(LayoverCrew.id == assignment_id)

        if load_relations:
            query = query.options(joinedload(LayoverCrew.crew_member), joinedload(LayoverCrew.layover))

        return query.first()

    def get_by_layover_id(
        self,
        layover_id: int,
        load_relations: bool = False
    ) -> List[LayoverCrew]:
        """
        Get all crew assignments for a specific layover.

        Args:
            layover_id: Layover ID
            load_relations: Load crew_member relationships

        Returns:
            List of crew assignments
        """
        query = self.db.query(LayoverCrew).filter(LayoverCrew.layover_id == layover_id)

        if load_relations:
            query = query.options(joinedload(LayoverCrew.crew_member))

        return query.all()

    def get_by_crew_member_id(
        self,
        crew_member_id: int,
        skip: int = 0,
        limit: int = 100,
        load_relations: bool = False
    ) -> List[LayoverCrew]:
        """
        Get all layover assignments for a specific crew member.

        Args:
            crew_member_id: Crew member ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            load_relations: Load layover relationships

        Returns:
            List of assignments ordered by created_at DESC
        """
        query = self.db.query(LayoverCrew).filter(LayoverCrew.crew_member_id == crew_member_id)

        if load_relations:
            query = query.options(joinedload(LayoverCrew.layover))

        return (
            query
            .order_by(desc(LayoverCrew.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_assignment(
        self,
        layover_id: int,
        crew_member_id: int
    ) -> Optional[LayoverCrew]:
        """
        Get specific crew assignment for a layover.

        Args:
            layover_id: Layover ID
            crew_member_id: Crew member ID

        Returns:
            LayoverCrew instance or None if not found
        """
        return (
            self.db.query(LayoverCrew)
            .filter(
                LayoverCrew.layover_id == layover_id,
                LayoverCrew.crew_member_id == crew_member_id
            )
            .first()
        )

    def get_primary_contact(self, layover_id: int) -> Optional[LayoverCrew]:
        """
        Get the primary contact for a layover (Captain or Purser).

        Args:
            layover_id: Layover ID

        Returns:
            Primary contact assignment or None if not set
        """
        return (
            self.db.query(LayoverCrew)
            .filter(
                LayoverCrew.layover_id == layover_id,
                LayoverCrew.is_primary_contact == True
            )
            .options(joinedload(LayoverCrew.crew_member))
            .first()
        )

    def get_by_notification_status(
        self,
        notification_status: NotificationStatus,
        skip: int = 0,
        limit: int = 100
    ) -> List[LayoverCrew]:
        """
        Get assignments by notification status.

        Useful for finding pending notifications or failed deliveries.

        Args:
            notification_status: Notification status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of assignments
        """
        return (
            self.db.query(LayoverCrew)
            .filter(LayoverCrew.notification_status == notification_status)
            .options(joinedload(LayoverCrew.crew_member), joinedload(LayoverCrew.layover))
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ========================================
    # CREATE
    # ========================================

    def create(self, assignment: LayoverCrew) -> LayoverCrew:
        """
        Create a new crew assignment.

        Args:
            assignment: LayoverCrew model instance to create

        Returns:
            Created assignment instance
        """
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def bulk_create(self, assignments: List[LayoverCrew]) -> List[LayoverCrew]:
        """
        Create multiple crew assignments at once.

        Args:
            assignments: List of LayoverCrew instances to create

        Returns:
            List of created assignments
        """
        self.db.add_all(assignments)
        self.db.commit()
        for assignment in assignments:
            self.db.refresh(assignment)
        return assignments

    # ========================================
    # UPDATE
    # ========================================

    def update(self, assignment: LayoverCrew) -> LayoverCrew:
        """
        Update an existing crew assignment.

        Args:
            assignment: LayoverCrew model instance with updated fields

        Returns:
            Updated assignment instance
        """
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def set_primary_contact(self, layover_id: int, crew_member_id: int) -> Optional[LayoverCrew]:
        """
        Set a crew member as the primary contact for a layover.

        Clears any existing primary contact first.

        Args:
            layover_id: Layover ID
            crew_member_id: Crew member ID to set as primary

        Returns:
            Updated assignment or None if not found
        """
        # Clear existing primary contact
        self.db.query(LayoverCrew).filter(
            LayoverCrew.layover_id == layover_id,
            LayoverCrew.is_primary_contact == True
        ).update({"is_primary_contact": False})

        # Set new primary contact
        assignment = self.get_assignment(layover_id, crew_member_id)
        if not assignment:
            return None

        assignment.is_primary_contact = True
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def update_notification_status(
        self,
        assignment_id: int,
        notification_status: NotificationStatus
    ) -> Optional[LayoverCrew]:
        """
        Update notification status for an assignment.

        Args:
            assignment_id: Assignment ID
            notification_status: New notification status

        Returns:
            Updated assignment or None if not found
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None

        assignment.notification_status = notification_status
        if notification_status == NotificationStatus.SENT:
            assignment.notified_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def update_room_allocation(
        self,
        assignment_id: int,
        room_number: Optional[str] = None,
        room_type: Optional[str] = None
    ) -> Optional[LayoverCrew]:
        """
        Update room allocation for a crew assignment.

        Args:
            assignment_id: Assignment ID
            room_number: Hotel room number
            room_type: Room type (single, double, suite)

        Returns:
            Updated assignment or None if not found
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None

        if room_number is not None:
            assignment.room_number = room_number
        if room_type is not None:
            assignment.room_type = room_type

        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    # ========================================
    # DELETE
    # ========================================

    def delete(self, assignment: LayoverCrew) -> None:
        """
        Delete a crew assignment.

        Args:
            assignment: LayoverCrew instance to delete
        """
        self.db.delete(assignment)
        self.db.commit()

    def delete_by_id(self, assignment_id: int) -> bool:
        """
        Delete a crew assignment by ID.

        Args:
            assignment_id: Assignment ID to delete

        Returns:
            True if deleted, False if not found
        """
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return False

        self.delete(assignment)
        return True

    def delete_by_layover(self, layover_id: int) -> int:
        """
        Delete all crew assignments for a specific layover.

        Used when a layover is deleted (cascade handled by DB).

        Args:
            layover_id: Layover ID

        Returns:
            Number of assignments deleted
        """
        count = self.db.query(LayoverCrew).filter(LayoverCrew.layover_id == layover_id).delete()
        self.db.commit()
        return count

    def remove_crew_member(self, layover_id: int, crew_member_id: int) -> bool:
        """
        Remove a specific crew member from a layover.

        Args:
            layover_id: Layover ID
            crew_member_id: Crew member ID to remove

        Returns:
            True if removed, False if not found
        """
        assignment = self.get_assignment(layover_id, crew_member_id)
        if not assignment:
            return False

        self.delete(assignment)
        return True

    # ========================================
    # UTILITIES
    # ========================================

    def count_by_layover(self, layover_id: int) -> int:
        """
        Count crew members assigned to a layover.

        Args:
            layover_id: Layover ID

        Returns:
            Count of crew assignments
        """
        return self.db.query(LayoverCrew).filter(LayoverCrew.layover_id == layover_id).count()

    def count_by_crew_member(self, crew_member_id: int) -> int:
        """
        Count layovers assigned to a crew member.

        Args:
            crew_member_id: Crew member ID

        Returns:
            Count of layover assignments
        """
        return self.db.query(LayoverCrew).filter(LayoverCrew.crew_member_id == crew_member_id).count()

    def assignment_exists(self, layover_id: int, crew_member_id: int) -> bool:
        """
        Check if a crew member is already assigned to a layover.

        Args:
            layover_id: Layover ID
            crew_member_id: Crew member ID

        Returns:
            True if assignment exists, False otherwise
        """
        return self.get_assignment(layover_id, crew_member_id) is not None

    def count_pending_notifications(self) -> int:
        """
        Count assignments with pending notifications.

        Returns:
            Count of pending notifications
        """
        return (
            self.db.query(LayoverCrew)
            .filter(LayoverCrew.notification_status == NotificationStatus.PENDING)
            .count()
        )
