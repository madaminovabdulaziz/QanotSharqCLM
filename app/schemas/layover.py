"""
Layover Schemas - Pydantic models for request/response validation
Pydantic v2 compatible + validations aligned with aviation operational requirements
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, condecimal


# ==================== ENUMS ====================

class LayoverStatusEnum(str, Enum):
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
    SCHEDULED_REST = "scheduled_rest"
    POSITIONING = "positioning"
    TRAINING = "training"
    STANDBY = "standby"
    IRREGULAR_OPS = "irregular_ops"
    OTHER = "other"


class CancellationReasonEnum(str, Enum):
    FLIGHT_CANCELLED = "flight_cancelled"
    CREW_CHANGE = "crew_change"
    WEATHER_DIVERSION = "weather_diversion"
    OPERATIONAL_DECISION = "operational_decision"
    OTHER = "other"


# ==================== BASE SCHEMAS ====================

class RoomBreakdown(BaseModel):
    """Room breakdown structure"""
    model_config = ConfigDict(from_attributes=True)

    singles: int = Field(ge=0, description="Number of single rooms")
    doubles: int = Field(ge=0, description="Number of double rooms")
    suites: int = Field(ge=0, description="Number of suites")

    @model_validator(mode="after")
    def validate_at_least_one_room(self):
        total = (self.singles or 0) + (self.doubles or 0) + (self.suites or 0)
        if total == 0:
            raise ValueError("At least one room must be requested")
        return self


class StationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    city: str
    country: str


class HotelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str
    phone: Optional[str]
    email: str


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    first_name: str
    last_name: str
    role: str


# ==================== CREATE SCHEMA ====================

class LayoverCreate(BaseModel):
    """Schema for creating a new layover request"""

    # Route & Station
    origin_station_code: Optional[str] = Field(None, max_length=10)
    destination_station_code: Optional[str] = Field(None, max_length=10)
    station_id: int = Field(..., description="Station handling this layover")
    hotel_id: Optional[int] = Field(None, description="Preferred hotel")

    # Reason / context
    layover_reason: LayoverReasonEnum = Field(LayoverReasonEnum.SCHEDULED_REST)
    operational_flight_number: Optional[str] = Field(None, max_length=20)

    # Dates & Times
    check_in_date: date
    check_in_time: time
    check_out_date: date
    check_out_time: time

    # Crew & Rooms
    crew_count: int = Field(..., ge=1, le=100)
    room_breakdown: RoomBreakdown

    # Special Requirements
    special_requirements: Optional[str] = Field(None, max_length=1000)
    transport_required: bool = False
    transport_details: Optional[str] = Field(None, max_length=500)

    # Multi-leg Trip
    trip_id: Optional[str] = Field(None, max_length=50)
    trip_sequence: Optional[int] = Field(None, ge=1)
    is_positioning: bool = False

    # Cost Tracking (API shows decimal; DB stores cents)
    estimated_cost: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    currency: str = Field("USD", max_length=3)

    @model_validator(mode="after")
    def validate_route_for_scheduled_rest(self):
        if self.layover_reason == LayoverReasonEnum.SCHEDULED_REST:
            if not self.origin_station_code or not self.destination_station_code:
                raise ValueError("Origin and destination required for scheduled rest layovers")
        return self

    @model_validator(mode="after")
    def validate_checkout_after_checkin(self):
        check_in_dt = datetime.combine(self.check_in_date, self.check_in_time)
        check_out_dt = datetime.combine(self.check_out_date, self.check_out_time)
        if check_out_dt <= check_in_dt:
            raise ValueError("Check-out must be after check-in")
        return self

    @model_validator(mode="after")
    def validate_transport_details_required(self):
        if self.transport_required and not self.transport_details:
            raise ValueError("Transport details required when transport is needed")
        return self

    @model_validator(mode="after")
    def validate_trip_sequence_required(self):
        if self.trip_id and not self.trip_sequence:
            raise ValueError("Trip sequence required when trip_id is provided")
        return self


# ==================== UPDATE SCHEMAS ====================

class LayoverUpdate(BaseModel):
    """Schema for updating a layover (draft only or specific fields)"""

    hotel_id: Optional[int] = None
    special_requirements: Optional[str] = Field(None, max_length=1000)
    transport_required: Optional[bool] = None
    transport_details: Optional[str] = Field(None, max_length=500)
    estimated_cost: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    currency: Optional[str] = Field(None, max_length=3)
    room_breakdown: Optional[RoomBreakdown] = None

    @model_validator(mode="after")
    def validate_transport_pair(self):
        # Only enforce when transport_required explicitly True
        if self.transport_required is True and not self.transport_details:
            raise ValueError("Transport details required when transport is needed")
        return self


class LayoverAmend(BaseModel):
    amendment_reason: str = Field(..., max_length=500)
    room_breakdown: Optional[RoomBreakdown] = None
    special_requirements: Optional[str] = Field(None, max_length=1000)
    transport_required: Optional[bool] = None
    transport_details: Optional[str] = Field(None, max_length=500)
    hotel_id: Optional[int] = None


class LayoverHold(BaseModel):
    on_hold_reason: str = Field(..., max_length=255)


class LayoverFinalize(BaseModel):
    hotel_confirmation_number: Optional[str] = Field(None, max_length=100)
    final_notes: Optional[str] = Field(None, max_length=1000)
    send_sms_notification: bool = False


class LayoverCancel(BaseModel):
    cancellation_reason: CancellationReasonEnum
    cancellation_note: Optional[str] = Field(None, max_length=500)


# ==================== RESPONSE SCHEMAS ====================

class LayoverResponse(BaseModel):
    """Basic layover response (for list views)"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str

    origin_station_code: Optional[str]
    destination_station_code: Optional[str]
    station_id: int
    hotel_id: Optional[int]

    layover_reason: str
    operational_flight_number: Optional[str]

    check_in_date: date
    check_in_time: time
    check_out_date: date
    check_out_time: time

    crew_count: int
    room_breakdown: Dict[str, int]

    status: str

    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime]
    confirmed_at: Optional[datetime]

    station: Optional[StationBase] = None
    hotel: Optional[HotelBase] = None
    creator: Optional[UserBase] = None


class LayoverDetailResponse(LayoverResponse):
    """Detailed layover response (for detail view)"""

    special_requirements: Optional[str]
    transport_required: bool
    transport_details: Optional[str]

    pending_at: Optional[datetime]
    declined_at: Optional[datetime]
    escalated_at: Optional[datetime]
    completed_at: Optional[datetime]

    hotel_response_note: Optional[str]
    hotel_response_metadata: Optional[Dict[str, Any]]

    last_reminder_sent_at: Optional[datetime]
    reminder_count: int
    reminders_paused: bool
    reminders_paused_reason: Optional[str]

    on_hold_at: Optional[datetime]
    on_hold_reason: Optional[str]

    amendment_count: int
    last_amended_at: Optional[datetime]
    hotel_notified_of_amendment: bool

    hotel_confirmation_number: Optional[str]

    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    cancellation_notice_hours: Optional[int] = None

    # expose charge metadata to UI
    cancellation_charge_applies: Optional[bool] = None
    cancellation_charge_policy: Optional[str] = None
    cancellation_charge_percent: Optional[int] = None
    cancellation_fee_cents: Optional[int] = None


    trip_id: Optional[str]
    trip_sequence: Optional[int]
    is_positioning: bool

    # Costs (API = Decimal, DB stores cents)
    estimated_cost: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    actual_cost: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    currency: str

    created_by: int


class LayoverListResponse(BaseModel):
    """Paginated list of layovers"""
    items: List[LayoverResponse]
    total: int
    page: int
    page_size: int
    total_pages: int = 0

    @model_validator(mode="after")
    def calculate_total_pages(self):
        # compute after model init
        page_size = self.page_size or 0
        if page_size <= 0:
            self.total_pages = 0
        else:
            self.total_pages = (self.total + page_size - 1) // page_size
        return self


# ==================== FILTER SCHEMAS ====================

class LayoverFilterParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=100)

    station_ids: Optional[List[int]] = None
    status: Optional[LayoverStatusEnum] = None
    statuses: Optional[List[LayoverStatusEnum]] = None

    check_in_date_from: Optional[date] = None
    check_in_date_to: Optional[date] = None

    hotel_id: Optional[int] = None
    created_by: Optional[int] = None
    layover_reason: Optional[LayoverReasonEnum] = None
    trip_id: Optional[str] = None

    search: Optional[str] = Field(None, max_length=100)

    order_by: str = Field("check_in_date", description="check_in_date, created_at, status")
    order_direction: str = Field("desc", pattern="^(asc|desc)$")


# ==================== METRICS SCHEMAS ====================

class DashboardMetrics(BaseModel):
    total_requests: int
    confirmed_count: int
    pending_count: int
    escalated_count: int
    on_hold_count: int
    declined_count: int
    completed_count: int
    confirmation_rate: float
    avg_response_hours: float
    # NEW: to match repository enhancement (HH:MM string)
    avg_response_hhmm: Optional[str] = None


class StationPerformance(BaseModel):
    station_id: int
    station_name: str
    station_code: str
    total_requests: int
    confirmed_count: int
    confirmation_rate: float
    avg_response_hours: float
    # NEW
    avg_response_hhmm: Optional[str] = None
    escalated_count: int


class HotelPerformance(BaseModel):
    hotel_id: int
    hotel_name: str
    station_name: str
    total_requests: int
    confirmed_count: int
    declined_count: int
    confirmation_rate: float
    decline_rate: float
    avg_response_hours: float
    # NEW
    avg_response_hhmm: Optional[str] = None
    last_response_date: Optional[datetime]
    rating: str  # excellent, good, average, poor


# ==================== STATUS TIMELINE ====================

class StatusTimelineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    timestamp: Optional[datetime]
    completed: bool


class LayoverTimeline(BaseModel):
    draft_created: StatusTimelineItem
    sent_to_hotel: StatusTimelineItem
    hotel_responded: StatusTimelineItem
    finalized: StatusTimelineItem
    crew_notified: StatusTimelineItem

    on_hold: Optional[StatusTimelineItem] = None
    amended: Optional[StatusTimelineItem] = None
    escalated: Optional[StatusTimelineItem] = None
    cancelled: Optional[StatusTimelineItem] = None


class LayoverDuplicateResponse(BaseModel):
    original_id: int
    new_layover: LayoverResponse
    duplicated_fields: List[str]
    cleared_fields: List[str]
