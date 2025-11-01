"""
Station API Router
Handles all station-related HTTP endpoints with RBAC.
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.station_service import StationService
from app.schemas.station import (
    StationCreate, StationUpdate, StationResponse, 
    StationListResponse, ReminderConfig
)
from app.models.user import User


router = APIRouter(
    prefix="/stations",
    tags=["Stations"]
)


# ========================================
# CREATE
# ========================================

@router.post(
    "",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new station",
    description="Create a new station with reminder configuration. Requires admin role."
)
def create_station(
    station_data: StationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationResponse:
    """
    Create a new station.
    
    **Required Role:** admin
    
    **Business Rules:**
    - Airport code must be unique
    - Timezone must be valid IANA identifier
    - Reminder hours must be logical (2nd > 1st, escalation > 2nd)
    
    **Returns:**
    - 201: Station created successfully
    - 400: Validation error
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 409: Station code already exists
    """
    # RBAC: Only admin can create stations
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create stations"
        )
    
    service = StationService(db)
    return service.create_station(station_data)


# ========================================
# READ
# ========================================

@router.get(
    "",
    response_model=StationListResponse,
    summary="List all stations",
    description="Get paginated list of stations with optional filtering"
)
def list_stations(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (max 100)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in code, name, or city"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationListResponse:
    """
    List all stations with pagination and filtering.
    
    **Required Role:** Any authenticated user
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 25, max: 100)
    - `is_active`: Filter by active status (true/false/null for all)
    - `search`: Search in code, name, or city (case-insensitive)
    
    **Returns:**
    - 200: List of stations with pagination metadata
    - 400: Invalid pagination parameters
    - 401: Not authenticated
    """
    service = StationService(db)
    return service.list_stations(
        page=page,
        page_size=page_size,
        is_active=is_active,
        search=search
    )


@router.get(
    "/active",
    response_model=List[StationResponse],
    summary="Get all active stations",
    description="Get all active stations (for dropdowns, selects)"
)
def get_active_stations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[StationResponse]:
    """
    Get all active stations.
    
    **Required Role:** Any authenticated user
    
    **Use Case:** Populate dropdowns, station selectors
    
    **Returns:**
    - 200: List of active stations (ordered by name)
    - 401: Not authenticated
    """
    service = StationService(db)
    return service.get_active_stations()


@router.get(
    "/statistics",
    response_model=Dict[str, Any],
    summary="Get station statistics",
    description="Get overall station statistics and metrics"
)
def get_station_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get station statistics.
    
    **Required Role:** admin, supervisor, ops_coordinator
    
    **Returns:**
    - 200: Station statistics (total, active, timezone distribution)
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Only admin, supervisor, ops_coordinator can view stats
    if current_user.role not in ["admin", "supervisor", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view statistics"
        )
    
    service = StationService(db)
    return service.get_station_statistics()


@router.get(
    "/{station_id}",
    response_model=StationResponse,
    summary="Get station by ID",
    description="Get detailed information about a specific station"
)
def get_station(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationResponse:
    """
    Get station by ID.
    
    **Required Role:** Any authenticated user
    
    **Path Parameters:**
    - `station_id`: Station ID
    
    **Returns:**
    - 200: Station details
    - 401: Not authenticated
    - 404: Station not found
    """
    service = StationService(db)
    return service.get_station(station_id)


@router.get(
    "/code/{code}",
    response_model=StationResponse,
    summary="Get station by airport code",
    description="Get station by IATA/ICAO code (case-insensitive)"
)
def get_station_by_code(
    code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationResponse:
    """
    Get station by airport code.
    
    **Required Role:** Any authenticated user
    
    **Path Parameters:**
    - `code`: Airport code (e.g., LHR, JFK) - case-insensitive
    
    **Returns:**
    - 200: Station details
    - 401: Not authenticated
    - 404: Station not found
    """
    service = StationService(db)
    return service.get_station_by_code(code)


@router.get(
    "/timezone/{timezone}",
    response_model=List[StationResponse],
    summary="Get stations by timezone",
    description="Get all stations in a specific timezone (for reminder scheduling)"
)
def get_stations_by_timezone(
    timezone: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[StationResponse]:
    """
    Get stations by timezone.
    
    **Required Role:** Any authenticated user
    
    **Path Parameters:**
    - `timezone`: IANA timezone (e.g., Europe/London, America/New_York)
    
    **Use Case:** Reminder scheduling, timezone-specific operations
    
    **Returns:**
    - 200: List of stations in that timezone
    - 400: Invalid timezone
    - 401: Not authenticated
    """
    service = StationService(db)
    return service.get_stations_by_timezone(timezone)


# ========================================
# UPDATE
# ========================================

@router.put(
    "/{station_id}",
    response_model=StationResponse,
    summary="Update station",
    description="Update station details (all fields optional)"
)
def update_station(
    station_id: int,
    station_data: StationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationResponse:
    """
    Update an existing station.
    
    **Required Role:** admin
    
    **Path Parameters:**
    - `station_id`: Station ID to update
    
    **Business Rules:**
    - Cannot change code to one that already exists
    - Timezone must be valid if provided
    - Reminder config must be logical if provided
    
    **Returns:**
    - 200: Station updated successfully
    - 400: Validation error
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Station not found
    - 409: Station code conflict
    """
    # RBAC: Only admin can update stations
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update stations"
        )
    
    service = StationService(db)
    return service.update_station(station_id, station_data)


@router.patch(
    "/{station_id}/reminder-config",
    response_model=StationResponse,
    summary="Update reminder configuration",
    description="Update only the reminder/escalation configuration for a station"
)
def update_reminder_config(
    station_id: int,
    reminder_config: ReminderConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationResponse:
    """
    Update reminder configuration for a station.
    
    **Required Role:** admin, ops_coordinator
    
    **Path Parameters:**
    - `station_id`: Station ID
    
    **Business Rules:**
    - Second reminder must be after first
    - Escalation must be after second reminder
    - Business hours end must be after start
    
    **Returns:**
    - 200: Reminder config updated successfully
    - 400: Validation error
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Station not found
    """
    # RBAC: Admin or ops_coordinator can update reminder config
    if current_user.role not in ["admin", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update reminder configuration"
        )
    
    service = StationService(db)
    return service.update_reminder_config(
        station_id, 
        reminder_config.model_dump()
    )


@router.patch(
    "/{station_id}/activate",
    response_model=StationResponse,
    summary="Activate station",
    description="Reactivate a deactivated station"
)
def activate_station(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StationResponse:
    """
    Activate a deactivated station.
    
    **Required Role:** admin
    
    **Path Parameters:**
    - `station_id`: Station ID to activate
    
    **Returns:**
    - 200: Station activated successfully
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Station not found
    """
    # RBAC: Only admin can activate stations
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can activate stations"
        )
    
    service = StationService(db)
    return service.activate_station(station_id)


# ========================================
# DELETE
# ========================================

@router.delete(
    "/{station_id}",
    response_model=Dict[str, str],
    summary="Deactivate station",
    description="Soft delete a station (set is_active=False)"
)
def delete_station(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Deactivate a station (soft delete).
    
    **Required Role:** admin
    
    **Path Parameters:**
    - `station_id`: Station ID to deactivate
    
    **Note:** Soft delete is preferred to preserve historical data.
    Use `/stations/{station_id}/hard-delete` for permanent deletion.
    
    **Returns:**
    - 200: Station deactivated successfully
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Station not found
    """
    # RBAC: Only admin can delete stations
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete stations"
        )
    
    service = StationService(db)
    return service.delete_station(station_id)


@router.delete(
    "/{station_id}/hard-delete",
    response_model=Dict[str, str],
    summary="Permanently delete station",
    description="Hard delete a station (permanent, cannot be undone)"
)
def hard_delete_station(
    station_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Permanently delete a station (hard delete).
    
    **Required Role:** admin
    
    **Path Parameters:**
    - `station_id`: Station ID to delete
    
    **Warning:** This action is permanent and cannot be undone.
    Will fail if station has associated hotels or layovers.
    
    **Returns:**
    - 200: Station deleted successfully
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Station not found
    - 409: Station has dependencies (hotels or layovers)
    """
    # RBAC: Only admin can hard delete stations
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can permanently delete stations"
        )
    
    service = StationService(db)
    return service.hard_delete_station(station_id)