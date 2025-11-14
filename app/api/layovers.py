"""
Layover API Router - REST endpoints for layover management
Includes all CRUD operations and workflow actions
"""

from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.layover_service import LayoverService
from app.schemas.layover import (
    LayoverCreate,
    LayoverUpdate,
    LayoverAmend,
    LayoverHold,
    LayoverFinalize,
    LayoverCancel,
    LayoverFilterParams,
    LayoverResponse,
    LayoverDetailResponse,
    LayoverListResponse,
    DashboardMetrics,
    StationPerformance,
    HotelPerformance,
    LayoverStatusEnum,
    LayoverReasonEnum
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
    BusinessRuleException
)


router = APIRouter(prefix="/layovers", tags=["Layovers"])


# ==================== HELPER FUNCTIONS ====================

def get_layover_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> LayoverService:
    """Dependency to get layover service with current user"""
    return LayoverService(db=db, current_user=current_user)


def handle_service_exceptions(func):
    """Decorator to handle service exceptions and convert to HTTP exceptions"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NotFoundException as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationException as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e)
            )
        except PermissionDeniedException as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except BusinessRuleException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            # Log unexpected errors
            print(f"Unexpected error in {func.__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )
    
    # Preserve function signature for FastAPI
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# ==================== CREATE ====================

@router.post(
    "",
    response_model=LayoverDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new layover request",
    description="Create a new layover request. Only admins and ops coordinators can create."
)
def create_layover(
    data: LayoverCreate,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Create a new layover request
    
    - **Auto-calculates room breakdown** if not provided
    - **Validates business rules** (dates, crew count, route requirements)
    - **Sets status to DRAFT**
    - **Logs audit trail**
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.create_layover(data)
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
    response_model=LayoverListResponse,
    summary="List layover requests",
    description="List layovers with filtering, search, and pagination. Station users see only their stations."
)
def list_layovers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    station_ids: Optional[List[int]] = Query(None, description="Filter by station IDs"),
    status: Optional[LayoverStatusEnum] = Query(None, description="Filter by single status"),
    statuses: Optional[List[LayoverStatusEnum]] = Query(None, description="Filter by multiple statuses"),
    check_in_date_from: Optional[date] = Query(None, description="Check-in date from"),
    check_in_date_to: Optional[date] = Query(None, description="Check-in date to"),
    hotel_id: Optional[int] = Query(None, description="Filter by hotel"),
    created_by: Optional[int] = Query(None, description="Filter by creator"),
    layover_reason: Optional[LayoverReasonEnum] = Query(None, description="Filter by reason"),
    trip_id: Optional[str] = Query(None, description="Filter by trip ID"),
    search: Optional[str] = Query(None, max_length=100, description="Search query"),
    order_by: str = Query("check_in_date", description="Sort field"),
    order_direction: str = Query("desc", regex="^(asc|desc)$", description="Sort direction"),
    service: LayoverService = Depends(get_layover_service)
):
    """
    List layover requests with comprehensive filtering
    
    **Filters:**
    - Station IDs (station users automatically filtered to their stations)
    - Status (single or multiple)
    - Date range (check-in dates)
    - Hotel, Creator, Reason, Trip ID
    - Search query (route, hotel name, request ID)
    
    **Sorting:**
    - By: check_in_date, created_at, status
    - Direction: asc, desc
    
    **Pagination:**
    - Page and page_size with total count
    """
    try:
        filters = LayoverFilterParams(
            page=page,
            page_size=page_size,
            station_ids=station_ids,
            status=status,
            statuses=statuses,
            check_in_date_from=check_in_date_from,
            check_in_date_to=check_in_date_to,
            hotel_id=hotel_id,
            created_by=created_by,
            layover_reason=layover_reason,
            trip_id=trip_id,
            search=search,
            order_by=order_by,
            order_direction=order_direction
        )
        
        return service.list_layovers(filters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{layover_id}",
    response_model=LayoverDetailResponse,
    summary="Get layover details",
    description="Get complete layover details including audit trail, notes, and files"
)
def get_layover(
    layover_id: int,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Get layover by ID
    
    Returns complete details including:
    - All layover fields
    - Station, hotel, creator info
    - Status timestamps
    - Hotel response metadata
    - Amendment history
    - Reminder status
    
    Permission check: User must have access to this layover's station
    """
    try:
        return service.get_layover_by_id(layover_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))


# ==================== UPDATE ====================

@router.put(
    "/{layover_id}",
    response_model=LayoverDetailResponse,
    summary="Update layover request",
    description="Update layover (draft only). For confirmed layovers, use amend endpoint."
)
def update_layover(
    layover_id: int,
    data: LayoverUpdate,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Update layover request
    
    **Business Rules:**
    - Only DRAFT layovers can be updated
    - Cannot change route or dates after sending
    - For confirmed layovers, use PUT /layovers/{id}/amend
    
    **Updateable fields:**
    - hotel_id
    - special_requirements
    - transport_required, transport_details
    - room_breakdown (if draft)
    - estimated_cost, currency
    
    Required permissions: admin, ops_coordinator, station_user (own station)
    """
    try:
        return service.update_layover(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== DELETE ====================

@router.delete(
    "/{layover_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete layover request",
    description="Delete layover (draft only). Use cancel endpoint for sent requests."
)
def delete_layover(
    layover_id: int,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Delete layover request
    
    **Business Rules:**
    - Can only delete DRAFT layovers
    - Sent/confirmed layovers must be cancelled instead
    
    Required permissions: admin, ops_coordinator
    """
    try:
        service.delete_layover(layover_id)
        return None
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== SEND TO HOTEL ====================

@router.post(
    "/{layover_id}/send",
    response_model=LayoverDetailResponse,
    summary="Send layover request to hotel",
    description="Send request to hotel via email with confirmation link. Status: DRAFT → SENT → PENDING"
)
def send_to_hotel(
    layover_id: int,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Send layover request to hotel
    
    **Actions performed:**
    1. Validate layover is DRAFT status
    2. Validate hotel is assigned
    3. Generate confirmation token (72-hour expiry)
    4. Update status: DRAFT → SENT → PENDING
    5. Send email to hotel with confirmation link
    6. Schedule automated reminders
    7. Log audit trail
    
    **Business Rules:**
    - Only DRAFT layovers can be sent
    - Hotel must be assigned
    - Cannot resend (create new request or use amend)
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.send_to_hotel(layover_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== DUPLICATE ====================

@router.post(
    "/{layover_id}/duplicate",
    response_model=LayoverDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate layover request",
    description="Create a copy of existing layover. Dates and status are cleared."
)
def duplicate_layover(
    layover_id: int,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Duplicate an existing layover
    
    **Copied fields:**
    - Route, station, hotel
    - Crew count, room breakdown
    - Special requirements, transport details
    - Trip info, costs
    
    **Cleared fields:**
    - ID, UUID (new generated)
    - Dates (user must set)
    - Status (reset to DRAFT)
    - All timestamps
    
    **Use cases:**
    - Repeat layovers (same route, different dates)
    - Template-based creation
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.duplicate_layover(layover_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))


# ==================== HOLD & RESUME (IRROPS) ====================

@router.put(
    "/{layover_id}/hold",
    response_model=LayoverDetailResponse,
    summary="Put layover on hold",
    description="Put layover on hold during irregular operations (IRROPS). Pauses reminders."
)
def put_on_hold(
    layover_id: int,
    data: LayoverHold,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Put layover on hold (irregular operations)
    
    **Use cases:**
    - Flight delay (crew might not need hotel)
    - Weather diversion
    - Aircraft technical issue
    - Crew schedule change pending
    
    **Actions performed:**
    1. Update status to ON_HOLD
    2. Pause automated reminders
    3. Log hold reason and timestamp
    4. Optionally notify hotel (if confirmed)
    
    **Business Rules:**
    - Can hold: SENT, PENDING, CONFIRMED layovers
    - Cannot hold: DRAFT, COMPLETED, CANCELLED
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.put_on_hold(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{layover_id}/resume",
    response_model=LayoverDetailResponse,
    summary="Resume layover from hold",
    description="Resume layover after IRROPS resolved. Restores previous status."
)
def resume_from_hold(
    layover_id: int,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Resume layover from hold
    
    **Actions performed:**
    1. Restore previous status (PENDING or CONFIRMED)
    2. Resume automated reminders (if not confirmed)
    3. Log resume action
    
    **Business Rules:**
    - Can only resume ON_HOLD layovers
    - Restores to CONFIRMED if hotel already confirmed
    - Otherwise restores to PENDING
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.resume_from_hold(layover_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== AMEND (POST-CONFIRMATION) ====================

@router.put(
    "/{layover_id}/amend",
    response_model=LayoverDetailResponse,
    summary="Amend confirmed layover",
    description="Make changes to confirmed layover. Increments amendment counter."
)
def amend_layover(
    layover_id: int,
    data: LayoverAmend,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Amend a confirmed layover (post-confirmation changes)
    
    **Use cases:**
    - Crew change (different room breakdown)
    - Additional special requirements
    - Transport arrangements updated
    - Hotel change (rare)
    
    **Actions performed:**
    1. Validate layover is CONFIRMED
    2. Apply changes
    3. Update status to AMENDED
    4. Increment amendment counter
    5. Mark hotel notification pending
    6. Log amendment reason
    
    **Business Rules:**
    - Can only amend CONFIRMED layovers
    - Cannot change dates (requires new request)
    - Hotel must be notified of amendment
    
    **Amendable fields:**
    - room_breakdown
    - special_requirements
    - transport_required, transport_details
    - hotel_id
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.amend_layover(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{layover_id}/notify-amendment",
    response_model=dict,
    summary="Send amendment notification to hotel",
    description="Manually trigger amendment notification email to hotel"
)
def notify_amendment(
    layover_id: int,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Send amendment notification to hotel
    
    **Use cases:**
    - After amending a confirmed layover
    - Hotel needs to be notified of changes
    - Manual trigger after multiple amendments
    
    **Actions performed:**
    1. Validate layover status is AMENDED
    2. Send email with before/after comparison
    3. Set hotel_notified_of_amendment = TRUE
    4. Log notification in audit trail
    
    **Business Rules:**
    - Can only notify AMENDED layovers
    - Cannot notify if already notified (unless flagged for re-notification)
    - Hotel must have email configured
    
    **Email includes:**
    - Amendment reason
    - Updated booking details
    - Confirmation link to acknowledge changes
    - Contact information
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.notify_amendment(layover_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== FINALIZE ====================

@router.post(
    "/{layover_id}/finalize",
    response_model=LayoverDetailResponse,
    summary="Finalize layover booking",
    description="Mark layover as completed and notify crew. Status: CONFIRMED → COMPLETED"
)
def finalize_layover(
    layover_id: int,
    data: LayoverFinalize,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Finalize layover booking and notify crew
    
    **Actions performed:**
    1. Validate layover is CONFIRMED or AMENDED
    2. Update status to COMPLETED
    3. Store hotel confirmation number
    4. Generate crew portal tokens
    5. Send email/SMS notifications to crew
    6. Log finalization
    
    **Business Rules:**
    - Can only finalize CONFIRMED or AMENDED layovers
    - Locks layover (no further edits without admin)
    - Crew receives hotel details + portal link
    
    **Crew notification includes:**
    - Hotel name, address, phone
    - Check-in/check-out times
    - Room assignment
    - Transport details
    - Emergency contact
    - Calendar file (.ics)
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.finalize_layover(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== CANCEL ====================

@router.post(
    "/{layover_id}/cancel",
    response_model=LayoverDetailResponse,
    summary="Cancel layover request",
    description="Cancel layover. Calculates notice hours and determines if cancellation charge applies."
)
def cancel_layover(
    layover_id: int,
    data: LayoverCancel,
    service: LayoverService = Depends(get_layover_service)
):
    """
    Cancel a layover request
    
    **Actions performed:**
    1. Calculate cancellation notice hours
    2. Determine if charge applies (<24h = charge)
    3. Update status to CANCELLED
    4. Pause reminders
    5. Notify hotel (if confirmed)
    6. Log cancellation reason
    
    **Business Rules:**
    - Cannot cancel COMPLETED layovers
    - Cancellation charge applies if <24h notice
    - Hotel must be notified if booking was confirmed
    
    **Cancellation reasons:**
    - flight_cancelled
    - crew_change
    - weather_diversion
    - operational_decision
    - other
    
    **Finance implications:**
    - >24h notice: Usually no charge
    - <24h notice: 1 night charge typical
    - No-show: Full stay charge
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return service.cancel_layover(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== METRICS & ANALYTICS ====================

@router.get(
    "/metrics/dashboard",
    response_model=DashboardMetrics,
    summary="Get dashboard metrics",
    description="Summary metrics for current month: total, confirmed, pending, escalated, etc."
)
def get_dashboard_metrics(
    station_ids: Optional[List[int]] = Query(None, description="Filter by station IDs"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    service: LayoverService = Depends(get_layover_service)
):
    """
    Get dashboard summary metrics
    
    **Metrics included:**
    - Total requests
    - Confirmed count
    - Pending count
    - Escalated count
    - On hold count
    - Declined count
    - Completed count
    - Confirmation rate (%)
    - Average response time (hours)
    
    **Filters:**
    - Station IDs (station users auto-filtered)
    - Date range (default: current month)
    
    Required permissions: All authenticated users
    """
    try:
        return service.get_dashboard_metrics(
            station_ids=station_ids,
            date_from=date_from,
            date_to=date_to
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/metrics/stations",
    response_model=List[StationPerformance],
    summary="Get station performance",
    description="Performance metrics by station: confirmation rate, response time, escalations"
)
def get_station_performance(
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    service: LayoverService = Depends(get_layover_service)
):
    """
    Get station performance report
    
    **Metrics per station:**
    - Total requests
    - Confirmed count
    - Confirmation rate (%)
    - Average response time (hours)
    - Escalated count
    
    **Sorted by:** Confirmation rate (descending)
    
    **Use cases:**
    - Identify high-performing stations
    - Flag stations with low confirmation rates
    - Monitor response times by location
    
    Required permissions: admin, supervisor, ops_coordinator
    """
    try:
        return service.get_station_performance(
            date_from=date_from,
            date_to=date_to
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/metrics/hotels",
    response_model=List[HotelPerformance],
    summary="Get hotel performance",
    description="Performance metrics by hotel: confirmation rate, decline rate, response time, rating"
)
def get_hotel_performance(
    station_id: Optional[int] = Query(None, description="Filter by station"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    min_requests: int = Query(3, ge=1, description="Minimum requests to include"),
    service: LayoverService = Depends(get_layover_service)
):
    """
    Get hotel performance report
    
    **Metrics per hotel:**
    - Total requests
    - Confirmed count
    - Declined count
    - Confirmation rate (%)
    - Decline rate (%)
    - Average response time (hours)
    - Last response date
    - Rating (excellent, good, average, poor)
    
    **Rating criteria:**
    - Excellent: >90% confirm, <12h response
    - Good: >80% confirm, <24h response
    - Average: >70% confirm
    - Poor: <70% confirm
    
    **Sorted by:** Confirmation rate (descending)
    
    **Use cases:**
    - Identify reliable hotel partners
    - Flag problematic hotels
    - Renegotiate contracts based on performance
    
    Required permissions: admin, supervisor, ops_coordinator
    """
    try:
        return service.get_hotel_performance(
            station_id=station_id,
            date_from=date_from,
            date_to=date_to,
            min_requests=min_requests
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))