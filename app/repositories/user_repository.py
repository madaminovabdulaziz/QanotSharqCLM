"""
User Repository - Database Access Layer
Handles all database operations for User entity.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import User, UserRole


class UserRepository:
    """
    Repository for User model database operations.
    
    Provides clean separation between business logic and data access.
    All database queries for users go through this repository.
    """
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    # ========================================
    # READ
    # ========================================
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email (case-insensitive).
        
        Args:
            email: User email address
            
        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.email == email).first()
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        role: Optional[UserRole] = None
    ) -> List[User]:
        """
        Get all users with pagination and filtering.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            is_active: Filter by active status (None = all)
            role: Filter by user role (None = all roles)
            
        Returns:
            List of users
        """
        query = self.db.query(User)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if role is not None:
            query = query.filter(User.role == role)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_role(self, role: UserRole) -> List[User]:
        """
        Get all users with a specific role.
        
        Args:
            role: User role to filter by
            
        Returns:
            List of users with that role
        """
        return self.db.query(User).filter(User.role == role).all()
    
    # ========================================
    # CREATE
    # ========================================
    
    def create(self, user: User) -> User:
        """
        Create a new user.
        
        Args:
            user: User model instance to create
            
        Returns:
            Created user instance
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    # ========================================
    # UPDATE
    # ========================================
    
    def update(self, user: User) -> User:
        """
        Update an existing user.
        
        Args:
            user: User model instance with updated fields
            
        Returns:
            Updated user instance
        """
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def activate(self, user_id: int) -> Optional[User]:
        """
        Activate a user account.
        
        Args:
            user_id: User ID to activate
            
        Returns:
            Activated user or None if not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        user.is_active = True
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def deactivate(self, user_id: int) -> Optional[User]:
        """
        Deactivate a user account (soft delete).
        
        Args:
            user_id: User ID to deactivate
            
        Returns:
            Deactivated user or None if not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return user
    
    # ========================================
    # DELETE
    # ========================================
    
    def delete(self, user: User) -> None:
        """
        Delete a user (hard delete).
        
        Note: This permanently removes the user from the database.
        Consider using deactivate() instead to preserve historical data.
        
        Args:
            user: User instance to delete
        """
        self.db.delete(user)
        self.db.commit()
    
    # ========================================
    # VALIDATION & UTILITIES
    # ========================================
    
    def email_exists(self, email: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if a user email already exists.
        
        Args:
            email: Email to check
            exclude_id: User ID to exclude from check (for updates)
            
        Returns:
            True if email exists, False otherwise
        """
        query = self.db.query(User).filter(User.email == email)
        
        if exclude_id:
            query = query.filter(User.id != exclude_id)
        
        return query.first() is not None
    
    def count(self, is_active: Optional[bool] = None) -> int:
        """
        Count total users.
        
        Args:
            is_active: Filter by active status (None = all)
            
        Returns:
            Count of users
        """
        query = self.db.query(User)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.count()
    
    def count_by_role(self, role: UserRole) -> int:
        """
        Count users by role.
        
        Args:
            role: User role to count
            
        Returns:
            Count of users with that role
        """
        return self.db.query(User).filter(User.role == role).count()