"""
Station Pydantic Schemas
Request/Response models for Station API endpoints with validation.
"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
import pytz


# ========================================
# REMINDER CONFIG SUB-SCHEMA
# ========================================

class ReminderConfig(BaseModel):
    """Reminder and escalation configuration for a station."""
    
    first_reminder_hours: int = Field(
        default=12,
        ge=1,
        le=48,
        description="Hours after send to send first reminder"
    )
    second_reminder_hours: int = Field(
        default=24,
        ge=1,
        le=72,
        description="Hours after send to send second reminder"
    )
    escalation_hours: int = Field(
        default=36,
        ge=1,
        le=96,
        description="Hours after send to escalate if no response"
    )
    business_hours_start: str = Field(
        default="08:00",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Business hours start time (HH:MM format)"
    )
    business_hours_end: str = Field(
        default="18:00",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Business hours end time (HH:MM format)"
    )
    pause_on_weekends: bool = Field(
        default=False,
        description="Whether to pause reminders on weekends"
    )
    
    @validator('second_reminder_hours')
    def validate_second_after_first(cls, v, values):
        """Ensure second reminder is after first reminder."""
        if 'first_reminder_hours' in values and v <= values['first_reminder_hours']:
            raise ValueError('second_reminder_hours must be greater than first_reminder_hours')
        return v
    
    @validator('escalation_hours')
    def validate_escalation_after_reminders(cls, v, values):
        """Ensure escalation is after second reminder."""
        if 'second_reminder_hours' in values and v <= values['second_reminder_hours']:
            raise ValueError('escalation_hours must be greater than second_reminder_hours')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "first_reminder_hours": 12,
            "second_reminder_hours": 24,
            "escalation_hours": 36,
            "business_hours_start": "08:00",
            "business_hours_end": "18:00",
            "pause_on_weekends": False
        }
    })


# ========================================
# BASE SCHEMAS
# ========================================

class StationBase(BaseModel):
    """Shared station fields."""
    
    code: str = Field(
        ...,
        min_length=3,
        max_length=10,
        description="IATA or ICAO airport code",
        examples=["LHR", "EGLL", "JFK"]
    )
    name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Full station name",
        examples=["London Heathrow", "John F Kennedy International"]
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City name",
        examples=["London", "New York"]
    )
    country: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Country name",
        examples=["United Kingdom", "United States"]
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone identifier",
        examples=["Europe/London", "America/New_York", "Asia/Dubai"]
    )
    
    @validator('code')
    def validate_code_uppercase(cls, v):
        """Ensure airport code is uppercase."""
        return v.upper().strip()
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Ensure timezone is valid IANA identifier."""
        if v not in pytz.all_timezones:
            raise ValueError(f'Invalid timezone: {v}. Must be valid IANA timezone.')
        return v


# ========================================
# CREATE SCHEMA
# ========================================

class StationCreate(StationBase):
    """Schema for creating a new station."""
    
    reminder_config: Optional[ReminderConfig] = Field(
        default=None,
        description="Custom reminder config (uses defaults if not provided)"
    )
    is_active: bool = Field(
        default=True,
        description="Whether station is active"
    )
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "code": "LHR",
            "name": "London Heathrow",
            "city": "London",
            "country": "United Kingdom",
            "timezone": "Europe/London",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "18:00",
                "pause_on_weekends": False
            },
            "is_active": True
        }
    })


# ========================================
# UPDATE SCHEMA
# ========================================

class StationUpdate(BaseModel):
    """Schema for updating an existing station (all fields optional)."""
    
    code: Optional[str] = Field(
        None,
        min_length=3,
        max_length=10,
        description="IATA or ICAO airport code"
    )
    name: Optional[str] = Field(
        None,
        min_length=3,
        max_length=255,
        description="Full station name"
    )
    city: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="City name"
    )
    country: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Country name"
    )
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone identifier"
    )
    reminder_config: Optional[ReminderConfig] = Field(
        None,
        description="Reminder/escalation configuration"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether station is active"
    )
    
    @validator('code')
    def validate_code_uppercase(cls, v):
        """Ensure airport code is uppercase."""
        if v is not None:
            return v.upper().strip()
        return v
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Ensure timezone is valid IANA identifier."""
        if v is not None and v not in pytz.all_timezones:
            raise ValueError(f'Invalid timezone: {v}. Must be valid IANA timezone.')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "London Heathrow International",
            "reminder_config": {
                "first_reminder_hours": 8,
                "second_reminder_hours": 16,
                "escalation_hours": 24
            }
        }
    })


# ========================================
# RESPONSE SCHEMA
# ========================================

class StationResponse(StationBase):
    """Schema for station responses (includes all fields + metadata)."""
    
    id: int = Field(..., description="Station ID")
    reminder_config: ReminderConfig = Field(..., description="Reminder configuration")
    is_active: bool = Field(..., description="Active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "code": "LHR",
                "name": "London Heathrow",
                "city": "London",
                "country": "United Kingdom",
                "timezone": "Europe/London",
                "reminder_config": {
                    "first_reminder_hours": 12,
                    "second_reminder_hours": 24,
                    "escalation_hours": 36,
                    "business_hours_start": "08:00",
                    "business_hours_end": "18:00",
                    "pause_on_weekends": False
                },
                "is_active": True,
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z"
            }
        }
    )


# ========================================
# LIST RESPONSE SCHEMA
# ========================================

class StationListResponse(BaseModel):
    """Paginated list of stations."""
    
    stations: list[StationResponse] = Field(..., description="List of stations")
    total: int = Field(..., description="Total number of stations")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stations": [
                {
                    "id": 1,
                    "code": "LHR",
                    "name": "London Heathrow",
                    "city": "London",
                    "country": "United Kingdom",
                    "timezone": "Europe/London",
                    "reminder_config": {
                        "first_reminder_hours": 12,
                        "second_reminder_hours": 24,
                        "escalation_hours": 36,
                        "business_hours_start": "08:00",
                        "business_hours_end": "18:00",
                        "pause_on_weekends": False
                    },
                    "is_active": True,
                    "created_at": "2025-01-15T10:30:00Z",
                    "updated_at": "2025-01-15T10:30:00Z"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 25
        }
    })