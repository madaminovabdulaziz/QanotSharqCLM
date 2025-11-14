"""
Crew Service - Business logic layer for crew operations
Handles crew member management and layover assignments
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.crew_member import CrewMember, CrewRank
from app.models.layover_crew import LayoverCrew, NotificationStatus
from app.models.user import User
from app.repositories.crew_member_repository import CrewMemberRepository
from app.repositories.layover_crew_repository import LayoverCrewRepository
from app.repositories.layover_repository import LayoverRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.crew import (
    CrewMemberCreate,
    CrewMemberUpdate,
    CrewMemberResponse,
    CrewMemberListResponse,
    CrewFilterParams,
    LayoverCrewCreate,
    LayoverCrewBulkCreate,
    LayoverCrewUpdate,
    LayoverCrewResponse,
    LayoverCrewListResponse,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
    BusinessRuleException,
)

logger = logging.getLogger(__name__)


class CrewService:
    """Service for crew member and assignment business logic"""

    def __init__(self, db: Session, current_user: Optional[User] = None):
        self.db = db
        self.current_user = current_user
        self.crew_repo = CrewMemberRepository(db)
        self.layover_crew_repo = LayoverCrewRepository(db)
        self.layover_repo = LayoverRepository(db)
        self.audit_repo = AuditRepository(db)

    # ==================== CREW MEMBER CRUD ====================

    def create_crew_member(self, data: CrewMemberCreate) -> CrewMemberResponse:
        """
        Create a new crew member.

        Args:
            data: CrewMemberCreate schema

        Returns:
            Created crew member response

        Raises:
            ValidationException: If employee_id or email already exists
            PermissionDeniedException: If user lacks permission
        """
        # Permission check
        if not self._can_manage_crew():
            raise PermissionDeniedException("User cannot manage crew members")

        # Validate unique employee ID
        if self.crew_repo.employee_id_exists(data.employee_id):
            raise ValidationException(f"Employee ID '{data.employee_id}' already exists")

        # Validate unique email
        if data.email and self.crew_repo.email_exists(data.email):
            raise ValidationException(f"Email '{data.email}' already exists")

        # Create crew member
        crew_member = CrewMember(
            employee_id=data.employee_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            crew_rank=data.crew_rank,
            seniority_number=data.seniority_number,
            accommodation_preferences=data.accommodation_preferences,
            medical_restrictions=data.medical_restrictions,
            is_active=True,
        )

        crew_member = self.crew_repo.create(crew_member)

        # Audit log
        self._log_audit(
            action="crew_member_created",
            entity_id=crew_member.id,
            details={
                "employee_id": crew_member.employee_id,
                "crew_rank": crew_member.crew_rank.value,
                "name": f"{crew_member.first_name} {crew_member.last_name}",
            },
        )

        return CrewMemberResponse.model_validate(crew_member)

    def get_crew_member(self, crew_id: int) -> CrewMemberResponse:
        """
        Get crew member by ID.

        Args:
            crew_id: Crew member ID

        Returns:
            Crew member response

        Raises:
            NotFoundException: If crew member not found
        """
        crew_member = self.crew_repo.get_by_id(crew_id)
        if not crew_member:
            raise NotFoundException(f"Crew member {crew_id} not found")

        return CrewMemberResponse.model_validate(crew_member)

    def list_crew_members(self, filters: CrewFilterParams) -> CrewMemberListResponse:
        """
        List crew members with filtering and pagination.

        Args:
            filters: Filter parameters

        Returns:
            Paginated crew member list
        """
        skip = (filters.page - 1) * filters.page_size

        crew_members = self.crew_repo.get_all(
            skip=skip,
            limit=filters.page_size,
            is_active=filters.is_active,
            crew_rank=filters.crew_rank,
            search=filters.search,
        )

        total = self.crew_repo.count(is_active=filters.is_active)

        items = [CrewMemberResponse.model_validate(cm) for cm in crew_members]

        total_pages = (total + filters.page_size - 1) // filters.page_size

        return CrewMemberListResponse(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
        )

    def update_crew_member(self, crew_id: int, data: CrewMemberUpdate) -> CrewMemberResponse:
        """
        Update crew member.

        Args:
            crew_id: Crew member ID
            data: Update data

        Returns:
            Updated crew member response

        Raises:
            NotFoundException: If crew member not found
            ValidationException: If employee_id or email already exists
            PermissionDeniedException: If user lacks permission
        """
        if not self._can_manage_crew():
            raise PermissionDeniedException("User cannot manage crew members")

        crew_member = self.crew_repo.get_by_id(crew_id)
        if not crew_member:
            raise NotFoundException(f"Crew member {crew_id} not found")

        update_data = data.model_dump(exclude_unset=True)

        # Validate unique employee ID if changed
        if "employee_id" in update_data:
            if self.crew_repo.employee_id_exists(update_data["employee_id"], exclude_id=crew_id):
                raise ValidationException(f"Employee ID '{update_data['employee_id']}' already exists")

        # Validate unique email if changed
        if "email" in update_data and update_data["email"]:
            if self.crew_repo.email_exists(update_data["email"], exclude_id=crew_id):
                raise ValidationException(f"Email '{update_data['email']}' already exists")

        # Apply updates
        for key, value in update_data.items():
            setattr(crew_member, key, value)

        crew_member = self.crew_repo.update(crew_member)

        # Audit log
        self._log_audit(
            action="crew_member_updated",
            entity_id=crew_member.id,
            details={"updated_fields": list(update_data.keys())},
        )

        return CrewMemberResponse.model_validate(crew_member)

    def deactivate_crew_member(self, crew_id: int) -> CrewMemberResponse:
        """
        Deactivate crew member (soft delete).

        Args:
            crew_id: Crew member ID

        Returns:
            Deactivated crew member

        Raises:
            NotFoundException: If crew member not found
            PermissionDeniedException: If user lacks permission
        """
        if not self._can_manage_crew():
            raise PermissionDeniedException("User cannot manage crew members")

        crew_member = self.crew_repo.deactivate(crew_id)
        if not crew_member:
            raise NotFoundException(f"Crew member {crew_id} not found")

        # Audit log
        self._log_audit(
            action="crew_member_deactivated",
            entity_id=crew_member.id,
            details={"employee_id": crew_member.employee_id},
        )

        return CrewMemberResponse.model_validate(crew_member)

    # ==================== LAYOVER CREW ASSIGNMENTS ====================

    def assign_crew_to_layover(
        self,
        layover_id: int,
        data: LayoverCrewCreate
    ) -> LayoverCrewResponse:
        """
        Assign a single crew member to a layover.

        Args:
            layover_id: Layover ID
            data: Crew assignment data

        Returns:
            Created assignment

        Raises:
            NotFoundException: If layover or crew member not found
            ValidationException: If crew member already assigned
            BusinessRuleException: If crew count exceeded
        """
        # Validate layover exists
        layover = self.layover_repo.get_by_id(layover_id)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        # Validate crew member exists and is active
        crew_member = self.crew_repo.get_by_id(data.crew_member_id)
        if not crew_member:
            raise NotFoundException(f"Crew member {data.crew_member_id} not found")

        if not crew_member.is_active:
            raise ValidationException(f"Crew member {data.crew_member_id} is inactive")

        # Check if already assigned
        if self.layover_crew_repo.assignment_exists(layover_id, data.crew_member_id):
            raise ValidationException(
                f"Crew member {data.crew_member_id} already assigned to layover {layover_id}"
            )

        # Check crew count limit
        current_count = self.layover_crew_repo.count_by_layover(layover_id)
        if current_count >= layover.crew_count:
            raise BusinessRuleException(
                f"Crew count limit ({layover.crew_count}) reached for layover {layover_id}"
            )

        # Calculate room allocation priority based on rank
        priority = self._get_rank_priority(crew_member.crew_rank)

        # Create assignment
        assignment = LayoverCrew(
            layover_id=layover_id,
            crew_member_id=data.crew_member_id,
            room_number=data.room_number,
            room_type=data.room_type,
            room_allocation_priority=priority,
            is_primary_contact=data.is_primary_contact,
            notification_status=NotificationStatus.PENDING,
        )

        assignment = self.layover_crew_repo.create(assignment)

        # If set as primary, clear others
        if data.is_primary_contact:
            self.layover_crew_repo.set_primary_contact(layover_id, data.crew_member_id)

        # Audit log
        self._log_audit(
            action="crew_assigned_to_layover",
            entity_id=layover_id,
            details={
                "crew_member_id": data.crew_member_id,
                "employee_id": crew_member.employee_id,
                "rank": crew_member.crew_rank.value,
                "is_primary_contact": data.is_primary_contact,
            },
        )

        # Load relationships for response
        assignment = self.layover_crew_repo.get_by_id(assignment.id, load_relations=True)
        return LayoverCrewResponse.model_validate(assignment)

    def bulk_assign_crew(
        self,
        layover_id: int,
        data: LayoverCrewBulkCreate
    ) -> LayoverCrewListResponse:
        """
        Assign multiple crew members to a layover.

        Args:
            layover_id: Layover ID
            data: Bulk assignment data

        Returns:
            List of created assignments

        Raises:
            NotFoundException: If layover not found
            ValidationException: If crew members invalid
            BusinessRuleException: If crew count exceeded
        """
        # Validate layover exists
        layover = self.layover_repo.get_by_id(layover_id)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        # Validate crew count
        if len(data.crew_member_ids) > layover.crew_count:
            raise BusinessRuleException(
                f"Cannot assign {len(data.crew_member_ids)} crew members. "
                f"Layover crew count is {layover.crew_count}"
            )

        assignments = []
        primary_contact_set = False

        for crew_member_id in data.crew_member_ids:
            # Validate crew member
            crew_member = self.crew_repo.get_by_id(crew_member_id)
            if not crew_member:
                raise NotFoundException(f"Crew member {crew_member_id} not found")

            if not crew_member.is_active:
                raise ValidationException(f"Crew member {crew_member_id} is inactive")

            # Skip if already assigned
            if self.layover_crew_repo.assignment_exists(layover_id, crew_member_id):
                continue

            # Calculate priority
            priority = self._get_rank_priority(crew_member.crew_rank)

            # Auto-assign primary contact if requested
            is_primary = False
            if data.auto_assign_primary and not primary_contact_set:
                if crew_member.crew_rank in [CrewRank.CAPTAIN, CrewRank.PURSER]:
                    is_primary = True
                    primary_contact_set = True

            # Create assignment
            assignment = LayoverCrew(
                layover_id=layover_id,
                crew_member_id=crew_member_id,
                room_allocation_priority=priority,
                is_primary_contact=is_primary,
                notification_status=NotificationStatus.PENDING,
            )
            assignments.append(assignment)

        # Bulk create
        created_assignments = self.layover_crew_repo.bulk_create(assignments)

        # Audit log
        self._log_audit(
            action="bulk_crew_assignment",
            entity_id=layover_id,
            details={
                "crew_member_ids": data.crew_member_ids,
                "count": len(created_assignments),
                "auto_assign_primary": data.auto_assign_primary,
            },
        )

        # Load relationships for response
        assignments_with_relations = self.layover_crew_repo.get_by_layover_id(
            layover_id, load_relations=True
        )

        items = [LayoverCrewResponse.model_validate(a) for a in assignments_with_relations]

        return LayoverCrewListResponse(items=items, total=len(items))

    def update_crew_assignment(
        self,
        assignment_id: int,
        data: LayoverCrewUpdate
    ) -> LayoverCrewResponse:
        """
        Update crew assignment details.

        Args:
            assignment_id: Assignment ID
            data: Update data

        Returns:
            Updated assignment
        """
        assignment = self.layover_crew_repo.get_by_id(assignment_id)
        if not assignment:
            raise NotFoundException(f"Assignment {assignment_id} not found")

        update_data = data.model_dump(exclude_unset=True)

        # Apply updates
        for key, value in update_data.items():
            if key == "is_primary_contact" and value:
                # Set as primary contact
                self.layover_crew_repo.set_primary_contact(
                    assignment.layover_id,
                    assignment.crew_member_id
                )
            else:
                setattr(assignment, key, value)

        assignment = self.layover_crew_repo.update(assignment)

        # Audit log
        self._log_audit(
            action="crew_assignment_updated",
            entity_id=assignment.layover_id,
            details={
                "assignment_id": assignment_id,
                "updated_fields": list(update_data.keys()),
            },
        )

        # Load relationships for response
        assignment = self.layover_crew_repo.get_by_id(assignment_id, load_relations=True)
        return LayoverCrewResponse.model_validate(assignment)

    def remove_crew_from_layover(self, layover_id: int, crew_member_id: int) -> dict:
        """
        Remove crew member from layover.

        Args:
            layover_id: Layover ID
            crew_member_id: Crew member ID

        Returns:
            Success message

        Raises:
            NotFoundException: If assignment not found
        """
        removed = self.layover_crew_repo.remove_crew_member(layover_id, crew_member_id)
        if not removed:
            raise NotFoundException(
                f"Crew member {crew_member_id} not assigned to layover {layover_id}"
            )

        # Audit log
        self._log_audit(
            action="crew_removed_from_layover",
            entity_id=layover_id,
            details={"crew_member_id": crew_member_id},
        )

        return {"message": "Crew member removed successfully"}

    def get_layover_crew(self, layover_id: int) -> LayoverCrewListResponse:
        """
        Get all crew assigned to a layover.

        Args:
            layover_id: Layover ID

        Returns:
            List of crew assignments
        """
        assignments = self.layover_crew_repo.get_by_layover_id(layover_id, load_relations=True)

        items = [LayoverCrewResponse.model_validate(a) for a in assignments]

        return LayoverCrewListResponse(items=items, total=len(items))

    # ==================== HELPER METHODS ====================

    def _can_manage_crew(self) -> bool:
        """Check if current user can manage crew members"""
        if not self.current_user:
            return False
        return self.current_user.role in ["admin", "ops_coordinator", "supervisor"]

    def _get_rank_priority(self, rank: CrewRank) -> int:
        """
        Get room allocation priority based on crew rank.
        Lower number = higher priority.
        """
        priority_map = {
            CrewRank.CAPTAIN: 1,
            CrewRank.FIRST_OFFICER: 2,
            CrewRank.SECOND_OFFICER: 3,
            CrewRank.PURSER: 4,
            CrewRank.CABIN_SERVICE_MANAGER: 5,
            CrewRank.SENIOR_FLIGHT_ATTENDANT: 6,
            CrewRank.FLIGHT_ATTENDANT: 7,
        }
        return priority_map.get(rank, 99)

    def _log_audit(self, action: str, entity_id: int, details: dict) -> None:
        """Log audit trail"""
        if not self.current_user:
            return

        try:
            self.audit_repo.log(
                user_id=self.current_user.id,
                action=action,
                entity_type="crew",
                entity_id=entity_id,
                details=details,
            )
        except Exception as e:
            logger.error(f"Failed to log audit: {e}")
