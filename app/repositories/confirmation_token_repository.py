"""
Confirmation Token Repository
Handles database operations for confirmation tokens (hotel confirmation links)
"""

from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.confirmation_token import ConfirmationToken
from app.core.exceptions import TokenExpiredException, TokenAlreadyUsedException


class ConfirmationTokenRepository:
    """Repository for confirmation token database operations"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        token: str,
        token_type: str,
        layover_id: int,
        hotel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        expires_at: datetime = None,
    ) -> ConfirmationToken:
        """
        Create a new confirmation token
        
        Args:
            token: UUID token string
            token_type: Type of token (hotel_confirmation, crew_portal, password_reset)
            layover_id: ID of the layover
            hotel_id: ID of the hotel (for hotel_confirmation type)
            user_id: ID of the user (for crew_portal or password_reset type)
            expires_at: Expiry datetime (defaults to 72 hours from now)
        
        Returns:
            ConfirmationToken: Created token object
        """
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(hours=72)

        db_token = ConfirmationToken(
            token=token,
            token_type=token_type,
            layover_id=layover_id,
            hotel_id=hotel_id,
            user_id=user_id,
            expires_at=expires_at,
            is_valid=True,
        )

        self.db.add(db_token)
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def get_by_token(self, token: str) -> Optional[ConfirmationToken]:
        """
        Get confirmation token by token string
        
        Args:
            token: UUID token string
        
        Returns:
            ConfirmationToken or None if not found
        """
        return (
            self.db.query(ConfirmationToken)
            .filter(ConfirmationToken.token == token)
            .first()
        )

    def validate_token(self, token: str) -> ConfirmationToken:
        """
        Validate token and return if valid
        
        Args:
            token: UUID token string
        
        Returns:
            ConfirmationToken if valid
        
        Raises:
            TokenExpiredException: If token has expired
            TokenAlreadyUsedException: If token has already been used
            ValueError: If token not found or invalid
        """
        db_token = self.get_by_token(token)

        if not db_token:
            raise ValueError("Invalid token")

        if not db_token.is_valid:
            raise TokenAlreadyUsedException("This confirmation link has already been used")

        if db_token.expires_at < datetime.utcnow():
            raise TokenExpiredException("This confirmation link has expired")

        return db_token

    def mark_as_used(
        self,
        token: str,
        response_metadata: dict,
    ) -> ConfirmationToken:
        """
        Mark token as used and store response metadata
        
        Args:
            token: UUID token string
            response_metadata: Dict containing IP, user-agent, action, timestamp
        
        Returns:
            Updated ConfirmationToken
        """
        db_token = self.get_by_token(token)
        
        if not db_token:
            raise ValueError("Invalid token")

        db_token.used_at = datetime.utcnow()
        db_token.is_valid = False
        db_token.response_metadata = response_metadata

        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def invalidate_token(self, token: str) -> ConfirmationToken:
        """
        Manually invalidate a token (e.g., admin override, security)
        
        Args:
            token: UUID token string
        
        Returns:
            Updated ConfirmationToken
        """
        db_token = self.get_by_token(token)
        
        if not db_token:
            raise ValueError("Invalid token")

        db_token.is_valid = False
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def get_tokens_by_layover(self, layover_id: int) -> list[ConfirmationToken]:
        """
        Get all confirmation tokens for a specific layover
        
        Args:
            layover_id: ID of the layover
        
        Returns:
            List of ConfirmationToken objects
        """
        return (
            self.db.query(ConfirmationToken)
            .filter(ConfirmationToken.layover_id == layover_id)
            .order_by(ConfirmationToken.created_at.desc())
            .all()
        )

    def get_active_hotel_token(
        self, 
        layover_id: int, 
        hotel_id: int
    ) -> Optional[ConfirmationToken]:
        """
        Get the active (valid, not expired) hotel confirmation token for a layover
        
        Args:
            layover_id: ID of the layover
            hotel_id: ID of the hotel
        
        Returns:
            ConfirmationToken or None if no active token exists
        """
        return (
            self.db.query(ConfirmationToken)
            .filter(
                and_(
                    ConfirmationToken.layover_id == layover_id,
                    ConfirmationToken.hotel_id == hotel_id,
                    ConfirmationToken.token_type == "hotel_confirmation",
                    ConfirmationToken.is_valid == True,
                    ConfirmationToken.expires_at > datetime.utcnow(),
                )
            )
            .first()
        )

    def cleanup_expired_tokens(self, days_old: int = 30) -> int:
        """
        Delete expired tokens older than specified days (housekeeping)
        
        Args:
            days_old: Number of days after expiry to keep tokens
        
        Returns:
            Number of tokens deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        deleted_count = (
            self.db.query(ConfirmationToken)
            .filter(
                and_(
                    ConfirmationToken.expires_at < cutoff_date,
                    ConfirmationToken.is_valid == False,
                )
            )
            .delete(synchronize_session=False)
        )
        
        self.db.commit()
        return deleted_count