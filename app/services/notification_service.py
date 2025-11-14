"""
Notification Service
Orchestrates all outbound communications for layover workflow
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.email_service import EmailService
from app.repositories.layover_repository import LayoverRepository
from app.repositories.user_repository import UserRepository
from app.repositories.hotel_repository import HotelRepository
from app.repositories.station_repository import StationRepository
from app.repositories.audit_repository import AuditRepository
from app.core.config import settings
from app.core.exceptions import BusinessRuleException

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for managing all notifications in layover workflow
    
    Handles:
    - Hotel request emails
    - Hotel reminder emails
    - Ops confirmation/decline/change notifications
    - Escalation alerts
    - Crew notifications
    """
    
    def __init__(self, db: Session):
        """Initialize notification service"""
        self.db = db
        self.email_service = EmailService(db)
        self.layover_repo = LayoverRepository(db)
        self.user_repo = UserRepository(db)
        self.hotel_repo = HotelRepository(db)
        self.station_repo = StationRepository(db)
        self.audit_repo = AuditRepository(db)
        # NOTE: No self.notification_service - that was causing circular import!
    
    # ==================== HOTEL NOTIFICATIONS ====================
    
    def send_hotel_request(
        self,
        layover_id: int,
        confirmation_token: str,
    ) -> Dict:
        """
        Send initial hotel confirmation request email
        
        Args:
            layover_id: ID of the layover
            confirmation_token: Confirmation token (UUID)
        
        Returns:
            Dict with success status and notification_id
        
        Raises:
            BusinessRuleException: If layover/hotel not found or email fails
        """
        # Get layover with relations
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        if not layover.hotel:
            raise BusinessRuleException("Hotel not assigned to layover")
        
        if not layover.hotel.email:
            raise BusinessRuleException(
                f"Hotel '{layover.hotel.name}' does not have an email address. "
                "Please update the hotel profile before sending request."
            )
        
        hotel = layover.hotel
        station = layover.station
        
        # Calculate duration
        checkin_dt = datetime.combine(layover.check_in_date, layover.check_in_time)
        checkout_dt = datetime.combine(layover.check_out_date, layover.check_out_time)
        duration_hours = int((checkout_dt - checkin_dt).total_seconds() / 3600)
        
        # Build confirmation URL
        confirmation_url = f"{settings.FRONTEND_URL}/api/confirm/{confirmation_token}"
        
        # Token expiration (72 hours from now)
        token_expires_at = (datetime.utcnow() + timedelta(hours=72)).strftime("%B %d, %Y at %I:%M %p UTC")
        
        # Get ops contact info
        ops_user = None
        if layover.created_by:
            ops_user = self.user_repo.get_by_id(layover.created_by)
        
        # Prepare template context
        context = {
            # App info
            "app_name": settings.APP_NAME,
            "support_email": settings.SMTP_FROM_EMAIL,
            
            # Hotel info
            "hotel_name": hotel.name,
            
            # Layover details
            "layover_id": layover.id,
            "origin_station": layover.origin_station_code,
            "destination_station": layover.destination_station_code,
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "check_in_time": layover.check_in_time.strftime("%I:%M %p"),
            "check_out_date": layover.check_out_date.strftime("%B %d, %Y"),
            "check_out_time": layover.check_out_time.strftime("%I:%M %p"),
            "duration_hours": duration_hours,
            "crew_count": layover.crew_count,
            "rooms": layover.room_breakdown,
            "special_requirements": layover.special_requirements,
            "transport_required": layover.transport_required,
            "transport_details": layover.transport_details,
            
            # Station info
            "station_name": station.name if station else layover.destination_station_code,
            
            # Confirmation
            "confirmation_url": confirmation_url,
            "token_expires_at": token_expires_at,
            
            # Contact info
            "ops_contact_name": f"{ops_user.first_name} {ops_user.last_name}" if ops_user else None,
            "ops_contact_email": ops_user.email if ops_user else settings.SMTP_FROM_EMAIL,
            "ops_contact_phone": ops_user.phone if ops_user else None,
        }
        
        # Subject line
        subject = (
            f"Layover Request - {layover.origin_station_code}→{layover.destination_station_code} "
            f"- {layover.check_in_date.strftime('%b %d, %Y')}"
        )
        
        # Send email
        try:
            result = self.email_service.send_templated_email(
                to_email=hotel.email,
                template_name="hotel_request.html",
                context=context,
                subject=subject,
                cc_emails=hotel.secondary_emails if hotel.secondary_emails else None,
                layover_id=layover_id,
                notification_type="hotel_request"
            )
            
            # Log audit trail
            if result["success"]:
                self.audit_repo.create(
                    user_id=layover.created_by,
                    user_role="ops_coordinator",
                    action_type="notification_sent",
                    entity_type="layover",
                    entity_id=layover_id,
                    details={
                        "notification_type": "hotel_request",
                        "recipient": hotel.email,
                        "hotel_name": hotel.name,
                        "notification_id": result.get("notification_id")
                    }
                )
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to send hotel request email: {str(e)}")
            raise BusinessRuleException(f"Failed to send email to hotel: {str(e)}")
    
    def send_hotel_reminder(
        self,
        layover_id: int,
        confirmation_token: str,
        reminder_number: int = 1,
    ) -> Dict:
        """
        Send reminder email to hotel for pending request
        
        Args:
            layover_id: ID of the layover
            confirmation_token: Confirmation token (same as original)
            reminder_number: 1 for first reminder, 2 for second
        
        Returns:
            Dict with success status
        """
        # Get layover with relations
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        if not layover.hotel or not layover.hotel.email:
            raise BusinessRuleException("Hotel email not available")
        
        hotel = layover.hotel
        
        # Build confirmation URL
        confirmation_url = f"{settings.FRONTEND_URL}/api/confirm/{confirmation_token}"
        
        # Calculate hours remaining before escalation
        if layover.sent_at:
            elapsed_hours = int((datetime.utcnow() - layover.sent_at).total_seconds() / 3600)
            station_config = layover.station.get_reminder_config() if layover.station else {}
            escalation_hours = station_config.get("escalation_hours", 36)
            hours_remaining = max(0, escalation_hours - elapsed_hours)
        else:
            hours_remaining = 36
        
        # Prepare context
        context = {
            "app_name": settings.APP_NAME,
            "support_email": settings.SMTP_FROM_EMAIL,
            "hotel_name": hotel.name,
            "layover_id": layover.id,
            "origin_station": layover.origin_station_code,
            "destination_station": layover.destination_station_code,
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "reminder_number": reminder_number,
            "hours_remaining": hours_remaining,
            "confirmation_url": confirmation_url,
        }
        
        # Subject with urgency
        urgency = "REMINDER" if reminder_number == 1 else "URGENT REMINDER"
        subject = (
            f"{urgency}: Layover Request #{layover.id} - "
            f"{layover.origin_station_code}→{layover.destination_station_code}"
        )
        
        # Send email
        result = self.email_service.send_templated_email(
            to_email=hotel.email,
            template_name="hotel_reminder.html",
            context=context,
            subject=subject,
            layover_id=layover_id,
            notification_type="hotel_reminder"
        )
        
        # Log audit
        if result["success"]:
            self.audit_repo.create(
                user_id=None,
                user_role="system",
                action_type="reminder_sent",
                entity_type="layover",
                entity_id=layover_id,
                details={
                    "reminder_number": reminder_number,
                    "recipient": hotel.email,
                    "hours_remaining": hours_remaining
                }
            )
        
        return result



    def send_amendment_notification(
        self,
        layover_id: int,
        amendment_reason: Optional[str] = None,
    ) -> Dict:
        """
        Send amendment notification email to hotel
        
        Args:
            layover_id: ID of amended layover
            amendment_reason: Reason for amendment
        
        Returns:
            Dict with success status and notification details
        """
        # Load layover with all relations
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        
        if not layover:
            return {
                "success": False,
                "message": f"Layover {layover_id} not found"
            }
        
        hotel = layover.hotel
        if not hotel:
            return {
                "success": False,
                "message": "Hotel not assigned to layover"
            }
        
        if not hotel.email:
            return {
                "success": False,
                "message": f"Hotel '{hotel.name}' does not have an email address"
            }
        
        # Generate new confirmation token for amendment acknowledgment
        from app.models.confirmation_token import ConfirmationToken, TokenType
        from datetime import timedelta
        import uuid
        
        token = ConfirmationToken(
            token=str(uuid.uuid4()),
            token_type=TokenType.HOTEL_CONFIRMATION,
            layover_id=layover.id,
            hotel_id=hotel.id,
            expires_at=datetime.utcnow() + timedelta(hours=72),
            is_valid=True
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        
        # Build confirmation URL
        confirmation_url = f"{settings.FRONTEND_URL}/confirm/{token.token}"
        
        # Prepare template context
        context = {
            "layover_id": layover.id,
            "layover_uuid": layover.uuid,
            "hotel_name": hotel.name,
            "origin": layover.origin_station_code or "N/A",
            "destination": layover.destination_station_code or "N/A",
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "check_in_time": layover.check_in_time.strftime("%H:%M"),
            "check_out_date": layover.check_out_date.strftime("%B %d, %Y"),
            "check_out_time": layover.check_out_time.strftime("%H:%M"),
            "crew_count": layover.crew_count,
            "room_breakdown": layover.room_breakdown,
            "special_requirements": layover.special_requirements or "None",
            "transport_required": "Yes" if layover.transport_required else "No",
            "transport_details": layover.transport_details or "N/A",
            "amendment_reason": amendment_reason or "Details updated by operations team",
            "amendment_count": layover.amendment_count,
            "last_amended_at": layover.last_amended_at.strftime("%B %d, %Y at %H:%M") if layover.last_amended_at else "N/A",
            "confirmation_url": confirmation_url,
            "contact_email": settings.SMTP_FROM_EMAIL,
            "airline_name": settings.SMTP_FROM_NAME,
        }
        
        # Email subject
        subject = f"AMENDED: Layover Request #{layover.id} - {context['origin']}→{context['destination']} - {context['check_in_date']}"
        
        # Send email using template
        result = self.email_service.send_templated_email(
            to_email=hotel.email,
            template_name="hotel_amendment.html",
            context=context,
            subject=subject,
            cc_emails=hotel.secondary_emails if hotel.secondary_emails else None,
            layover_id=layover_id,
            notification_type="amendment_notification"
        )
        
        # Log audit trail
        if result.get("success"):
            self.audit_repo.create(
                user_id=None,
                user_role="system",
                action_type="amendment_notified",
                entity_type="layover",
                entity_id=layover_id,
                details={
                    "notification_type": "amendment_notification",
                    "recipient": hotel.email,
                    "hotel_name": hotel.name,
                    "notification_id": result.get("notification_id"),
                    "amendment_count": layover.amendment_count
                }
            )
        
        return result
    
    # ==================== OPS NOTIFICATIONS ====================
    
    def notify_ops_confirmation(
        self,
        layover_id: int,
        hotel_response: Optional[Dict] = None,
    ) -> Dict:
        """
        Notify Ops when hotel confirms booking
        
        Args:
            layover_id: ID of the layover
            hotel_response: Response metadata from hotel
        
        Returns:
            Dict with success status
        """
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        # Get Ops users to notify (creator + station users)
        recipients = []
        
        # Add creator
        if layover.created_by:
            creator = self.user_repo.get_by_id(layover.created_by)
            if creator and creator.email:
                recipients.append(creator.email)
        
        # Add station users
        if layover.station_id:
            station_users = self.user_repo.get_by_station(layover.station_id)
            recipients.extend([u.email for u in station_users if u.email and u.email not in recipients])
        
        if not recipients:
            logger.warning(f"No Ops recipients found for layover {layover_id} confirmation")
            return {"success": False, "message": "No recipients"}
        
        # Prepare context
        context = {
            "app_name": settings.APP_NAME,
            "layover_id": layover.id,
            "hotel_name": layover.hotel.name if layover.hotel else "Unknown",
            "origin_station": layover.origin_station_code,
            "destination_station": layover.destination_station_code,
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "check_in_time": layover.check_in_time.strftime("%I:%M %p"),
            "crew_count": layover.crew_count,
            "confirmation_number": hotel_response.get("confirmation_number") if hotel_response else None,
            "hotel_note": hotel_response.get("note") if hotel_response else None,
            "confirmed_at": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
            "layover_url": f"{settings.FRONTEND_URL}/layovers/{layover.id}",
        }
        
        subject = f"✅ Hotel Confirmed: Request #{layover.id} - {layover.hotel.name}"
        
        # Send to all recipients
        results = []
        for email in recipients:
            result = self.email_service.send_templated_email(
                to_email=email,
                template_name="ops_confirmation.html",
                context=context,
                subject=subject,
                layover_id=layover_id,
                notification_type="ops_confirmation"
            )
            results.append(result)
        
        # Log audit
        self.audit_repo.create(
            user_id=None,
            user_role="system",
            action_type="notification_sent",
            entity_type="layover",
            entity_id=layover_id,
            details={
                "notification_type": "ops_confirmation",
                "recipients": recipients,
                "hotel_name": layover.hotel.name if layover.hotel else None
            }
        )
        
        return {
            "success": all(r["success"] for r in results),
            "message": f"Notifications sent to {len(recipients)} recipient(s)"
        }
    
    def notify_ops_decline(
        self,
        layover_id: int,
        decline_reason: str,
        decline_note: Optional[str] = None,
    ) -> Dict:
        """
        Notify Ops when hotel declines booking
        
        Args:
            layover_id: ID of the layover
            decline_reason: Reason for decline
            decline_note: Additional note from hotel
        
        Returns:
            Dict with success status
        """
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        # Get Ops recipients (same logic as confirmation)
        recipients = []
        if layover.created_by:
            creator = self.user_repo.get_by_id(layover.created_by)
            if creator and creator.email:
                recipients.append(creator.email)
        
        if layover.station_id:
            station_users = self.user_repo.get_by_station(layover.station_id)
            recipients.extend([u.email for u in station_users if u.email and u.email not in recipients])
        
        if not recipients:
            return {"success": False, "message": "No recipients"}
        
        # Map decline reason to friendly text
        reason_map = {
            "fully_booked": "Fully Booked",
            "insufficient_notice": "Insufficient Notice",
            "cannot_meet_requirements": "Cannot Meet Requirements",
            "other": "Other Reason"
        }
        
        context = {
            "app_name": settings.APP_NAME,
            "layover_id": layover.id,
            "hotel_name": layover.hotel.name if layover.hotel else "Unknown",
            "origin_station": layover.origin_station_code,
            "destination_station": layover.destination_station_code,
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "decline_reason": reason_map.get(decline_reason, decline_reason),
            "decline_note": decline_note,
            "declined_at": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
            "layover_url": f"{settings.FRONTEND_URL}/layovers/{layover.id}",
        }
        
        subject = f"❌ Hotel Declined: Request #{layover.id} - {layover.hotel.name}"
        
        # Send notifications
        results = []
        for email in recipients:
            result = self.email_service.send_templated_email(
                to_email=email,
                template_name="ops_decline.html",
                context=context,
                subject=subject,
                layover_id=layover_id,
                notification_type="ops_decline"
            )
            results.append(result)
        
        # Log audit
        self.audit_repo.create(
            user_id=None,
            user_role="system",
            action_type="notification_sent",
            entity_type="layover",
            entity_id=layover_id,
            details={
                "notification_type": "ops_decline",
                "recipients": recipients,
                "decline_reason": decline_reason
            }
        )
        
        return {
            "success": all(r["success"] for r in results),
            "message": f"Decline notifications sent to {len(recipients)} recipient(s)"
        }
    
    def notify_ops_changes_requested(
        self,
        layover_id: int,
        change_types: List[str],
        change_note: str,
    ) -> Dict:
        """
        Notify Ops when hotel requests changes
        
        Args:
            layover_id: ID of the layover
            change_types: Types of changes requested
            change_note: Note from hotel explaining changes
        
        Returns:
            Dict with success status
        """
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        # Get recipients
        recipients = []
        if layover.created_by:
            creator = self.user_repo.get_by_id(layover.created_by)
            if creator and creator.email:
                recipients.append(creator.email)
        
        if layover.station_id:
            station_users = self.user_repo.get_by_station(layover.station_id)
            recipients.extend([u.email for u in station_users if u.email and u.email not in recipients])
        
        if not recipients:
            return {"success": False, "message": "No recipients"}
        
        context = {
            "app_name": settings.APP_NAME,
            "layover_id": layover.id,
            "hotel_name": layover.hotel.name if layover.hotel else "Unknown",
            "origin_station": layover.origin_station_code,
            "destination_station": layover.destination_station_code,
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "change_types": change_types,
            "change_note": change_note,
            "requested_at": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC"),
            "layover_url": f"{settings.FRONTEND_URL}/layovers/{layover.id}",
        }
        
        subject = f"⚠️ Hotel Requests Changes: Request #{layover.id} - {layover.hotel.name}"
        
        # Send notifications
        results = []
        for email in recipients:
            result = self.email_service.send_templated_email(
                to_email=email,
                template_name="ops_changes_requested.html",
                context=context,
                subject=subject,
                layover_id=layover_id,
                notification_type="ops_changes_requested"
            )
            results.append(result)
        
        # Log audit
        self.audit_repo.create(
            user_id=None,
            user_role="system",
            action_type="notification_sent",
            entity_type="layover",
            entity_id=layover_id,
            details={
                "notification_type": "ops_changes_requested",
                "recipients": recipients,
                "change_types": change_types
            }
        )
        
        return {
            "success": all(r["success"] for r in results),
            "message": f"Change request notifications sent to {len(recipients)} recipient(s)"
        }    
    # ==================== CREW NOTIFICATIONS ====================
    
    def send_crew_notification(
        self,
        layover_id: int,
        crew_member_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        Send layover details notification to crew members.
        
        Called when layover is finalized. Notifies assigned crew about
        hotel details, transport, check-in times, etc.
        
        Args:
            layover_id: ID of the layover
            crew_member_ids: Optional list of specific crew IDs (None = all assigned crew)
        
        Returns:
            Dict with success status and notification_ids
        
        Raises:
            BusinessRuleException: If layover not found or no crew assigned
        """
        # Get layover with relations
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        if not layover.hotel:
            raise BusinessRuleException("Hotel not assigned to layover")
        
        hotel = layover.hotel
        station = layover.station
        
        # Get assigned crew
        from app.repositories.layover_crew_repository import LayoverCrewRepository
        layover_crew_repo = LayoverCrewRepository(self.db)
        
        crew_assignments = layover_crew_repo.get_by_layover_id(layover_id, load_relations=True)
        
        if not crew_assignments:
            raise BusinessRuleException("No crew assigned to this layover")
        
        # Filter by specific crew_member_ids if provided
        if crew_member_ids:
            crew_assignments = [
                ca for ca in crew_assignments 
                if ca.crew_member_id in crew_member_ids
            ]
        
        if not crew_assignments:
            raise BusinessRuleException("No valid crew members to notify")
        
        # Calculate layover duration
        from datetime import datetime, timedelta
        checkin_dt = datetime.combine(layover.check_in_date, layover.check_in_time)
        checkout_dt = datetime.combine(layover.check_out_date, layover.check_out_time)
        duration_hours = int((checkout_dt - checkin_dt).total_seconds() / 3600)
        
        # Get primary contact
        primary_contact = layover_crew_repo.get_primary_contact(layover_id)
        primary_contact_name = None
        if primary_contact and primary_contact.crew_member:
            primary_contact_name = primary_contact.crew_member.full_name
        
        # Prepare hotel address/map link
        hotel_address = f"{hotel.address}, {station.name}"
        hotel_map_url = f"https://maps.google.com/?q={hotel.name.replace(' ', '+')},{station.name.replace(' ', '+')}"
        
        results = []
        
        for assignment in crew_assignments:
            crew_member = assignment.crew_member
            
            if not crew_member.email:
                logger.warning(f"Crew member {crew_member.id} has no email address")
                continue
            
            # Prepare context for this crew member
            context = {
                "crew_member_name": crew_member.full_name,
                "crew_rank": crew_member.crew_rank.value.replace("_", " ").title(),
                "layover_id": layover.id,
                "layover_uuid": layover.uuid,
                
                # Flight details
                "origin": layover.origin_station_code,
                "destination": layover.destination_station_code,
                "flight_number": layover.operational_flight_number,
                "layover_reason": layover.layover_reason.value.replace("_", " ").title(),
                
                # Dates & Times
                "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
                "check_in_time": layover.check_in_time.strftime("%H:%M"),
                "check_out_date": layover.check_out_date.strftime("%B %d, %Y"),
                "check_out_time": layover.check_out_time.strftime("%H:%M"),
                "duration_hours": duration_hours,
                
                # Hotel details
                "hotel_name": hotel.name,
                "hotel_address": hotel_address,
                "hotel_phone": hotel.phone,
                "hotel_email": hotel.email if hotel.email else "N/A",
                "hotel_map_url": hotel_map_url,
                
                # Room assignment
                "room_number": assignment.room_number if assignment.room_number else "TBA",
                "room_type": assignment.room_type.replace("_", " ").title() if assignment.room_type else "TBA",
                
                # Transport
                "transport_required": layover.transport_required,
                "transport_details": layover.transport_details if layover.transport_details else "N/A",
                
                # Special requirements
                "special_requirements": layover.special_requirements if layover.special_requirements else "None",
                
                # Primary contact
                "primary_contact_name": primary_contact_name if primary_contact_name else "TBA",
                
                # Station
                "station_name": station.name,
                "station_contact_email": station.contact_email,
                "station_contact_phone": station.contact_phone,
                
                # App info
                "app_name": "Qanot Sharq Airlines - Crew Layover Management",
                "support_email": "operations@qanotsharq.uz",
            }
            
            try:
                # Send email
                result = self.email_service.send_templated_email(
                    to=crew_member.email,
                    template_name="crew_notification.html",
                    subject=f"Layover Details: {layover.origin_station_code} → {layover.destination_station_code} - {layover.check_in_date.strftime('%b %d')}",
                    context=context
                )
                
                results.append({"crew_member_id": crew_member.id, "success": result["success"]})
                
                # Update notification status
                from app.models.layover_crew import NotificationStatus
                assignment.notification_status = NotificationStatus.SENT
                assignment.notified_at = datetime.utcnow()
                layover_crew_repo.update(assignment)
                
            except Exception as e:
                logger.error(f"Failed to send crew notification to {crew_member.email}: {e}")
                results.append({"crew_member_id": crew_member.id, "success": False, "error": str(e)})
        
        # Log audit
        self.audit_repo.log(
            user_id=None,  # System action
            action="crew_notified",
            entity_type="layover",
            entity_id=layover_id,
            details={
                "crew_member_ids": [r["crew_member_id"] for r in results],
                "success_count": sum(1 for r in results if r["success"]),
                "failure_count": sum(1 for r in results if not r["success"])
            }
        )
        
        return {
            "success": all(r["success"] for r in results),
            "message": f"Crew notifications sent to {len(results)} crew member(s)",
            "results": results
        }
    
    # ==================== ESCALATION NOTIFICATIONS ====================
    
    def send_escalation_alert(
        self,
        layover_id: int,
    ) -> Dict:
        """
        Send escalation alert to supervisors/managers.
        
        Called when a layover has been pending for too long without
        hotel response. Alerts management to take manual action.
        
        Args:
            layover_id: ID of the layover
        
        Returns:
            Dict with success status and notification_ids
        
        Raises:
            BusinessRuleException: If layover not found
        """
        # Get layover with relations
        layover = self.layover_repo.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise BusinessRuleException("Layover not found")
        
        if not layover.hotel:
            raise BusinessRuleException("Hotel not assigned to layover")
        
        hotel = layover.hotel
        station = layover.station
        
        # Calculate how long pending
        from datetime import datetime, timedelta
        if not layover.sent_at:
            raise BusinessRuleException("Layover has not been sent to hotel yet")
        
        pending_duration = datetime.utcnow() - layover.sent_at
        pending_hours = int(pending_duration.total_seconds() / 3600)
        
        # Get supervisors and ops coordinators
        supervisors = self.user_repo.get_by_role("supervisor")
        ops_coordinators = self.user_repo.get_by_role("ops_coordinator")
        admins = self.user_repo.get_by_role("admin")
        
        recipients = list(set(supervisors + ops_coordinators + admins))
        
        if not recipients:
            raise BusinessRuleException("No supervisors/managers found to escalate to")
        
        # Get creator details
        creator = None
        if layover.created_by:
            creator = self.user_repo.get_by_id(layover.created_by)
        
        # Prepare context
        context = {
            "layover_id": layover.id,
            "layover_uuid": layover.uuid,
            
            # Flight details
            "origin": layover.origin_station_code,
            "destination": layover.destination_station_code,
            "flight_number": layover.operational_flight_number,
            "crew_count": layover.crew_count,
            
            # Dates & Times
            "check_in_date": layover.check_in_date.strftime("%B %d, %Y"),
            "check_in_time": layover.check_in_time.strftime("%H:%M"),
            
            # Hotel details
            "hotel_name": hotel.name,
            "hotel_contact_email": hotel.email,
            "hotel_contact_phone": hotel.phone,
            "hotel_whatsapp": hotel.whatsapp if hotel.whatsapp else "N/A",
            
            # Station
            "station_name": station.name,
            
            # Escalation details
            "sent_at": layover.sent_at.strftime("%B %d, %Y at %H:%M UTC"),
            "pending_hours": pending_hours,
            "reminder_count": layover.reminder_count,
            "last_reminder_sent": layover.last_reminder_sent_at.strftime("%B %d, %Y at %H:%M UTC") if layover.last_reminder_sent_at else "Never",
            
            # Creator
            "created_by_name": f"{creator.first_name} {creator.last_name}" if creator else "Unknown",
            "created_by_email": creator.email if creator else "N/A",
            
            # Action URL
            "layover_detail_url": f"{settings.FRONTEND_URL}/layovers/{layover.id}",
            
            # App info
            "app_name": "Qanot Sharq Airlines - Crew Layover Management",
            "support_email": "operations@qanotsharq.uz",
        }
        
        results = []
        
        for recipient in recipients:
            try:
                context["recipient_name"] = f"{recipient.first_name} {recipient.last_name}"
                
                # Send email
                result = self.email_service.send_templated_email(
                    to=recipient.email,
                    template_name="escalation_alert.html",
                    subject=f"🚨 ESCALATION: Layover #{layover.id} - No Hotel Response ({pending_hours}h)",
                    context=context
                )
                
                results.append({"user_id": recipient.id, "success": result["success"]})
                
            except Exception as e:
                logger.error(f"Failed to send escalation alert to {recipient.email}: {e}")
                results.append({"user_id": recipient.id, "success": False, "error": str(e)})
        
        # Log audit
        self.audit_repo.log(
            user_id=None,  # System action
            action="layover_escalated",
            entity_type="layover",
            entity_id=layover_id,
            details={
                "pending_hours": pending_hours,
                "recipients": [r["user_id"] for r in results],
                "success_count": sum(1 for r in results if r["success"]),
                "failure_count": sum(1 for r in results if not r["success"])
            }
        )
        
        return {
            "success": all(r["success"] for r in results),
            "message": f"Escalation alerts sent to {len(results)} recipient(s)",
            "results": results
        }
