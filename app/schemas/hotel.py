"""
Hotel Pydantic Schemas
Request/Response models for Hotel API endpoints with validation.
"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# ========================================
# ENUMS
# ========================================

class ContractType(str, Enum):
    """Hotel contract types (SME Priority - contract rate tracking)."""
    AD_HOC = "ad_hoc"
    BLOCK_BOOKING = "block_booking"
    PREFERRED_RATE = "preferred_rate"


# ========================================
# PERFORMANCE METRICS SUB-SCHEMA
# ========================================

class PerformanceMetrics(BaseModel):
    """Hotel performance statistics."""
    
    total_requests: int = Field(default=0, ge=0)
    confirmed_count: int = Field(default=0, ge=0)
    declined_count: int = Field(default=0, ge=0)
    avg_response_hours: float = Field(default=0.0, ge=0.0)
    last_updated: Optional[datetime] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total_requests": 50,
            "confirmed_count": 45,
            "declined_count": 3,
            "avg_response_hours": 8.5,
            "last_updated": "2025-01-15T03:00:00Z"
        }
    })


# ========================================
# BASE SCHEMAS
# ========================================

class HotelBase(BaseModel):
    """Shared hotel fields."""
    
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Hotel name",
        examples=["Heathrow Hilton", "JFK Marriott"]
    )
    address: str = Field(
        ...,
        min_length=5,
        description="Full hotel address",
        examples=["123 Airport Road, Hounslow, London"]
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City name",
        examples=["London", "New York"]
    )
    postal_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Postal/ZIP code",
        examples=["TW6 2GA", "11430"]
    )
    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Hotel phone number",
        examples=["+44-20-1234-5678", "+1-718-555-0100"]
    )
    email: str = Field(
        ...,
        description="Primary contact email for layover requests",
        examples=["reservations@heathrowhilton.com"]
    )


# ========================================
# CREATE SCHEMA
# ========================================

class HotelCreate(HotelBase):
    """Schema for creating a new hotel."""
    
    station_id: int = Field(
        ...,
        gt=0,
        description="ID of the station this hotel serves"
    )
    secondary_emails: Optional[List[str]] = Field(
        None,
        max_length=5,
        description="Additional emails for CC (max 5)",
        examples=[["backup@hotel.com", "night@hotel.com"]]
    )
    whatsapp_number: Optional[str] = Field(
        None,
        max_length=20,
        description="WhatsApp number (international format)",
        examples=["+44-20-1234-5678"]
    )
    whatsapp_enabled: bool = Field(
        default=False,
        description="Whether WhatsApp notifications are enabled"
    )
    contract_type: ContractType = Field(
        default=ContractType.AD_HOC,
        description="Type of contract agreement"
    )
    contract_rate: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Pre-negotiated rate per room per night (USD)",
        examples=[120.00, 150.50]
    )
    contract_valid_until: Optional[date] = Field(
        None,
        description="Contract expiration date",
        examples=["2025-12-31"]
    )
    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Internal notes about the hotel",
        examples=["Prefers 24h notice. Late check-in difficult after 23:00."]
    )
    is_active: bool = Field(
        default=True,
        description="Whether hotel is active"
    )
    
    @validator('secondary_emails')
    def validate_secondary_emails_unique(cls, v, values):
        """Ensure secondary emails don't duplicate primary email."""
        if v and 'email' in values:
            primary = values['email']
            if primary in v:
                raise ValueError('Secondary emails cannot include primary email')
            if len(v) != len(set(v)):
                raise ValueError('Secondary emails must be unique')
        return v
    
    @validator('contract_rate')
    def validate_contract_rate_with_type(cls, v, values):
        """If contract_rate provided, contract_type must not be ad_hoc."""
        if v is not None and values.get('contract_type') == ContractType.AD_HOC:
            raise ValueError('contract_rate cannot be set for ad_hoc contract type')
        return v
    
    @validator('whatsapp_number')
    def validate_whatsapp_number(cls, v):
        """Basic WhatsApp number format validation."""
        if v:
            # Remove common separators
            cleaned = v.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            if not cleaned.startswith('+'):
                raise ValueError('WhatsApp number must start with + (international format)')
            if not cleaned[1:].isdigit():
                raise ValueError('WhatsApp number must contain only digits after +')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "station_id": 1,
            "name": "Heathrow Hilton",
            "address": "123 Airport Road, Hounslow",
            "city": "London",
            "postal_code": "TW6 2GA",
            "phone": "+44-20-1234-5678",
            "email": "reservations@heathrowhilton.com",
            "secondary_emails": ["backup@heathrowhilton.com"],
            "whatsapp_number": "+44-20-1234-5678",
            "whatsapp_enabled": True,
            "contract_type": "preferred_rate",
            "contract_rate": 120.00,
            "contract_valid_until": "2025-12-31",
            "notes": "Prefers 24h notice for large groups.",
            "is_active": True
        }
    })


# ========================================
# UPDATE SCHEMA
# ========================================

class HotelUpdate(BaseModel):
    """Schema for updating an existing hotel (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    address: Optional[str] = Field(None, min_length=5)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = None
    secondary_emails: Optional[List[str]] = Field(None, max_length=5)
    whatsapp_number: Optional[str] = Field(None, max_length=20)
    whatsapp_enabled: Optional[bool] = None
    contract_type: Optional[ContractType] = None
    contract_rate: Optional[Decimal] = Field(None, ge=0)
    contract_valid_until: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None
    
    @validator('secondary_emails')
    def validate_secondary_emails_unique(cls, v):
        """Ensure secondary emails are unique."""
        if v and len(v) != len(set(v)):
            raise ValueError('Secondary emails must be unique')
        return v
    
    @validator('whatsapp_number')
    def validate_whatsapp_number(cls, v):
        """Basic WhatsApp number format validation."""
        if v:
            cleaned = v.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
            if not cleaned.startswith('+'):
                raise ValueError('WhatsApp number must start with + (international format)')
            if not cleaned[1:].isdigit():
                raise ValueError('WhatsApp number must contain only digits after +')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "contract_rate": 125.00,
            "contract_valid_until": "2026-12-31",
            "notes": "Updated: Now accepts same-day bookings."
        }
    })


# ========================================
# RESPONSE SCHEMA
# ========================================

class HotelResponse(HotelBase):
    """Schema for hotel responses (includes all fields + metadata)."""
    
    id: int = Field(..., description="Hotel ID")
    station_id: int = Field(..., description="Station ID")
    secondary_emails: Optional[List[str]] = Field(None, description="Secondary contact emails")
    whatsapp_number: Optional[str] = None
    whatsapp_enabled: bool = Field(..., description="WhatsApp enabled status")
    contract_type: ContractType = Field(..., description="Contract type")
    contract_rate: Optional[Decimal] = None
    contract_valid_until: Optional[date] = None
    notes: Optional[str] = None
    performance_metrics: PerformanceMetrics = Field(..., description="Performance statistics")
    is_active: bool = Field(..., description="Active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "station_id": 1,
                "name": "Heathrow Hilton",
                "address": "123 Airport Road, Hounslow",
                "city": "London",
                "postal_code": "TW6 2GA",
                "phone": "+44-20-1234-5678",
                "email": "reservations@heathrowhilton.com",
                "secondary_emails": ["backup@heathrowhilton.com"],
                "whatsapp_number": "+44-20-1234-5678",
                "whatsapp_enabled": True,
                "contract_type": "preferred_rate",
                "contract_rate": 120.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Prefers 24h notice.",
                "performance_metrics": {
                    "total_requests": 50,
                    "confirmed_count": 45,
                    "declined_count": 3,
                    "avg_response_hours": 8.5,
                    "last_updated": "2025-01-15T03:00:00Z"
                },
                "is_active": True,
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z"
            }
        }
    )


# ========================================
# RESPONSE WITH STATION INFO
# ========================================

class HotelWithStationResponse(HotelResponse):
    """Hotel response with embedded station information."""
    
    station: Dict[str, Any] = Field(..., description="Station details")
    
    model_config = ConfigDict(from_attributes=True)


# ========================================
# LIST RESPONSE SCHEMA
# ========================================

class HotelListResponse(BaseModel):
    """Paginated list of hotels."""
    
    hotels: List[HotelResponse] = Field(..., description="List of hotels")
    total: int = Field(..., description="Total number of hotels")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "hotels": [
                {
                    "id": 1,
                    "station_id": 1,
                    "name": "Heathrow Hilton",
                    "address": "123 Airport Road, Hounslow",
                    "city": "London",
                    "postal_code": "TW6 2GA",
                    "phone": "+44-20-1234-5678",
                    "email": "reservations@heathrowhilton.com",
                    "secondary_emails": None,
                    "whatsapp_number": None,
                    "whatsapp_enabled": False,
                    "contract_type": "ad_hoc",
                    "contract_rate": None,
                    "contract_valid_until": None,
                    "notes": None,
                    "performance_metrics": {
                        "total_requests": 0,
                        "confirmed_count": 0,
                        "declined_count": 0,
                        "avg_response_hours": 0.0,
                        "last_updated": None
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