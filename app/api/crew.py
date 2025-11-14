"""
Crew API Router - REST endpoints for crew member management
Includes CRUD operations for crew members
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.crew_member import CrewRank
from app.services.crew_service import CrewService
from app.schemas.crew import (
    CrewMemberCreate,
    CrewMemberUpdate,
    CrewMemberResponse,
    CrewMemberListResponse,
    CrewFilterParams,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
    BusinessRuleException
)


router = APIRouter(prefix="/crew", tags=["Crew Members"])


# ==================== HELPER FUNCTIONS ====================

def get_crew_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CrewService:
    """Dependency to get crew service with current user"""
    return CrewService(db=db, current_user=current_user)


# ==================== CREATE ====================

@router.post(
    "",
    response_model=CrewMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new crew member",
    description="Create a new crew member profile. Requires admin/ops coordinator permissions."
)
def create_crew_member(
    data: CrewMemberCreate,
    service: CrewService = Depends(get_crew_service)
):
    """
    Create a new crew member

    - **Validates unique employee_id and email**
    - **Sets crew rank and seniority**
    - **Logs audit trail**

    Required permissions: admin, ops_coordinator, supervisor
    """
    try:
        return service.create_crew_member(data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== READ ====================

@router.get(
    "",
    response_model=CrewMemberListResponse,
    summary="List crew members",
    description="List crew members with filtering, search, and pagination"
)
def list_crew_members(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, max_length=100, description="Search by name or employee ID"),
    crew_rank: Optional[CrewRank] = Query(None, description="Filter by crew rank"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    service: CrewService = Depends(get_crew_service)
):
    """
    List crew members with filtering and pagination

    - **Search by name or employee ID**
    - **Filter by rank, active status**
    - **Paginated results**
    """
    try:
        filters = CrewFilterParams(
            page=page,
            page_size=page_size,
            search=search,
            crew_rank=crew_rank,
            is_active=is_active
        )
        return service.list_crew_members(filters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{crew_id}",
    response_model=CrewMemberResponse,
    summary="Get crew member by ID",
    description="Retrieve a specific crew member's details"
)
def get_crew_member(
    crew_id: int,
    service: CrewService = Depends(get_crew_service)
):
    """
    Get crew member details

    - **Returns crew member profile**
    - **Includes rank, seniority, preferences**
    """
    try:
        return service.get_crew_member(crew_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== UPDATE ====================

@router.put(
    "/{crew_id}",
    response_model=CrewMemberResponse,
    summary="Update crew member",
    description="Update crew member details. Requires admin/ops coordinator permissions."
)
def update_crew_member(
    crew_id: int,
    data: CrewMemberUpdate,
    service: CrewService = Depends(get_crew_service)
):
    """
    Update crew member details

    - **Partial updates supported**
    - **Validates unique employee_id and email**
    - **Logs audit trail**

    Required permissions: admin, ops_coordinator, supervisor
    """
    try:
        return service.update_crew_member(crew_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== DEACTIVATE ====================

@router.delete(
    "/{crew_id}",
    response_model=CrewMemberResponse,
    summary="Deactivate crew member",
    description="Soft delete crew member (sets is_active=False). Requires admin/ops coordinator permissions."
)
def deactivate_crew_member(
    crew_id: int,
    service: CrewService = Depends(get_crew_service)
):
    """
    Deactivate crew member (soft delete)

    - **Sets is_active=False**
    - **Preserves historical data**
    - **Logs audit trail**

    Required permissions: admin, ops_coordinator, supervisor
    """
    try:
        return service.deactivate_crew_member(crew_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
