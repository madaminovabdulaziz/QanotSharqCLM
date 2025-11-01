"""
Confirmation API (PUBLIC)
Hotel confirmation endpoints - NO AUTHENTICATION REQUIRED
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.services.confirmation_service import ConfirmationService
from app.core.exceptions import (
    TokenExpiredException,
    TokenAlreadyUsedException,
    InvalidStatusTransitionException,
)
from app.schemas.confirmation import (
    HotelConfirmRequest,
    HotelDeclineRequest,
    HotelChangeRequest,
    LayoverConfirmationDetails,
    ConfirmationResponse,
    TokenExpiredResponse,
    TokenAlreadyUsedResponse,
)

router = APIRouter(prefix="/confirm", tags=["Hotel Confirmation (Public)"])


def get_client_info(request: Request) -> dict:
    """Extract client IP and user agent from request"""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.get(
    "/{token}",
    response_model=LayoverConfirmationDetails,
    responses={
        410: {"model": TokenExpiredResponse, "description": "Token expired"},
        409: {"model": TokenAlreadyUsedResponse, "description": "Token already used"},
        404: {"description": "Token not found"},
    },
    summary="Load hotel confirmation page",
    description="""
    **PUBLIC ENDPOINT - NO AUTHENTICATION REQUIRED**
    
    Hotel clicks link from email and lands on this page.
    Returns layover details for the hotel to review and respond.
    
    **Token Validation:**
    - Token must not be expired (72 hours)
    - Token must not have been used already
    - Layover must be in a state where hotel can respond
    """,
)
async def get_confirmation_page(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Get layover details for hotel confirmation page
    
    **Flow:**
    1. Hotel receives email with confirmation link
    2. Clicks link → arrives here
    3. System validates token
    4. Returns layover details if valid
    5. Hotel sees confirmation page with 3 buttons: Confirm / Decline / Request Changes
    """
    confirmation_service = ConfirmationService(db)

    try:
        # Validate token and get layover details
        result = confirmation_service.validate_and_get_layover(token)
        layover = result["layover"]
        token_obj = result["token"]

        # Build response
        response = LayoverConfirmationDetails(
            layover_id=layover.id,
            request_number=layover.uuid,
            route=f"{layover.origin_station_code} → {layover.destination_station_code}",
            station_name=layover.station.name,
            hotel_name=layover.hotel.name,
            check_in_date=layover.check_in_date.isoformat(),
            check_in_time=layover.check_in_time.strftime("%H:%M"),
            check_out_date=layover.check_out_date.isoformat(),
            check_out_time=layover.check_out_time.strftime("%H:%M"),
            duration_hours=int(
                (
                    datetime.combine(layover.check_out_date, layover.check_out_time)
                    - datetime.combine(layover.check_in_date, layover.check_in_time)
                ).total_seconds()
                / 3600
            ),
            crew_count=layover.crew_count,
            room_breakdown=layover.room_breakdown,
            special_requirements=layover.special_requirements,
            status=layover.status,
            sent_at=layover.sent_at,
            token_expires_at=token_obj.expires_at,
            can_respond=result["can_respond"],
        )

        return response

    except TokenExpiredException as e:
        # Token expired - return 410 Gone with contact info
        raise HTTPException(
            status_code=410,
            detail={
                "expired": True,
                "message": str(e),
                "contact_email": "ops@airline.com",
                "contact_phone": "+1-800-AIRLINE",
            },
        )

    except TokenAlreadyUsedException as e:
        # Token already used - return 409 Conflict
        raise HTTPException(
            status_code=409,
            detail={
                "already_used": True,
                "message": str(e),
                "contact_email": "ops@airline.com",
                "contact_phone": "+1-800-AIRLINE",
            },
        )

    except ValueError as e:
        # Invalid token or layover not found
        raise HTTPException(status_code=404, detail=str(e))

    except InvalidStatusTransitionException as e:
        # Layover in wrong status
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{token}/confirm",
    response_model=ConfirmationResponse,
    status_code=200,
    summary="Hotel confirms booking",
    description="""
    **PUBLIC ENDPOINT - NO AUTHENTICATION REQUIRED**
    
    Hotel clicks "Confirm Booking" button.
    Updates layover status to CONFIRMED and cancels pending reminders.
    
    **Optional Fields:**
    - confirmation_number: Hotel's booking confirmation number
    - hotel_note: Any additional notes from hotel
    """,
)
async def confirm_booking(
    token: str,
    request_data: HotelConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Process hotel confirmation
    
    **Flow:**
    1. Hotel clicks "Confirm" button
    2. Optional: Enters confirmation number and/or note
    3. System validates token
    4. Updates layover status to CONFIRMED
    5. Captures response metadata (IP, timestamp, user-agent)
    6. Cancels pending reminders
    7. Creates audit log
    8. Returns success response
    9. Frontend shows "Thank You" page
    """
    confirmation_service = ConfirmationService(db)
    client_info = get_client_info(request)

    try:
        result = confirmation_service.confirm_booking(
            token=token,
            confirmation_number=request_data.confirmation_number,
            hotel_note=request_data.hotel_note,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return ConfirmationResponse(
            success=True,
            message=result["message"],
            layover_id=result["layover"].id,
            new_status=result["layover"].status,
            response_timestamp=datetime.utcnow(),
        )

    except (TokenExpiredException, TokenAlreadyUsedException) as e:
        raise HTTPException(status_code=410, detail=str(e))

    except InvalidStatusTransitionException as e:
        raise HTTPException(status_code=400, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{token}/decline",
    response_model=ConfirmationResponse,
    status_code=200,
    summary="Hotel declines booking",
    description="""
    **PUBLIC ENDPOINT - NO AUTHENTICATION REQUIRED**
    
    Hotel clicks "Decline Request" button.
    Updates layover status to DECLINED with reason.
    
    **Required:**
    - decline_reason: One of [fully_booked, insufficient_notice, cannot_meet_requirements, other]
    
    **Optional:**
    - decline_note: Additional explanation
    """,
)
async def decline_booking(
    token: str,
    request_data: HotelDeclineRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Process hotel decline
    
    **Flow:**
    1. Hotel clicks "Decline" button
    2. Selects decline reason from predefined list
    3. Optional: Adds additional note
    4. System validates token
    5. Updates layover status to DECLINED
    6. Captures response metadata
    7. Cancels pending reminders
    8. Creates audit log
    9. Returns success response
    10. Frontend shows "Thank You" page with decline confirmation
    """
    confirmation_service = ConfirmationService(db)
    client_info = get_client_info(request)

    try:
        result = confirmation_service.decline_booking(
            token=token,
            decline_reason=request_data.decline_reason,
            decline_note=request_data.decline_note,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return ConfirmationResponse(
            success=True,
            message=result["message"],
            layover_id=result["layover"].id,
            new_status=result["layover"].status,
            response_timestamp=datetime.utcnow(),
        )

    except (TokenExpiredException, TokenAlreadyUsedException) as e:
        raise HTTPException(status_code=410, detail=str(e))

    except InvalidStatusTransitionException as e:
        raise HTTPException(status_code=400, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{token}/request-changes",
    response_model=ConfirmationResponse,
    status_code=200,
    summary="Hotel requests changes",
    description="""
    **PUBLIC ENDPOINT - NO AUTHENTICATION REQUIRED**
    
    Hotel clicks "Request Changes" button.
    Updates layover status to CHANGES_REQUESTED.
    
    **Required:**
    - change_types: List of change types (e.g., ['check_in_time', 'room_configuration'])
    - change_note: Explanation of what changes are needed (min 10 chars)
    """,
)
async def request_changes(
    token: str,
    request_data: HotelChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Process hotel change request
    
    **Flow:**
    1. Hotel clicks "Request Changes" button
    2. Selects change types (checkboxes)
    3. Enters required note explaining changes
    4. System validates token
    5. Updates layover status to CHANGES_REQUESTED
    6. Captures response metadata
    7. Pauses reminders (Ops needs to review)
    8. Creates audit log
    9. Returns success response
    10. Frontend shows "Thank You" page informing hotel that Ops will contact them
    """
    confirmation_service = ConfirmationService(db)
    client_info = get_client_info(request)

    try:
        result = confirmation_service.request_changes(
            token=token,
            change_types=request_data.change_types,
            change_note=request_data.change_note,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        return ConfirmationResponse(
            success=True,
            message=result["message"],
            layover_id=result["layover"].id,
            new_status=result["layover"].status,
            response_timestamp=datetime.utcnow(),
        )

    except (TokenExpiredException, TokenAlreadyUsedException) as e:
        raise HTTPException(status_code=410, detail=str(e))

    except InvalidStatusTransitionException as e:
        raise HTTPException(status_code=400, detail=str(e))

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))