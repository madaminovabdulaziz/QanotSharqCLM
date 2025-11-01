"""
User Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: str
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: UserRole


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8, max_length=72)
    station_ids: Optional[List[int]] = None


class UserUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[UserRole] = None
    station_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response (without password)"""
    id: int
    station_ids: Optional[List[int]] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # For Pydantic v2 (was orm_mode in v1)


class UserLogin(BaseModel):
    """Schema for login request"""
    email: str
    password: str


class Token(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload"""
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None