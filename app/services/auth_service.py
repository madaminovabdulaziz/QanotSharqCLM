"""
Authentication service for login and user management.
"""
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserLogin, Token, UserCreate
from app.repositories.user_repository import UserRepository
from app.core.security import verify_password, hash_password, create_access_token


class AuthService:
    """Service for authentication operations"""
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            
        Returns:
            User object if authenticated, None otherwise
        """
        # Create repository instance
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(email)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        # Update last login timestamp
        user.last_login_at = datetime.utcnow()
        db.commit()
        
        return user
    
    @staticmethod
    def create_token_for_user(user: User) -> Token:
        """
        Create access token for authenticated user.
        
        Args:
            user: Authenticated user
            
        Returns:
            Token object with access_token
        """
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = create_access_token(data=token_data)
        
        return Token(access_token=access_token, token_type="bearer")
    
    @staticmethod
    def login(db: Session, login_data: UserLogin) -> Token:
        """
        Login user and return access token.
        
        Args:
            db: Database session
            login_data: Login credentials
            
        Returns:
            Token object
            
        Raises:
            HTTPException: If credentials are invalid
        """
        user = AuthService.authenticate_user(
            db,
            login_data.email,
            login_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return AuthService.create_token_for_user(user)
    
    @staticmethod
    def register_user(db: Session, user_data: UserCreate) -> User:
        """
        Register a new user.
        
        Args:
            db: Database session
            user_data: User registration data
            
        Returns:
            Created user
            
        Raises:
            HTTPException: If email already exists
        """
        # Create repository instance
        user_repo = UserRepository(db)
        
        # Check if email already exists
        existing_user = user_repo.get_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        new_user = User(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            role=user_data.role,
            station_ids=user_data.station_ids,
            is_active=True
        )
        
        return user_repo.create(new_user)