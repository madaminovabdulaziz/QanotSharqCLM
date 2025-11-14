"""
Crew Member Repository - Database Access Layer
Handles all database operations for CrewMember entity.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.crew_member import CrewMember, CrewRank


class CrewMemberRepository:
    """
    Repository for CrewMember model database operations.

    Provides clean separation between business logic and data access.
    All database queries for crew members go through this repository.
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ========================================
    # READ
    # ========================================

    def get_by_id(self, crew_id: int) -> Optional[CrewMember]:
        """
        Get crew member by ID.

        Args:
            crew_id: Crew member ID

        Returns:
            CrewMember instance or None if not found
        """
        return self.db.query(CrewMember).filter(CrewMember.id == crew_id).first()

    def get_by_employee_id(self, employee_id: str) -> Optional[CrewMember]:
        """
        Get crew member by employee ID.

        Args:
            employee_id: Employee ID (airline employee number)

        Returns:
            CrewMember instance or None if not found
        """
        return self.db.query(CrewMember).filter(CrewMember.employee_id == employee_id).first()

    def get_by_email(self, email: str) -> Optional[CrewMember]:
        """
        Get crew member by email.

        Args:
            email: Email address

        Returns:
            CrewMember instance or None if not found
        """
        return self.db.query(CrewMember).filter(CrewMember.email == email).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        crew_rank: Optional[CrewRank] = None,
        search: Optional[str] = None
    ) -> List[CrewMember]:
        """
        Get all crew members with pagination and filtering.

        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            is_active: Filter by active status (None = all)
            crew_rank: Filter by crew rank (None = all ranks)
            search: Search by name or employee ID

        Returns:
            List of crew members
        """
        query = self.db.query(CrewMember)

        if is_active is not None:
            query = query.filter(CrewMember.is_active == is_active)

        if crew_rank is not None:
            query = query.filter(CrewMember.crew_rank == crew_rank)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    CrewMember.first_name.ilike(search_pattern),
                    CrewMember.last_name.ilike(search_pattern),
                    CrewMember.employee_id.ilike(search_pattern),
                    CrewMember.email.ilike(search_pattern)
                )
            )

        return query.offset(skip).limit(limit).all()

    def get_by_rank(self, crew_rank: CrewRank) -> List[CrewMember]:
        """
        Get all crew members with a specific rank.

        Args:
            crew_rank: Crew rank to filter by

        Returns:
            List of crew members with that rank
        """
        return (
            self.db.query(CrewMember)
            .filter(CrewMember.crew_rank == crew_rank, CrewMember.is_active == True)
            .all()
        )

    def get_pilots(self, is_active: Optional[bool] = True) -> List[CrewMember]:
        """
        Get all pilots (Captain, First Officer, Second Officer).

        Args:
            is_active: Filter by active status (None = all)

        Returns:
            List of pilots
        """
        query = self.db.query(CrewMember).filter(
            CrewMember.crew_rank.in_([
                CrewRank.CAPTAIN,
                CrewRank.FIRST_OFFICER,
                CrewRank.SECOND_OFFICER
            ])
        )

        if is_active is not None:
            query = query.filter(CrewMember.is_active == is_active)

        return query.all()

    def get_cabin_crew(self, is_active: Optional[bool] = True) -> List[CrewMember]:
        """
        Get all cabin crew (Purser, CSM, SFA, FA).

        Args:
            is_active: Filter by active status (None = all)

        Returns:
            List of cabin crew
        """
        query = self.db.query(CrewMember).filter(
            CrewMember.crew_rank.in_([
                CrewRank.PURSER,
                CrewRank.CABIN_SERVICE_MANAGER,
                CrewRank.SENIOR_FLIGHT_ATTENDANT,
                CrewRank.FLIGHT_ATTENDANT
            ])
        )

        if is_active is not None:
            query = query.filter(CrewMember.is_active == is_active)

        return query.all()

    # ========================================
    # CREATE
    # ========================================

    def create(self, crew_member: CrewMember) -> CrewMember:
        """
        Create a new crew member.

        Args:
            crew_member: CrewMember model instance to create

        Returns:
            Created crew member instance
        """
        self.db.add(crew_member)
        self.db.commit()
        self.db.refresh(crew_member)
        return crew_member

    # ========================================
    # UPDATE
    # ========================================

    def update(self, crew_member: CrewMember) -> CrewMember:
        """
        Update an existing crew member.

        Args:
            crew_member: CrewMember model instance with updated fields

        Returns:
            Updated crew member instance
        """
        self.db.commit()
        self.db.refresh(crew_member)
        return crew_member

    def activate(self, crew_id: int) -> Optional[CrewMember]:
        """
        Activate a crew member.

        Args:
            crew_id: Crew member ID to activate

        Returns:
            Activated crew member or None if not found
        """
        crew_member = self.get_by_id(crew_id)
        if not crew_member:
            return None

        crew_member.is_active = True
        self.db.commit()
        self.db.refresh(crew_member)
        return crew_member

    def deactivate(self, crew_id: int) -> Optional[CrewMember]:
        """
        Deactivate a crew member (soft delete).

        Args:
            crew_id: Crew member ID to deactivate

        Returns:
            Deactivated crew member or None if not found
        """
        crew_member = self.get_by_id(crew_id)
        if not crew_member:
            return None

        crew_member.is_active = False
        self.db.commit()
        self.db.refresh(crew_member)
        return crew_member

    # ========================================
    # DELETE
    # ========================================

    def delete(self, crew_member: CrewMember) -> None:
        """
        Delete a crew member (hard delete).

        Note: This permanently removes the crew member from the database.
        Consider using deactivate() instead to preserve historical data.

        Args:
            crew_member: CrewMember instance to delete
        """
        self.db.delete(crew_member)
        self.db.commit()

    # ========================================
    # VALIDATION & UTILITIES
    # ========================================

    def employee_id_exists(self, employee_id: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if an employee ID already exists.

        Args:
            employee_id: Employee ID to check
            exclude_id: Crew member ID to exclude from check (for updates)

        Returns:
            True if employee ID exists, False otherwise
        """
        query = self.db.query(CrewMember).filter(CrewMember.employee_id == employee_id)

        if exclude_id:
            query = query.filter(CrewMember.id != exclude_id)

        return query.first() is not None

    def email_exists(self, email: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if a crew member email already exists.

        Args:
            email: Email to check
            exclude_id: Crew member ID to exclude from check (for updates)

        Returns:
            True if email exists, False otherwise
        """
        query = self.db.query(CrewMember).filter(CrewMember.email == email)

        if exclude_id:
            query = query.filter(CrewMember.id != exclude_id)

        return query.first() is not None

    def count(self, is_active: Optional[bool] = None) -> int:
        """
        Count total crew members.

        Args:
            is_active: Filter by active status (None = all)

        Returns:
            Count of crew members
        """
        query = self.db.query(CrewMember)

        if is_active is not None:
            query = query.filter(CrewMember.is_active == is_active)

        return query.count()

    def count_by_rank(self, crew_rank: CrewRank, is_active: Optional[bool] = True) -> int:
        """
        Count crew members by rank.

        Args:
            crew_rank: Crew rank to count
            is_active: Filter by active status (None = all)

        Returns:
            Count of crew members with that rank
        """
        query = self.db.query(CrewMember).filter(CrewMember.crew_rank == crew_rank)

        if is_active is not None:
            query = query.filter(CrewMember.is_active == is_active)

        return query.count()
