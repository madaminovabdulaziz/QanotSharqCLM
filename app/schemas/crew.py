"""
Crew Member Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.crew_member import CrewRank


# ==================== CREW MEMBER SCHEMAS ====================

class CrewMemberBase(BaseModel):
    """Base crew member schema with common fields"""
    employee_id: str = Field(..., min_length=1, max_length=50, description="Airline employee ID")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    crew_rank: CrewRank = Field(..., description="Crew rank/position")
    seniority_number: Optional[int] = Field(None, ge=1, description="Seniority number (lower = more senior)")
    accommodation_preferences: Optional[Dict[str, Any]] = Field(None, description="Accommodation preferences JSON")
    medical_restrictions: Optional[str] = Field(None, max_length=500, description="Medical restrictions or requirements")


class CrewMemberCreate(CrewMemberBase):
    """Schema for creating a new crew member"""
    pass


class CrewMemberUpdate(BaseModel):
    """Schema for updating a crew member"""
    employee_id: Optional[str] = Field(None, min_length=1, max_length=50)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    crew_rank: Optional[CrewRank] = None
    seniority_number: Optional[int] = Field(None, ge=1)
    accommodation_preferences: Optional[Dict[str, Any]] = None
    medical_restrictions: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class CrewMemberResponse(CrewMemberBase):
    """Schema for crew member response"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def full_name(self) -> str:
        """Get crew member's full name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_pilot(self) -> bool:
        """Check if crew member is flight crew"""
        return self.crew_rank in [
            CrewRank.CAPTAIN,
            CrewRank.FIRST_OFFICER,
            CrewRank.SECOND_OFFICER
        ]


class CrewMemberListResponse(BaseModel):
    """Schema for paginated crew member list response"""
    items: List[CrewMemberResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== LAYOVER CREW ASSIGNMENT SCHEMAS ====================

class LayoverCrewBase(BaseModel):
    """Base layover crew assignment schema"""
    layover_id: int = Field(..., description="Layover ID")
    crew_member_id: int = Field(..., description="Crew member ID")
    room_number: Optional[str] = Field(None, max_length=20, description="Hotel room number")
    room_type: Optional[str] = Field(None, max_length=50, description="Room type: single, double, suite")
    room_allocation_priority: Optional[int] = Field(None, ge=1, description="Priority for room allocation")
    is_primary_contact: bool = Field(False, description="Primary contact for this layover")


class LayoverCrewCreate(BaseModel):
    """Schema for creating a crew assignment"""
    crew_member_id: int = Field(..., description="Crew member ID to assign")
    is_primary_contact: bool = Field(False, description="Set as primary contact")
    room_number: Optional[str] = Field(None, max_length=20)
    room_type: Optional[str] = Field(None, max_length=50)


class LayoverCrewBulkCreate(BaseModel):
    """Schema for bulk creating crew assignments"""
    crew_member_ids: List[int] = Field(..., min_length=1, description="List of crew member IDs to assign")
    auto_assign_primary: bool = Field(True, description="Auto-assign primary contact (Captain or Purser)")


class LayoverCrewUpdate(BaseModel):
    """Schema for updating a crew assignment"""
    room_number: Optional[str] = Field(None, max_length=20)
    room_type: Optional[str] = Field(None, max_length=50)
    is_primary_contact: Optional[bool] = None


class LayoverCrewResponse(LayoverCrewBase):
    """Schema for crew assignment response"""
    id: int
    crew_member: Optional[CrewMemberResponse] = None
    notification_status: str
    notified_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LayoverCrewListResponse(BaseModel):
    """Schema for list of crew assignments"""
    items: List[LayoverCrewResponse]
    total: int


# ==================== CREW NOTE SCHEMAS ====================

class NoteCreate(BaseModel):
    """Schema for creating a note"""
    note_text: str = Field(..., min_length=1, description="Note content")
    tagged_user_ids: Optional[List[int]] = Field(None, description="User IDs to tag (@mentions)")
    is_internal: bool = Field(True, description="Internal only (not visible to hotel)")


class NoteResponse(BaseModel):
    """Schema for note response"""
    id: int
    layover_id: int
    note_text: str
    tagged_user_ids: Optional[List[int]] = None
    is_internal: bool
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NoteListResponse(BaseModel):
    """Schema for list of notes"""
    items: List[NoteResponse]
    total: int


# ==================== FILE ATTACHMENT SCHEMAS ====================

class FileAttachmentResponse(BaseModel):
    """Schema for file attachment response"""
    id: int
    layover_id: int
    file_name: str
    file_size: int
    file_type: str
    scan_status: str
    scanned_at: Optional[datetime] = None
    uploaded_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)


class FileAttachmentListResponse(BaseModel):
    """Schema for list of file attachments"""
    items: List[FileAttachmentResponse]
    total: int


# ==================== FILTER & SEARCH SCHEMAS ====================

class CrewFilterParams(BaseModel):
    """Schema for crew member filtering parameters"""
    search: Optional[str] = Field(None, max_length=100, description="Search by name or employee ID")
    crew_rank: Optional[CrewRank] = Field(None, description="Filter by crew rank")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(25, ge=1, le=100, description="Items per page")
