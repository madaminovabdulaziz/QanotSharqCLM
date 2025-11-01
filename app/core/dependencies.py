"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    user = UserRepository.get_by_id(db, int(user_id))
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (alias for get_current_user).
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        Current user if active
    """
    return current_user


def require_role(required_roles: list[UserRole]):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @app.get("/admin-only")
        def admin_endpoint(
            user: User = Depends(require_role([UserRole.ADMIN]))
        ):
            ...
    
    Args:
        required_roles: List of allowed roles
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in required_roles]}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for specific roles
require_admin = require_role([UserRole.ADMIN])
require_ops = require_role([UserRole.ADMIN, UserRole.OPS_COORDINATOR])
require_station = require_role([UserRole.ADMIN, UserRole.OPS_COORDINATOR, UserRole.STATION_USER])