"""
Layover Schemas - Pydantic models for request/response validation
Includes validation rules aligned with aviation operational requirements
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field, validator, model_validator
from enum import Enum


# ==================== ENUMS ====================

class LayoverStatusEnum(str, Enum):
    """Layover status enum (matches database)"""
    DRAFT = "DRAFT"
    SENT = "SENT"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ON_HOLD = "ON_HOLD"
    AMENDED = "AMENDED"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LayoverReasonEnum(str, Enum):
    """Layover reason enum (from SME review)"""
    SCHEDULED_REST = "scheduled_rest"
    POSITIONING = "positioning"
    TRAINING = "training"
    STANDBY = "standby"
    IRREGULAR_OPS = "irregular_ops"
    OTHER = "other"


class CancellationReasonEnum(str, Enum):
    """Cancellation reason enum"""
    FLIGHT_CANCELLED = "flight_cancelled"
    CREW_CHANGE = "crew_change"
    WEATHER_DIVERSION = "weather_diversion"
    OPERATIONAL_DECISION = "operational_decision"
    OTHER = "other"


# ==================== BASE SCHEMAS ====================

class RoomBreakdown(BaseModel):
    """Room breakdown structure"""
    singles: int = Field(ge=0, description="Number of single rooms")
    doubles: int = Field(ge=0, description="Number of double rooms")
    suites: int = Field(ge=0, description="Number of suites")
    
    @validator('singles', 'doubles', 'suites')
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError("Room count cannot be negative")
        return v
    
    @model_validator(mode='after')
    def validate_at_least_one_room(cls, values):
        total = values.get('singles', 0) + values.get('doubles', 0) + values.get('suites', 0)
        if total == 0:
            raise ValueError("At least one room must be requested")
        return values


class StationBase(BaseModel):
    """Minimal station info (for nested responses)"""
    id: int
    code: str
    name: str
    city: str
    country: str
    
    class Config:
        from_attributes = True


class HotelBase(BaseModel):
    """Minimal hotel info (for nested responses)"""
    id: int
    name: str
    address: str
    phone: Optional[str]
    email: str
    
    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Minimal user info (for nested responses)"""
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    
    class Config:
        from_attributes = True


# ==================== CREATE SCHEMA ====================

class LayoverCreate(BaseModel):
    """Schema for creating a new layover request"""
    
    # Route & Station
    origin_station_code: Optional[str] = Field(
        None, 
        max_length=10,
        description="Origin airport code (nullable for positioning/training)"
    )
    destination_station_code: Optional[str] = Field(
        None,
        max_length=10,
        description="Destination airport code (nullable for positioning/training)"
    )
    station_id: int = Field(..., description="Station handling this layover")
    hotel_id: Optional[int] = Field(None, description="Preferred hotel (can be selected later)")
    
    # Layover Reason (from SME review)
    layover_reason: LayoverReasonEnum = Field(
        LayoverReasonEnum.SCHEDULED_REST,
        description="Reason for layover"
    )
    operational_flight_number: Optional[str] = Field(
        None,
        max_length=20,
        description="Flight number if operational (e.g., AA100)"
    )
    
    # Dates & Times
    check_in_date: date = Field(..., description="Check-in date")
    check_in_time: time = Field(..., description="Check-in time")
    check_out_date: date = Field(..., description="Check-out date")
    check_out_time: time = Field(..., description="Check-out time")
    
    # Crew & Rooms
    crew_count: int = Field(..., ge=1, le=100, description="Number of crew members")
    room_breakdown: RoomBreakdown = Field(..., description="Room allocation")
    
    # Special Requirements
    special_requirements: Optional[str] = Field(
        None,
        max_length=1000,
        description="Special requirements (dietary, late check-in, etc.)"
    )
    transport_required: bool = Field(False, description="Transport required flag")
    transport_details: Optional[str] = Field(
        None,
        max_length=500,
        description="Transport details if required"
    )
    
    # Multi-leg Trip Grouping (from SME review)
    trip_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Trip ID for multi-leg layovers (e.g., AA-JAN25-P001)"
    )
    trip_sequence: Optional[int] = Field(
        None,
        ge=1,
        description="Sequence in trip (1, 2, 3...)"
    )
    is_positioning: bool = Field(
        False,
        description="True if crew is deadheading"
    )
    
    # Cost Tracking (optional for MVP)
    estimated_cost: Optional[Decimal] = Field(
        None,
        ge=0,
        max_digits=10,
        decimal_places=2,
        description="Estimated cost"
    )
    currency: str = Field("USD", max_length=3, description="Currency code")
    
    @model_validator(mode='after')
    def validate_route_for_scheduled_rest(cls, values):
        """Route required for scheduled rest, optional for other reasons"""
        reason = values.get('layover_reason')
        origin = values.get('origin_station_code')
        destination = values.get('destination_station_code')
        
        if reason == LayoverReasonEnum.SCHEDULED_REST:
            if not origin or not destination:
                raise ValueError(
                    "Origin and destination required for scheduled rest layovers"
                )
        
        return values
    
    @model_validator(mode='after')
    def validate_checkout_after_checkin(cls, values):
        """Check-out must be after check-in"""
        check_in_date = values.get('check_in_date')
        check_in_time = values.get('check_in_time')
        check_out_date = values.get('check_out_date')
        check_out_time = values.get('check_out_time')
        
        if all([check_in_date, check_in_time, check_out_date, check_out_time]):
            check_in_dt = datetime.combine(check_in_date, check_in_time)
            check_out_dt = datetime.combine(check_out_date, check_out_time)
            
            if check_out_dt <= check_in_dt:
                raise ValueError("Check-out must be after check-in")
        
        return values
    
    @model_validator(mode='after')
    def validate_transport_details(cls, values):
        """Transport details required if transport_required is True"""
        transport_required = values.get('transport_required')
        transport_details = values.get('transport_details')
        
        if transport_required and not transport_details:
            raise ValueError("Transport details required when transport is needed")
        
        return values
    
    @model_validator(mode='after')
    def validate_trip_sequence(cls, values):
        """Trip sequence required if trip_id provided"""
        trip_id = values.get('trip_id')
        trip_sequence = values.get('trip_sequence')
        
        if trip_id and not trip_sequence:
            raise ValueError("Trip sequence required when trip_id is provided")
        
        return values


# ==================== UPDATE SCHEMAS ====================

class LayoverUpdate(BaseModel):
    """Schema for updating a layover (draft only or specific fields)"""
    
    # Only allow updating these fields after creation
    hotel_id: Optional[int] = None
    special_requirements: Optional[str] = Field(None, max_length=1000)
    transport_required: Optional[bool] = None
    transport_details: Optional[str] = Field(None, max_length=500)
    estimated_cost: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    
    # Can update room breakdown if still draft
    room_breakdown: Optional[RoomBreakdown] = None
    
    # Cannot update: route, dates, crew_count (requires amend flow)
    
    @validator('transport_details')
    def validate_transport_details_not_empty(cls, v, values):
        if values.get('transport_required') and not v:
            raise ValueError("Transport details required when transport is needed")
        return v


class LayoverAmend(BaseModel):
    """Schema for amending a confirmed layover (post-confirmation changes)"""
    
    amendment_reason: str = Field(..., max_length=500, description="Reason for amendment")
    
    # Fields that can be amended
    room_breakdown: Optional[RoomBreakdown] = None
    special_requirements: Optional[str] = Field(None, max_length=1000)
    transport_required: Optional[bool] = None
    transport_details: Optional[str] = Field(None, max_length=500)
    hotel_id: Optional[int] = None  # Can change hotel if needed
    
    # Note: Date/time changes require hotel re-confirmation


class LayoverHold(BaseModel):
    """Schema for putting layover on hold (IRROPS)"""
    
    on_hold_reason: str = Field(
        ...,
        max_length=255,
        description="Reason for hold (e.g., 'Flight delayed 4 hours', 'Weather diversion')"
    )


class LayoverFinalize(BaseModel):
    """Schema for finalizing a booking (mark as completed)"""
    
    hotel_confirmation_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Hotel confirmation number"
    )
    final_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Final notes before completion"
    )
    send_sms_notification: bool = Field(
        False,
        description="Send SMS in addition to email"
    )


class LayoverCancel(BaseModel):
    """Schema for cancelling a layover"""
    
    cancellation_reason: CancellationReasonEnum = Field(
        ...,
        description="Reason for cancellation"
    )
    cancellation_note: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional cancellation details"
    )


# ==================== RESPONSE SCHEMAS ====================

class LayoverResponse(BaseModel):
    """Basic layover response (for list views)"""
    
    id: int
    uuid: str
    
    # Route
    origin_station_code: Optional[str]
    destination_station_code: Optional[str]
    station_id: int
    hotel_id: Optional[int]
    
    # Reason
    layover_reason: str
    operational_flight_number: Optional[str]
    
    # Dates
    check_in_date: date
    check_in_time: time
    check_out_date: date
    check_out_time: time
    
    # Crew
    crew_count: int
    room_breakdown: Dict[str, int]
    
    # Status
    status: str
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    
    # Nested relations (optional)
    station: Optional[StationBase] = None
    hotel: Optional[HotelBase] = None
    creator: Optional[UserBase] = None
    
    class Config:
        from_attributes = True


class LayoverDetailResponse(LayoverResponse):
    """Detailed layover response (for detail view)"""
    
    # All fields from LayoverResponse plus:
    
    # Special requirements
    special_requirements: Optional[str]
    transport_required: bool
    transport_details: Optional[str]
    
    # Status timestamps
    pending_at: Optional[datetime]
    declined_at: Optional[datetime]
    escalated_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    # Hotel response
    hotel_response_note: Optional[str]
    hotel_response_metadata: Optional[Dict[str, Any]]
    
    # Reminders
    last_reminder_sent_at: Optional[datetime]
    reminder_count: int
    reminders_paused: bool
    reminders_paused_reason: Optional[str]
    
    # On Hold
    on_hold_at: Optional[datetime]
    on_hold_reason: Optional[str]
    
    # Amendments
    amendment_count: int
    last_amended_at: Optional[datetime]
    hotel_notified_of_amendment: bool
    
    # Confirmation
    hotel_confirmation_number: Optional[str]
    
    # Cancellation
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    cancellation_notice_hours: Optional[int]
    
    # Trip grouping
    trip_id: Optional[str]
    trip_sequence: Optional[int]
    is_positioning: bool
    
    # Cost
    estimated_cost: Optional[Decimal]
    actual_cost: Optional[Decimal]
    currency: str
    
    # Audit
    created_by: int
    
    class Config:
        from_attributes = True


class LayoverListResponse(BaseModel):
    """Paginated list of layovers"""
    
    items: List[LayoverResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @validator('total_pages', always=True)
    def calculate_total_pages(cls, v, values):
        total = values.get('total', 0)
        page_size = values.get('page_size', 25)
        return (total + page_size - 1) // page_size if page_size > 0 else 0


# ==================== FILTER SCHEMAS ====================

class LayoverFilterParams(BaseModel):
    """Query parameters for filtering layovers"""
    
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(25, ge=1, le=100, description="Items per page")
    
    # Filters
    station_ids: Optional[List[int]] = Field(None, description="Filter by station IDs")
    status: Optional[LayoverStatusEnum] = Field(None, description="Filter by single status")
    statuses: Optional[List[LayoverStatusEnum]] = Field(None, description="Filter by multiple statuses")
    
    # Date range
    check_in_date_from: Optional[date] = Field(None, description="Check-in date from")
    check_in_date_to: Optional[date] = Field(None, description="Check-in date to")
    
    # Other filters
    hotel_id: Optional[int] = Field(None, description="Filter by hotel")
    created_by: Optional[int] = Field(None, description="Filter by creator")
    layover_reason: Optional[LayoverReasonEnum] = Field(None, description="Filter by reason")
    trip_id: Optional[str] = Field(None, description="Filter by trip ID")
    
    # Search
    search: Optional[str] = Field(None, max_length=100, description="Search query")
    
    # Sorting
    order_by: str = Field(
        "check_in_date",
        description="Sort field (check_in_date, created_at, status)"
    )
    order_direction: str = Field(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort direction"
    )


# ==================== METRICS SCHEMAS ====================

class DashboardMetrics(BaseModel):
    """Dashboard summary metrics"""
    
    total_requests: int
    confirmed_count: int
    pending_count: int
    escalated_count: int
    on_hold_count: int
    declined_count: int
    completed_count: int
    confirmation_rate: float = Field(description="Percentage")
    avg_response_hours: float


class StationPerformance(BaseModel):
    """Station performance metrics"""
    
    station_id: int
    station_name: str
    station_code: str
    total_requests: int
    confirmed_count: int
    confirmation_rate: float
    avg_response_hours: float
    escalated_count: int


class HotelPerformance(BaseModel):
    """Hotel performance metrics"""
    
    hotel_id: int
    hotel_name: str
    station_name: str
    total_requests: int
    confirmed_count: int
    declined_count: int
    confirmation_rate: float
    decline_rate: float
    avg_response_hours: float
    last_response_date: Optional[datetime]
    rating: str = Field(description="excellent, good, average, poor")


# ==================== STATUS TIMELINE ====================

class StatusTimelineItem(BaseModel):
    """Single item in status timeline"""
    
    status: str
    timestamp: Optional[datetime]
    completed: bool
    
    class Config:
        from_attributes = True


class LayoverTimeline(BaseModel):
    """Complete status timeline for layover"""
    
    draft_created: StatusTimelineItem
    sent_to_hotel: StatusTimelineItem
    hotel_responded: StatusTimelineItem
    finalized: StatusTimelineItem
    crew_notified: StatusTimelineItem
    
    # Additional statuses
    on_hold: Optional[StatusTimelineItem] = None
    amended: Optional[StatusTimelineItem] = None
    escalated: Optional[StatusTimelineItem] = None
    cancelled: Optional[StatusTimelineItem] = None


# ==================== DUPLICATE SCHEMA ====================

class LayoverDuplicateResponse(BaseModel):
    """Response after duplicating a layover"""
    
    original_id: int
    new_layover: LayoverResponse
    duplicated_fields: List[str] = Field(
        description="List of fields that were duplicated"
    )
    cleared_fields: List[str] = Field(
        description="List of fields that were cleared (dates, status, etc.)"
    )