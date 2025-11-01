"""
Confirmation Service
Handles hotel confirmation link generation, validation, and response processing
"""

import uuid
from typing import Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.repositories.confirmation_token_repository import ConfirmationTokenRepository
from app.repositories.layover_repository import LayoverRepository
from app.repositories.audit_repository import AuditRepository
from app.core.exceptions import (
    TokenExpiredException,
    TokenAlreadyUsedException,
    InvalidStatusTransitionException,
)


class ConfirmationService:
    """Service for handling hotel confirmation flow"""

    def __init__(self, db: Session):
        self.db = db
        self.token_repo = ConfirmationTokenRepository(db)
        self.layover_repo = LayoverRepository(db)
        self.audit_repo = AuditRepository(db)

    def generate_hotel_confirmation_token(
        self,
        layover_id: int,
        hotel_id: int,
        expiry_hours: int = 72,
    ) -> str:
        """
        Generate a new hotel confirmation token
        
        Args:
            layover_id: ID of the layover
            hotel_id: ID of the hotel
            expiry_hours: Token expiry time in hours (default 72)
        
        Returns:
            str: UUID token string
        """
        # Check if an active token already exists
        existing_token = self.token_repo.get_active_hotel_token(layover_id, hotel_id)
        
        if existing_token:
            # Return existing token if still valid
            return existing_token.token

        # Generate new token
        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

        self.token_repo.create(
            token=token,
            token_type="hotel_confirmation",
            layover_id=layover_id,
            hotel_id=hotel_id,
            expires_at=expires_at,
        )

        # Audit log
        self.audit_repo.create(
            user_id=None,  # System action
            user_role="system",
            action_type="token_generated",
            entity_type="confirmation_token",
            entity_id=layover_id,
            details={
                "token_type": "hotel_confirmation",
                "hotel_id": hotel_id,
                "expires_at": expires_at.isoformat(),
            },
        )

        return token

    def validate_and_get_layover(self, token: str) -> Dict:
        """
        Validate token and return layover details for confirmation page
        
        Args:
            token: UUID token string
        
        Returns:
            Dict with layover details and hotel info
        
        Raises:
            TokenExpiredException: If token has expired
            TokenAlreadyUsedException: If token already used
            ValueError: If token invalid or layover not found
        """
        # Validate token
        db_token = self.token_repo.validate_token(token)

        # Get layover details
        layover = self.layover_repo.get_by_id(db_token.layover_id)
        
        if not layover:
            raise ValueError("Layover not found")

        # Check if layover is in a state where hotel can still respond
        if layover.status not in ["SENT", "PENDING", "CHANGES_REQUESTED"]:
            raise InvalidStatusTransitionException(
                f"Cannot respond to layover in status: {layover.status}"
            )

        return {
            "layover": layover,
            "token": db_token,
            "can_respond": True,
        }

    def confirm_booking(
        self,
        token: str,
        confirmation_number: Optional[str] = None,
        hotel_note: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict:
        """
        Process hotel confirmation
        
        Args:
            token: UUID token string
            confirmation_number: Hotel's confirmation number (optional)
            hotel_note: Optional note from hotel
            ip_address: IP address of hotel user
            user_agent: User agent string
        
        Returns:
            Dict with updated layover and success message
        """
        # Validate token
        db_token = self.token_repo.validate_token(token)
        layover = self.layover_repo.get_by_id(db_token.layover_id)

        if not layover:
            raise ValueError("Layover not found")

        # Check status
        if layover.status not in ["SENT", "PENDING", "CHANGES_REQUESTED"]:
            raise InvalidStatusTransitionException(
                f"Cannot confirm layover in status: {layover.status}"
            )

        # Update layover status
        old_status = layover.status
        layover.status = "CONFIRMED"
        layover.confirmed_at = datetime.utcnow()
        
        if confirmation_number:
            layover.hotel_confirmation_number = confirmation_number
        
        if hotel_note:
            layover.hotel_response_note = hotel_note

        # Store response metadata
        response_metadata = {
            "action": "confirmed",
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat(),
            "confirmation_number": confirmation_number,
            "note": hotel_note,
        }
        layover.hotel_response_metadata = response_metadata

        # Cancel any pending reminders (will be handled by ReminderService)
        layover.reminders_paused = True
        layover.reminders_paused_reason = "Hotel confirmed booking"
        layover.reminders_paused_at = datetime.utcnow()

        # Save changes
        updated_layover = self.layover_repo.update(layover)

        # Mark token as used
        self.token_repo.mark_as_used(token, response_metadata)

        # Audit log
        self.audit_repo.create(
            user_id=None,  # Hotel action (no user account)
            user_role="hotel",
            action_type="status_changed",
            entity_type="layover",
            entity_id=layover.id,
            details={
                "before": {"status": old_status},
                "after": {"status": "CONFIRMED"},
                "confirmation_number": confirmation_number,
                "hotel_note": hotel_note,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "success": True,
            "message": "Booking confirmed successfully",
            "layover": updated_layover,
        }

    def decline_booking(
        self,
        token: str,
        decline_reason: str,
        decline_note: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict:
        """
        Process hotel decline
        
        Args:
            token: UUID token string
            decline_reason: Reason for declining (fully_booked, insufficient_notice, etc.)
            decline_note: Optional additional details
            ip_address: IP address of hotel user
            user_agent: User agent string
        
        Returns:
            Dict with updated layover and message
        """
        # Validate token
        db_token = self.token_repo.validate_token(token)
        layover = self.layover_repo.get_by_id(db_token.layover_id)

        if not layover:
            raise ValueError("Layover not found")

        # Check status
        if layover.status not in ["SENT", "PENDING", "CHANGES_REQUESTED"]:
            raise InvalidStatusTransitionException(
                f"Cannot decline layover in status: {layover.status}"
            )

        # Update layover status
        old_status = layover.status
        layover.status = "DECLINED"
        layover.declined_at = datetime.utcnow()

        # Store decline reason
        decline_text = f"Reason: {decline_reason}"
        if decline_note:
            decline_text += f"\nDetails: {decline_note}"
        layover.hotel_response_note = decline_text

        # Store response metadata
        response_metadata = {
            "action": "declined",
            "reason": decline_reason,
            "note": decline_note,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat(),
        }
        layover.hotel_response_metadata = response_metadata

        # Cancel reminders
        layover.reminders_paused = True
        layover.reminders_paused_reason = "Hotel declined booking"
        layover.reminders_paused_at = datetime.utcnow()

        # Save changes
        updated_layover = self.layover_repo.update(layover)

        # Mark token as used
        self.token_repo.mark_as_used(token, response_metadata)

        # Audit log
        self.audit_repo.create(
            user_id=None,
            user_role="hotel",
            action_type="status_changed",
            entity_type="layover",
            entity_id=layover.id,
            details={
                "before": {"status": old_status},
                "after": {"status": "DECLINED"},
                "decline_reason": decline_reason,
                "decline_note": decline_note,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "success": True,
            "message": "Decline request processed",
            "layover": updated_layover,
        }

    def request_changes(
        self,
        token: str,
        change_types: list[str],
        change_note: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict:
        """
        Process hotel change request
        
        Args:
            token: UUID token string
            change_types: List of change types (e.g., ['dates', 'rooms', 'costs'])
            change_note: Required note explaining what changes are needed
            ip_address: IP address of hotel user
            user_agent: User agent string
        
        Returns:
            Dict with updated layover and message
        """
        # Validate token
        db_token = self.token_repo.validate_token(token)
        layover = self.layover_repo.get_by_id(db_token.layover_id)

        if not layover:
            raise ValueError("Layover not found")

        # Check status
        if layover.status not in ["SENT", "PENDING", "CHANGES_REQUESTED"]:
            raise InvalidStatusTransitionException(
                f"Cannot request changes for layover in status: {layover.status}"
            )

        # Update layover status
        old_status = layover.status
        layover.status = "CHANGES_REQUESTED"

        # Store change request
        change_text = f"Requested changes: {', '.join(change_types)}\n\n{change_note}"
        layover.hotel_response_note = change_text

        # Store response metadata
        response_metadata = {
            "action": "changes_requested",
            "change_types": change_types,
            "note": change_note,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat(),
        }
        layover.hotel_response_metadata = response_metadata

        # Pause reminders (Ops needs to review and respond)
        layover.reminders_paused = True
        layover.reminders_paused_reason = "Hotel requested changes - awaiting Ops review"
        layover.reminders_paused_at = datetime.utcnow()

        # Save changes
        updated_layover = self.layover_repo.update(layover)

        # Mark token as used
        self.token_repo.mark_as_used(token, response_metadata)

        # Audit log
        self.audit_repo.create(
            user_id=None,
            user_role="hotel",
            action_type="status_changed",
            entity_type="layover",
            entity_id=layover.id,
            details={
                "before": {"status": old_status},
                "after": {"status": "CHANGES_REQUESTED"},
                "change_types": change_types,
                "change_note": change_note,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "success": True,
            "message": "Change request submitted successfully",
            "layover": updated_layover,
        }

    def regenerate_token(
        self,
        layover_id: int,
        hotel_id: int,
    ) -> str:
        """
        Regenerate a new token for a layover (e.g., after changes made by Ops)
        
        Args:
            layover_id: ID of the layover
            hotel_id: ID of the hotel
        
        Returns:
            str: New UUID token string
        """
        # Invalidate any existing active tokens
        existing_token = self.token_repo.get_active_hotel_token(layover_id, hotel_id)
        if existing_token:
            self.token_repo.invalidate_token(existing_token.token)

        # Generate new token
        return self.generate_hotel_confirmation_token(layover_id, hotel_id)