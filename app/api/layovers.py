"""
Layover API Router - REST endpoints for layover management
Includes all CRUD operations and workflow actions
"""

from typing import List, Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.layover_service import LayoverService
from app.services.crew_service import CrewService
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
from app.schemas.crew import (
    LayoverCrewCreate,
    LayoverCrewBulkCreate,
    LayoverCrewUpdate,
    LayoverCrewResponse,
    LayoverCrewListResponse,
    NoteCreate,
    NoteResponse,
    NoteListResponse,
    FileAttachmentResponse,
    FileAttachmentListResponse,
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


def get_crew_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CrewService:
    """Dependency to get crew service with current user"""
    return CrewService(db=db, current_user=current_user)


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

# ==================== CREW ASSIGNMENT ENDPOINTS ====================

@router.post(
    "/{layover_id}/crew",
    response_model=LayoverCrewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign crew member to layover",
    description="Assign a single crew member to a layover with optional room details"
)
def assign_crew_to_layover(
    layover_id: int,
    data: LayoverCrewCreate,
    crew_service: CrewService = Depends(get_crew_service)
):
    """
    Assign crew member to layover
    
    - **Validates crew count limit**
    - **Calculates room allocation priority by rank**
    - **Prevents duplicate assignments**
    - **Logs audit trail**
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return crew_service.assign_crew_to_layover(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{layover_id}/crew/bulk",
    response_model=LayoverCrewListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk assign crew members to layover",
    description="Assign multiple crew members at once with auto-primary contact designation"
)
def bulk_assign_crew_to_layover(
    layover_id: int,
    data: LayoverCrewBulkCreate,
    crew_service: CrewService = Depends(get_crew_service)
):
    """
    Bulk assign crew members to layover
    
    - **Assign multiple crew at once**
    - **Auto-designate primary contact (Captain/Purser)**
    - **Validates crew count limit**
    - **Skips already assigned members**
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return crew_service.bulk_assign_crew(layover_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BusinessRuleException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{layover_id}/crew",
    response_model=LayoverCrewListResponse,
    summary="List crew assigned to layover",
    description="Get all crew members assigned to a specific layover"
)
def list_layover_crew(
    layover_id: int,
    crew_service: CrewService = Depends(get_crew_service)
):
    """
    List crew assigned to layover
    
    - **Returns all assigned crew**
    - **Includes crew member details**
    - **Shows room assignments**
    - **Displays notification status**
    """
    try:
        return crew_service.get_layover_crew(layover_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/{layover_id}/crew/{assignment_id}",
    response_model=LayoverCrewResponse,
    summary="Update crew assignment",
    description="Update crew assignment details (room number, type, primary contact)"
)
def update_crew_assignment(
    layover_id: int,
    assignment_id: int,
    data: LayoverCrewUpdate,
    crew_service: CrewService = Depends(get_crew_service)
):
    """
    Update crew assignment
    
    - **Update room number/type**
    - **Change primary contact**
    - **Logs audit trail**
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return crew_service.update_crew_assignment(assignment_id, data)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete(
    "/{layover_id}/crew/{crew_member_id}",
    summary="Remove crew from layover",
    description="Remove a crew member assignment from a layover"
)
def remove_crew_from_layover(
    layover_id: int,
    crew_member_id: int,
    crew_service: CrewService = Depends(get_crew_service)
):
    """
    Remove crew from layover
    
    - **Removes crew assignment**
    - **Logs audit trail**
    
    Required permissions: admin, ops_coordinator
    """
    try:
        return crew_service.remove_crew_from_layover(layover_id, crew_member_id)
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedException as e:
        raise HTTPException(status_code=403, detail=str(e))


# ==================== NOTES ENDPOINTS ====================

@router.post(
    "/{layover_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add note to layover",
    description="Add an internal note to a layover with optional user tagging"
)
def add_note_to_layover(
    layover_id: int,
    data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add note to layover
    
    - **Internal communication**
    - **Support @mentions (tagged_user_ids)**
    - **Immutable once created**
    - **Logs audit trail**
    
    Required permissions: Any authenticated user
    """
    from app.models.layover_note import LayoverNote
    from app.repositories.layover_note_repository import LayoverNoteRepository
    from app.repositories.layover_repository import LayoverRepository
    
    try:
        # Validate layover exists
        layover_repo = LayoverRepository(db)
        layover = layover_repo.get_by_id(layover_id)
        if not layover:
            raise HTTPException(status_code=404, detail=f"Layover {layover_id} not found")
        
        # Create note
        note = LayoverNote(
            layover_id=layover_id,
            note_text=data.note_text,
            tagged_user_ids=data.tagged_user_ids,
            is_internal=data.is_internal,
            created_by=current_user.id
        )
        
        note_repo = LayoverNoteRepository(db)
        note = note_repo.create(note)
        
        return NoteResponse.model_validate(note)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{layover_id}/notes",
    response_model=NoteListResponse,
    summary="List notes for layover",
    description="Get all notes for a specific layover"
)
def list_layover_notes(
    layover_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    internal_only: Optional[bool] = Query(None, description="Filter by internal flag"),
    db: Session = Depends(get_db)
):
    """
    List notes for layover
    
    - **Returns notes in reverse chronological order**
    - **Optional filtering by internal/external**
    - **Paginated results**
    """
    from app.repositories.layover_note_repository import LayoverNoteRepository
    
    try:
        note_repo = LayoverNoteRepository(db)
        notes = note_repo.get_by_layover_id(
            layover_id,
            skip=skip,
            limit=limit,
            internal_only=internal_only
        )
        
        total = note_repo.count_by_layover(layover_id)
        
        items = [NoteResponse.model_validate(n) for n in notes]
        
        return NoteListResponse(items=items, total=total)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FILE ATTACHMENT ENDPOINTS ====================

@router.post(
    "/{layover_id}/files",
    response_model=FileAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file to layover",
    description="Upload a file attachment (rooming list, hotel quote, etc.)"
)
async def upload_file_to_layover(
    layover_id: int,
    file: UploadFile = File(..., description="File to upload (max 5MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload file to layover
    
    - **Supported types**: PDF, Excel, Word, Images
    - **Max size**: 5MB
    - **Virus scan**: Marked as PENDING initially
    - **Logs audit trail**
    
    Required permissions: admin, ops_coordinator, station_user
    """
    from app.models.file_attachment import FileAttachment, ScanStatus
    from app.repositories.file_attachment_repository import FileAttachmentRepository
    from app.repositories.layover_repository import LayoverRepository
    import os
    import uuid
    from pathlib import Path
    
    try:
        # Validate layover exists
        layover_repo = LayoverRepository(db)
        layover = layover_repo.get_by_id(layover_id)
        if not layover:
            raise HTTPException(status_code=404, detail=f"Layover {layover_id} not found")
        
        # Validate file size (5MB max)
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size is 5MB, got {file_size / (1024*1024):.2f}MB"
            )
        
        # Validate file type
        allowed_types = [
            "application/pdf",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "image/jpeg",
            "image/png",
            "image/gif",
            "text/plain",
            "text/csv"
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=415,
                detail=f"File type '{file.content_type}' not allowed. Supported: PDF, Excel, Word, Images, CSV"
            )
        
        # Create uploads directory if not exists
        upload_dir = Path("uploads/layovers")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{layover_id}_{uuid.uuid4()}{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Create database record
        attachment = FileAttachment(
            layover_id=layover_id,
            file_name=file.filename,
            file_size=file_size,
            file_type=file.content_type,
            storage_key=str(file_path),
            scan_status=ScanStatus.PENDING,
            uploaded_by=current_user.id
        )
        
        file_repo = FileAttachmentRepository(db)
        attachment = file_repo.create(attachment)
        
        return FileAttachmentResponse.model_validate(attachment)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get(
    "/{layover_id}/files",
    response_model=FileAttachmentListResponse,
    summary="List files for layover",
    description="Get all file attachments for a specific layover"
)
def list_layover_files(
    layover_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    db: Session = Depends(get_db)
):
    """
    List files for layover
    
    - **Returns all non-deleted files**
    - **Ordered by upload date (newest first)**
    - **Includes scan status**
    """
    from app.repositories.file_attachment_repository import FileAttachmentRepository
    
    try:
        file_repo = FileAttachmentRepository(db)
        files = file_repo.get_by_layover_id(
            layover_id,
            skip=skip,
            limit=limit,
            include_deleted=False
        )
        
        total = file_repo.count_by_layover(layover_id, include_deleted=False)
        
        items = [FileAttachmentResponse.model_validate(f) for f in files]
        
        return FileAttachmentListResponse(items=items, total=total)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{layover_id}/files/{file_id}",
    summary="Download file",
    description="Download a file attachment"
)
def download_layover_file(
    layover_id: int,
    file_id: int,
    db: Session = Depends(get_db)
):
    """
    Download file attachment
    
    - **Returns file for download**
    - **Validates file belongs to layover**
    - **Checks scan status (warns if infected)**
    """
    from app.repositories.file_attachment_repository import FileAttachmentRepository
    from app.models.file_attachment import ScanStatus
    from fastapi.responses import FileResponse
    import os
    
    try:
        file_repo = FileAttachmentRepository(db)
        attachment = file_repo.get_by_id(file_id, include_deleted=False)
        
        if not attachment:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        
        if attachment.layover_id != layover_id:
            raise HTTPException(
                status_code=403,
                detail=f"File {file_id} does not belong to layover {layover_id}"
            )
        
        # Warn if file is infected
        if attachment.scan_status == ScanStatus.INFECTED:
            raise HTTPException(
                status_code=403,
                detail="File is infected and cannot be downloaded"
            )
        
        # Check if file exists
        if not os.path.exists(attachment.storage_key):
            raise HTTPException(
                status_code=404,
                detail="File not found on server (may have been deleted)"
            )
        
        return FileResponse(
            path=attachment.storage_key,
            filename=attachment.file_name,
            media_type=attachment.file_type
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{layover_id}/files/{file_id}",
    summary="Delete file",
    description="Soft delete a file attachment"
)
def delete_layover_file(
    layover_id: int,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete file attachment (soft delete)
    
    - **Soft delete (preserves audit trail)**
    - **Validates file belongs to layover**
    - **Logs audit trail**
    
    Required permissions: admin, ops_coordinator, uploader
    """
    from app.repositories.file_attachment_repository import FileAttachmentRepository
    
    try:
        file_repo = FileAttachmentRepository(db)
        attachment = file_repo.get_by_id(file_id, include_deleted=False)
        
        if not attachment:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        
        if attachment.layover_id != layover_id:
            raise HTTPException(
                status_code=403,
                detail=f"File {file_id} does not belong to layover {layover_id}"
            )
        
        # Permission check: admin, ops_coordinator, or original uploader
        if current_user.role not in ["admin", "ops_coordinator"]:
            if attachment.uploaded_by != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete files you uploaded"
                )
        
        file_repo.soft_delete(file_id, deleted_by=current_user.id)
        
        return {"message": "File deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MANUAL REMINDER TRIGGER ====================

@router.post(
    "/{layover_id}/send-reminder",
    summary="Manually send reminder to hotel",
    description="Manually trigger a reminder email to the hotel (outside automatic schedule)"
)
def send_manual_reminder(
    layover_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually send reminder to hotel
    
    - **Bypasses automatic schedule**
    - **Increments reminder count**
    - **Updates last_reminder_sent_at**
    - **Respects reminders_paused flag**
    
    Use cases:
    - Hotel requested reminder
    - Urgent layover needs immediate follow-up
    - Testing/debugging
    
    Required permissions: admin, ops_coordinator, supervisor
    """
    from app.services.scheduler_service import get_scheduler_service
    
    try:
        # Permission check
        if current_user.role not in ["admin", "ops_coordinator", "supervisor"]:
            raise HTTPException(
                status_code=403,
                detail="Only admin, ops coordinator, or supervisor can send manual reminders"
            )
        
        # Trigger manual reminder
        scheduler = get_scheduler_service()
        result = scheduler.trigger_reminder_manually(layover_id, db)
        
        if result["success"]:
            return {
                "success": True,
                "message": result.get("message", "Reminder sent successfully")
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to send reminder")
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SCHEDULER STATUS ENDPOINT ====================

@router.get(
    "/scheduler/status",
    summary="Get scheduler status",
    description="Get background scheduler status and job information (admin only)"
)
def get_scheduler_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get scheduler status
    
    Returns information about:
    - Scheduler running status
    - Registered jobs
    - Next run times
    - Job configurations
    
    Required permissions: admin, supervisor
    """
    from app.services.scheduler_service import get_scheduler_service
    
    try:
        # Permission check
        if current_user.role not in ["admin", "supervisor"]:
            raise HTTPException(
                status_code=403,
                detail="Only admin or supervisor can view scheduler status"
            )
        
        scheduler = get_scheduler_service()
        status_info = scheduler.get_scheduler_status()
        
        return status_info
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
