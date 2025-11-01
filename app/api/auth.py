"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.user import UserLogin, Token, UserResponse, UserCreate
from app.services.auth_service import AuthService
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    
    Returns JWT access token.
    """
    return AuthService.login(db, login_data)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user.
    
    Note: In production, you may want to restrict this endpoint
    or require admin authentication.
    """
    user = AuthService.register_user(db, user_data)
    return user


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    """
    return current_user


@router.post("/logout")
def logout():
    """
    Logout endpoint.
    
    In JWT-based auth, logout is typically handled client-side
    by deleting the token. This endpoint is a placeholder.
    """
    return {"message": "Successfully logged out"}