"""
Hotel API Router
Handles all hotel-related HTTP endpoints with RBAC.
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.hotel_service import HotelService
from app.schemas.hotel import (
    HotelCreate, HotelUpdate, HotelResponse, 
    HotelWithStationResponse, HotelListResponse
)
from app.models.user import User


router = APIRouter(
    prefix="/hotels",
    tags=["Hotels"]
)


# ========================================
# CREATE
# ========================================

@router.post(
    "",
    response_model=HotelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hotel",
    description="Create a new hotel partner at a station"
)
def create_hotel(
    hotel_data: HotelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HotelResponse:
    """
    Create a new hotel.
    
    **Required Role:** admin, ops_coordinator
    
    **Business Rules:**
    - Station must exist
    - Email must be unique
    - Contract rate requires non-ad_hoc contract type
    - WhatsApp number must be valid international format if provided
    
    **Returns:**
    - 201: Hotel created successfully
    - 400: Validation error
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Station not found
    - 409: Email already exists
    """
    # RBAC: Admin or ops_coordinator can create hotels
    if current_user.role not in ["admin", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create hotels"
        )
    
    service = HotelService(db)
    return service.create_hotel(hotel_data, created_by=current_user.id)


# ========================================
# READ
# ========================================

@router.get(
    "",
    response_model=HotelListResponse,
    summary="List all hotels",
    description="Get paginated list of hotels with optional filtering"
)
def list_hotels(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (max 100)"),
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name, city, or email"),
    include_station: bool = Query(False, description="Include station details"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HotelListResponse:
    """
    List all hotels with pagination and filtering.
    
    **Required Role:** Any authenticated user
    
    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 25, max: 100)
    - `station_id`: Filter by station
    - `is_active`: Filter by active status (true/false/null for all)
    - `search`: Search in name, city, or email (case-insensitive)
    - `include_station`: Include station details in response
    
    **Returns:**
    - 200: List of hotels with pagination metadata
    - 400: Invalid pagination parameters
    - 401: Not authenticated
    """
    service = HotelService(db)
    return service.list_hotels(
        page=page,
        page_size=page_size,
        station_id=station_id,
        is_active=is_active,
        search=search,
        include_station=include_station
    )


@router.get(
    "/station/{station_id}",
    response_model=List[HotelResponse],
    summary="Get hotels by station",
    description="Get all hotels for a specific station"
)
def get_hotels_by_station(
    station_id: int,
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[HotelResponse]:
    """
    Get all hotels for a specific station.
    
    **Required Role:** Any authenticated user
    
    **Path Parameters:**
    - `station_id`: Station ID
    
    **Query Parameters:**
    - `is_active`: Filter by active status (default: true)
    
    **Use Case:** Populate hotel dropdown when creating layover request
    
    **Returns:**
    - 200: List of hotels at that station
    - 401: Not authenticated
    - 404: Station not found
    """
    service = HotelService(db)
    return service.get_hotels_by_station(station_id, is_active)


@router.get(
    "/contracts",
    response_model=List[HotelResponse],
    summary="Get hotels with contracts",
    description="Get hotels with active contract rates"
)
def get_hotels_with_contracts(
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[HotelResponse]:
    """
    Get hotels with active contracts.
    
    **Required Role:** admin, ops_coordinator, finance
    
    **Query Parameters:**
    - `station_id`: Optional filter by station
    
    **Use Case:** Finance reporting, contract management
    
    **Returns:**
    - 200: List of hotels with active contracts
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Admin, ops_coordinator, or finance can view contracts
    if current_user.role not in ["admin", "ops_coordinator", "finance"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view contracts"
        )
    
    service = HotelService(db)
    return service.get_hotels_with_contracts(station_id)


@router.get(
    "/contracts/expired",
    response_model=List[HotelResponse],
    summary="Get hotels with expired contracts",
    description="Get hotels with expired contract rates"
)
def get_expired_contracts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[HotelResponse]:
    """
    Get hotels with expired contracts.
    
    **Required Role:** admin, ops_coordinator, finance
    
    **Use Case:** Contract renewal management
    
    **Returns:**
    - 200: List of hotels with expired contracts
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Admin, ops_coordinator, or finance
    if current_user.role not in ["admin", "ops_coordinator", "finance"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view contracts"
        )
    
    service = HotelService(db)
    return service.check_expired_contracts()


@router.get(
    "/contracts/expiring",
    response_model=List[HotelResponse],
    summary="Get hotels with expiring contracts",
    description="Get hotels with contracts expiring soon"
)
def get_expiring_contracts(
    days: int = Query(30, ge=1, le=365, description="Days to look ahead (default 30)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[HotelResponse]:
    """
    Get hotels with contracts expiring soon.
    
    **Required Role:** admin, ops_coordinator, finance
    
    **Query Parameters:**
    - `days`: Number of days to look ahead (default: 30, max: 365)
    
    **Use Case:** Proactive contract renewal
    
    **Returns:**
    - 200: List of hotels with expiring contracts
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Admin, ops_coordinator, or finance
    if current_user.role not in ["admin", "ops_coordinator", "finance"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view contracts"
        )
    
    service = HotelService(db)
    return service.get_expiring_contracts(days)


@router.get(
    "/performance/top",
    response_model=List[HotelResponse],
    summary="Get top performing hotels",
    description="Get hotels with highest confirmation rates"
)
def get_top_performers(
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    limit: int = Query(10, ge=1, le=50, description="Number of hotels to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[HotelResponse]:
    """
    Get top performing hotels by confirmation rate.
    
    **Required Role:** admin, supervisor, ops_coordinator
    
    **Query Parameters:**
    - `station_id`: Optional filter by station
    - `limit`: Number of hotels to return (default: 10, max: 50)
    
    **Use Case:** Performance dashboards, hotel selection
    
    **Returns:**
    - 200: List of top performing hotels
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Admin, supervisor, or ops_coordinator
    if current_user.role not in ["admin", "supervisor", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view performance data"
        )
    
    service = HotelService(db)
    return service.get_top_performers(station_id, limit)


@router.get(
    "/performance/low",
    response_model=List[HotelResponse],
    summary="Get low performing hotels",
    description="Get hotels with confirmation rates below threshold"
)
def get_low_performers(
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    threshold: float = Query(70.0, ge=0.0, le=100.0, description="Confirmation rate threshold (%)"),
    limit: int = Query(10, ge=1, le=50, description="Number of hotels to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[HotelResponse]:
    """
    Get low performing hotels.
    
    **Required Role:** admin, supervisor, ops_coordinator
    
    **Query Parameters:**
    - `station_id`: Optional filter by station
    - `threshold`: Confirmation rate threshold (default: 70%)
    - `limit`: Number of hotels to return (default: 10, max: 50)
    
    **Use Case:** Identify problematic hotels, review partnerships
    
    **Returns:**
    - 200: List of low performing hotels
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Admin, supervisor, or ops_coordinator
    if current_user.role not in ["admin", "supervisor", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view performance data"
        )
    
    service = HotelService(db)
    return service.get_low_performers(station_id, threshold, limit)


@router.get(
    "/statistics",
    response_model=Dict[str, Any],
    summary="Get hotel statistics",
    description="Get overall hotel statistics and metrics"
)
def get_hotel_statistics(
    station_id: Optional[int] = Query(None, description="Filter by station ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get hotel statistics.
    
    **Required Role:** admin, supervisor, ops_coordinator
    
    **Query Parameters:**
    - `station_id`: Optional filter by station
    
    **Returns:**
    - 200: Hotel statistics
    - 401: Not authenticated
    - 403: Insufficient permissions
    """
    # RBAC: Admin, supervisor, or ops_coordinator
    if current_user.role not in ["admin", "supervisor", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view statistics"
        )
    
    service = HotelService(db)
    return service.get_hotel_statistics(station_id)


@router.get(
    "/{hotel_id}",
    response_model=HotelResponse,
    summary="Get hotel by ID",
    description="Get detailed information about a specific hotel"
)
def get_hotel(
    hotel_id: int,
    include_station: bool = Query(False, description="Include station details"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HotelResponse | HotelWithStationResponse:
    """
    Get hotel by ID.
    
    **Required Role:** Any authenticated user
    
    **Path Parameters:**
    - `hotel_id`: Hotel ID
    
    **Query Parameters:**
    - `include_station`: Include station details in response
    
    **Returns:**
    - 200: Hotel details
    - 401: Not authenticated
    - 404: Hotel not found
    """
    service = HotelService(db)
    return service.get_hotel(hotel_id, include_station)


# ========================================
# UPDATE
# ========================================

@router.put(
    "/{hotel_id}",
    response_model=HotelResponse,
    summary="Update hotel",
    description="Update hotel details (all fields optional)"
)
def update_hotel(
    hotel_id: int,
    hotel_data: HotelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HotelResponse:
    """
    Update an existing hotel.
    
    **Required Role:** admin, ops_coordinator
    
    **Path Parameters:**
    - `hotel_id`: Hotel ID to update
    
    **Business Rules:**
    - Cannot change email to one that already exists
    - Contract logic must be valid
    
    **Returns:**
    - 200: Hotel updated successfully
    - 400: Validation error
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Hotel not found
    - 409: Email conflict
    """
    # RBAC: Admin or ops_coordinator can update hotels
    if current_user.role not in ["admin", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update hotels"
        )
    
    service = HotelService(db)
    return service.update_hotel(hotel_id, hotel_data)


@router.patch(
    "/{hotel_id}/activate",
    response_model=HotelResponse,
    summary="Activate hotel",
    description="Reactivate a deactivated hotel"
)
def activate_hotel(
    hotel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> HotelResponse:
    """
    Activate a deactivated hotel.
    
    **Required Role:** admin, ops_coordinator
    
    **Path Parameters:**
    - `hotel_id`: Hotel ID to activate
    
    **Returns:**
    - 200: Hotel activated successfully
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Hotel not found
    """
    # RBAC: Admin or ops_coordinator can activate hotels
    if current_user.role not in ["admin", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to activate hotels"
        )
    
    service = HotelService(db)
    return service.activate_hotel(hotel_id)


# ========================================
# DELETE
# ========================================

@router.delete(
    "/{hotel_id}",
    response_model=Dict[str, str],
    summary="Deactivate hotel",
    description="Soft delete a hotel (set is_active=False)"
)
def delete_hotel(
    hotel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Deactivate a hotel (soft delete).
    
    **Required Role:** admin, ops_coordinator
    
    **Path Parameters:**
    - `hotel_id`: Hotel ID to deactivate
    
    **Note:** Soft delete is preferred to preserve historical data.
    Use `/hotels/{hotel_id}/hard-delete` for permanent deletion.
    
    **Returns:**
    - 200: Hotel deactivated successfully
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Hotel not found
    """
    # RBAC: Admin or ops_coordinator can delete hotels
    if current_user.role not in ["admin", "ops_coordinator"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete hotels"
        )
    
    service = HotelService(db)
    return service.delete_hotel(hotel_id)


@router.delete(
    "/{hotel_id}/hard-delete",
    response_model=Dict[str, str],
    summary="Permanently delete hotel",
    description="Hard delete a hotel (permanent, cannot be undone)"
)
def hard_delete_hotel(
    hotel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Permanently delete a hotel (hard delete).
    
    **Required Role:** admin
    
    **Path Parameters:**
    - `hotel_id`: Hotel ID to delete
    
    **Warning:** This action is permanent and cannot be undone.
    Will fail if hotel has associated layovers.
    
    **Returns:**
    - 200: Hotel deleted successfully
    - 401: Not authenticated
    - 403: Insufficient permissions
    - 404: Hotel not found
    - 409: Hotel has dependencies (layovers)
    """
    # RBAC: Only admin can hard delete hotels
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can permanently delete hotels"
        )
    
    service = HotelService(db)
    return service.hard_delete_hotel(hotel_id)