"""
Confirmation Schemas
Pydantic models for hotel confirmation API requests/responses
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class HotelConfirmRequest(BaseModel):
    """Request schema for hotel confirming a booking"""
    
    confirmation_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Hotel's confirmation number (optional)",
    )
    hotel_note: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional note from hotel",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "confirmation_number": "HTL-12345",
                "hotel_note": "Late check-in arranged. Vegetarian meals confirmed.",
            }
        }


class HotelDeclineRequest(BaseModel):
    """Request schema for hotel declining a booking"""
    
    decline_reason: str = Field(
        ...,
        description="Reason for declining",
    )
    decline_note: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional details about the decline",
    )

    @validator("decline_reason")
    def validate_decline_reason(cls, v):
        """Validate decline reason is one of the predefined options"""
        valid_reasons = [
            "fully_booked",
            "insufficient_notice",
            "cannot_meet_requirements",
            "other",
        ]
        if v not in valid_reasons:
            raise ValueError(f"decline_reason must be one of: {', '.join(valid_reasons)}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "decline_reason": "fully_booked",
                "decline_note": "Unfortunately we are fully booked for Feb 1-2. We have availability from Feb 3 onwards.",
            }
        }


class HotelChangeRequest(BaseModel):
    """Request schema for hotel requesting changes"""
    
    change_types: List[str] = Field(
        ...,
        description="Types of changes needed",
    )
    change_note: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Required explanation of what changes are needed",
    )

    @validator("change_types")
    def validate_change_types(cls, v):
        """Validate change types"""
        valid_types = [
            "check_in_time",
            "check_out_time",
            "room_configuration",
            "additional_costs",
            "special_requirements",
            "other",
        ]
        for change_type in v:
            if change_type not in valid_types:
                raise ValueError(f"Invalid change_type: {change_type}")
        
        if not v:
            raise ValueError("At least one change type must be selected")
        
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "change_types": ["check_in_time", "room_configuration"],
                "change_note": "We can accommodate 5 rooms, but check-in must be after 16:00 due to housekeeping schedule. We can provide 3 singles and 1 double instead of 5 singles. Please confirm if this works.",
            }
        }


class LayoverConfirmationDetails(BaseModel):
    """Response schema with layover details for confirmation page"""
    
    layover_id: int
    request_number: str = Field(..., description="Public-facing request number (UUID)")
    route: str
    station_name: str
    hotel_name: str
    
    check_in_date: str
    check_in_time: str
    check_out_date: str
    check_out_time: str
    duration_hours: int
    
    crew_count: int
    room_breakdown: dict
    special_requirements: Optional[str]
    
    status: str
    sent_at: Optional[datetime]
    
    token_expires_at: datetime
    can_respond: bool

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "layover_id": 126,
                "request_number": "abc123-uuid",
                "route": "JFK → LHR",
                "station_name": "London Heathrow",
                "hotel_name": "Heathrow Hilton",
                "check_in_date": "2025-02-01",
                "check_in_time": "14:00",
                "check_out_date": "2025-02-02",
                "check_out_time": "10:00",
                "duration_hours": 20,
                "crew_count": 5,
                "room_breakdown": {"singles": 5, "doubles": 0, "suites": 0},
                "special_requirements": "Late check-in required. 2 vegetarian meals.",
                "status": "PENDING",
                "sent_at": "2025-01-25T09:15:00Z",
                "token_expires_at": "2025-01-28T09:15:00Z",
                "can_respond": True,
            }
        }


class ConfirmationResponse(BaseModel):
    """Generic response after hotel takes action"""
    
    success: bool
    message: str
    layover_id: int
    new_status: str
    response_timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Booking confirmed successfully",
                "layover_id": 126,
                "new_status": "CONFIRMED",
                "response_timestamp": "2025-01-25T11:23:00Z",
            }
        }


class TokenExpiredResponse(BaseModel):
    """Response when token has expired"""
    
    expired: bool = True
    message: str = "This confirmation link has expired"
    request_id: Optional[str] = None
    hotel_name: Optional[str] = None
    contact_email: str = "ops@airline.com"
    contact_phone: str = "+1-800-AIRLINE"

    class Config:
        json_schema_extra = {
            "example": {
                "expired": True,
                "message": "This confirmation link has expired",
                "request_id": "#126",
                "hotel_name": "Heathrow Hilton",
                "contact_email": "ops@airline.com",
                "contact_phone": "+1-800-AIRLINE",
            }
        }


class TokenAlreadyUsedResponse(BaseModel):
    """Response when token has already been used"""
    
    already_used: bool = True
    message: str = "This confirmation link has already been used"
    action_taken: str
    responded_at: datetime
    contact_email: str = "ops@airline.com"
    contact_phone: str = "+1-800-AIRLINE"

    class Config:
        json_schema_extra = {
            "example": {
                "already_used": True,
                "message": "This confirmation link has already been used",
                "action_taken": "confirmed",
                "responded_at": "2025-01-25T11:23:00Z",
                "contact_email": "ops@airline.com",
                "contact_phone": "+1-800-AIRLINE",
            }
        }