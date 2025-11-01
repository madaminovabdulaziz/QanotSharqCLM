# """
# Notification Service
# Handles all outbound communications (email, WhatsApp, SMS)
# """

# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from typing import Optional, Dict, List
# from datetime import datetime, timedelta
# from jinja2 import Environment, FileSystemLoader, select_autoescape
# from pathlib import Path
# from sqlalchemy.orm import Session

# from app.repositories.notification_repository import NotificationRepository
# from app.repositories.layover_repository import LayoverRepository
# from app.repositories.audit_repository import AuditRepository
# from app.core.config import settings


# class NotificationService:
#     """Service for sending notifications via email, WhatsApp, SMS"""

#     def __init__(self, db: Session):
#         self.db = db
#         self.notification_repo = NotificationRepository(db)
#         self.layover_repo = LayoverRepository(db)
#         self.audit_repo = AuditRepository(db)
        
#         # Setup Jinja2 template environment
#         template_dir = Path(__file__).parent.parent / "templates" / "emails"
#         self.jinja_env = Environment(
#             loader=FileSystemLoader(str(template_dir)),
#             autoescape=select_autoescape(['html', 'xml'])
#         )

#     def _render_template(
#         self,
#         template_name: str,
#         context: Dict,
#     ) -> tuple[str, str]:
#         """
#         Render email template to HTML and plain text
        
#         Args:
#             template_name: Name of the template file (e.g., 'hotel_request.html')
#             context: Template context variables
        
#         Returns:
#             Tuple of (html_body, text_body)
#         """
#         template = self.jinja_env.get_template(template_name)
#         html_body = template.render(**context)
        
#         # Simple text conversion (strip HTML tags for plain text version)
#         # In production, you might want a more sophisticated text renderer
#         text_body = html_body  # Fallback to HTML if no text template
        
#         return html_body, text_body

#     def _send_email(
#         self,
#         to_email: str,
#         subject: str,
#         html_body: str,
#         text_body: str,
#     ) -> tuple[bool, Optional[str]]:
#         """
#         Send email via SMTP
        
#         Args:
#             to_email: Recipient email address
#             subject: Email subject
#             html_body: HTML email body
#             text_body: Plain text email body
        
#         Returns:
#             Tuple of (success: bool, message_id: Optional[str])
#         """
#         try:
#             # Create message
#             msg = MIMEMultipart('alternative')
#             msg['From'] = settings.SMTP_FROM_EMAIL
#             msg['To'] = to_email
#             msg['Subject'] = subject
            
#             # Attach both plain text and HTML versions
#             part_text = MIMEText(text_body, 'plain', 'utf-8')
#             part_html = MIMEText(html_body, 'html', 'utf-8')
            
#             msg.attach(part_text)
#             msg.attach(part_html)
            
#             # Send via SMTP
#             with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
#                 if settings.SMTP_TLS:
#                     server.starttls()
#                 if settings.SMTP_USER and settings.SMTP_PASSWORD:
#                     server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                
#                 server.send_message(msg)
            
#             # Return success with a generated message ID
#             message_id = msg['Message-ID'] if 'Message-ID' in msg else None
#             return True, message_id
            
#         except Exception as e:
#             print(f"Email send failed: {str(e)}")
#             return False, None

#     def send_hotel_request(
#         self,
#         layover_id: int,
#         confirmation_token: str,
#     ) -> Dict:
#         """
#         Send initial hotel confirmation request email
        
#         Args:
#             layover_id: ID of the layover
#             confirmation_token: Confirmation token (UUID)
        
#         Returns:
#             Dict with success status and notification_id
#         """
#         # Get layover with relations
#         layover = self.layover_repo.get_by_id(layover_id)
#         if not layover:
#             raise ValueError("Layover not found")

#         hotel = layover.hotel
#         station = layover.station
        
#         # Calculate duration
#         duration_hours = int(
#             (
#                 datetime.combine(layover.check_out_date, layover.check_out_time)
#                 - datetime.combine(layover.check_in_date, layover.check_in_time)
#             ).total_seconds() / 3600
#         )
        
#         # Build confirmation URL
#         confirmation_url = f"{settings.FRONTEND_URL}/api/confirm/{confirmation_token}"
        
#         # Prepare template context
#         context = {
#             "layover": layover,
#             "hotel": hotel,
#             "station": station,
#             "duration_hours": duration_hours,
#             "confirmation_url": confirmation_url,
#             "token_expires_at": datetime.utcnow() + timedelta(hours=72),
#         }
        
#         # Render template
#         html_body, text_body = self._render_template("hotel_request.html", context)
        
#         # Subject line
#         subject = f"Layover Request - {layover.origin_station_code}→{layover.destination_station_code} - {layover.check_in_date.strftime('%b %d, %Y')}"
        
#         # Create notification record
#         notification = self.notification_repo.create(
#             layover_id=layover_id,
#             user_id=None,
#             notification_type="hotel_request",
#             recipient_email=hotel.email,
#             recipient_phone=None,
#             channel="email",
#             subject=subject,
#             body_text=text_body,
#             body_html=html_body,
#             template_name="hotel_request.html",
#         )
        
#         # Send email
#         success, external_id = self._send_email(
#             to_email=hotel.email,
#             subject=subject,
#             html_body=html_body,
#             text_body=text_body,
#         )
        
#         # Update notification status
#         if success:
#             self.notification_repo.mark_as_sent(notification.id, external_id)
            
#             # Audit log
#             self.audit_repo.create(
#                 user_id=None,
#                 user_role="system",
#                 action_type="email_sent",
#                 entity_type="layover",
#                 entity_id=layover_id,
#                 details={
#                     "notification_type": "hotel_request",
#                     "recipient": hotel.email,
#                     "notification_id": notification.id,
#                 },
#             )
            
#             return {
#                 "success": True,
#                 "notification_id": notification.id,
#                 "message": "Hotel request email sent successfully",
#             }
#         else:
#             self.notification_repo.mark_as_failed(
#                 notification.id,
#                 "SMTP send failed"
#             )
            
#             return {
#                 "success": False,
#                 "notification_id": notification.id,
#                 "message": "Failed to send email",
#             }

#     def send_hotel_reminder(
#         self,
#         layover_id: int,
#         confirmation_token: str,
#         reminder_number: int = 1,
#     ) -> Dict:
#         """
#         Send reminder email to hotel
        
#         Args:
#             layover_id: ID of the layover
#             confirmation_token: Confirmation token (UUID)
#             reminder_number: Which reminder (1, 2, etc.)
        
#         Returns:
#             Dict with success status
#         """
#         layover = self.layover_repo.get_by_id(layover_id)
#         if not layover:
#             raise ValueError("Layover not found")

#         hotel = layover.hotel
        
#         # Calculate hours elapsed
#         hours_elapsed = int(
#             (datetime.utcnow() - layover.sent_at).total_seconds() / 3600
#         ) if layover.sent_at else 0
        
#         # Build confirmation URL
#         confirmation_url = f"{settings.FRONTEND_URL}/api/confirm/{confirmation_token}"
        
#         # Prepare context
#         context = {
#             "layover": layover,
#             "hotel": hotel,
#             "confirmation_url": confirmation_url,
#             "reminder_number": reminder_number,
#             "hours_elapsed": hours_elapsed,
#         }
        
#         # Render template
#         html_body, text_body = self._render_template("hotel_reminder.html", context)
        
#         # Subject
#         subject = f"REMINDER #{reminder_number}: Layover Request #{layover.id} - Response Needed"
        
#         # Create notification
#         notification = self.notification_repo.create(
#             layover_id=layover_id,
#             user_id=None,
#             notification_type="hotel_reminder",
#             recipient_email=hotel.email,
#             recipient_phone=None,
#             channel="email",
#             subject=subject,
#             body_text=text_body,
#             body_html=html_body,
#             template_name="hotel_reminder.html",
#         )
        
#         # Send email
#         success, external_id = self._send_email(
#             to_email=hotel.email,
#             subject=subject,
#             html_body=html_body,
#             text_body=text_body,
#         )
        
#         if success:
#             self.notification_repo.mark_as_sent(notification.id, external_id)
#             return {"success": True, "notification_id": notification.id}
#         else:
#             self.notification_repo.mark_as_failed(notification.id, "SMTP send failed")
#             return {"success": False, "notification_id": notification.id}

#     def notify_ops_confirmation(
#         self,
#         layover_id: int,
#         recipient_user_id: int,
#     ) -> Dict:
#         """
#         Notify Ops coordinator that hotel confirmed
        
#         Args:
#             layover_id: ID of the layover
#             recipient_user_id: ID of Ops user to notify
        
#         Returns:
#             Dict with success status
#         """
#         layover = self.layover_repo.get_by_id(layover_id)
#         if not layover:
#             raise ValueError("Layover not found")

#         # Get recipient user
#         from app.repositories.user_repository import UserRepository
#         user_repo = UserRepository(self.db)
#         recipient = user_repo.get_by_id(recipient_user_id)
        
#         if not recipient:
#             raise ValueError("Recipient user not found")

#         hotel = layover.hotel
#         station = layover.station
        
#         # Calculate response time
#         response_time_hours = 0
#         if layover.sent_at and layover.confirmed_at:
#             response_time_hours = int(
#                 (layover.confirmed_at - layover.sent_at).total_seconds() / 3600
#             )
        
#         # Prepare context
#         context = {
#             "layover": layover,
#             "hotel": hotel,
#             "station": station,
#             "recipient_name": f"{recipient.first_name} {recipient.last_name}",
#             "response_time_hours": response_time_hours,
#             "layover_detail_url": f"{settings.FRONTEND_URL}/layovers/{layover.id}",
#         }
        
#         # Render template
#         html_body, text_body = self._render_template("ops_confirmation.html", context)
        
#         # Subject
#         subject = f"✅ Hotel Confirmed: Request #{layover.id} - {hotel.name}"
        
#         # Create notification
#         notification = self.notification_repo.create(
#             layover_id=layover_id,
#             user_id=recipient_user_id,
#             notification_type="ops_confirmation",
#             recipient_email=recipient.email,
#             recipient_phone=None,
#             channel="email",
#             subject=subject,
#             body_text=text_body,
#             body_html=html_body,
#             template_name="ops_confirmation.html",
#         )
        
#         # Send email
#         success, external_id = self._send_email(
#             to_email=recipient.email,
#             subject=subject,
#             html_body=html_body,
#             text_body=text_body,
#         )
        
#         if success:
#             self.notification_repo.mark_as_sent(notification.id, external_id)
#             return {"success": True, "notification_id": notification.id}
#         else:
#             self.notification_repo.mark_as_failed(notification.id, "SMTP send failed")
#             return {"success": False, "notification_id": notification.id}

#     def notify_ops_decline(
#         self,
#         layover_id: int,
#         recipient_user_id: int,
#     ) -> Dict:
#         """
#         Notify Ops coordinator that hotel declined
        
#         Args:
#             layover_id: ID of the layover
#             recipient_user_id: ID of Ops user to notify
        
#         Returns:
#             Dict with success status
#         """
#         layover = self.layover_repo.get_by_id(layover_id)
#         if not layover:
#             raise ValueError("Layover not found")

#         from app.repositories.user_repository import UserRepository
#         user_repo = UserRepository(self.db)
#         recipient = user_repo.get_by_id(recipient_user_id)
        
#         if not recipient:
#             raise ValueError("Recipient user not found")

#         hotel = layover.hotel
#         station = layover.station
        
#         # Calculate response time
#         response_time_hours = 0
#         if layover.sent_at and layover.declined_at:
#             response_time_hours = int(
#                 (layover.declined_at - layover.sent_at).total_seconds() / 3600
#             )
        
#         # Prepare context
#         context = {
#             "layover": layover,
#             "hotel": hotel,
#             "station": station,
#             "recipient_name": f"{recipient.first_name} {recipient.last_name}",
#             "response_time_hours": response_time_hours,
#             "layover_detail_url": f"{settings.FRONTEND_URL}/layovers/{layover.id}",
#         }
        
#         # Render template
#         html_body, text_body = self._render_template("ops_decline.html", context)
        
#         # Subject
#         subject = f"❌ Hotel Declined: Request #{layover.id} - {hotel.name}"
        
#         # Create notification
#         notification = self.notification_repo.create(
#             layover_id=layover_id,
#             user_id=recipient_user_id,
#             notification_type="ops_decline",
#             recipient_email=recipient.email,
#             recipient_phone=None,
#             channel="email",
#             subject=subject,
#             body_text=text_body,
#             body_html=html_body,
#             template_name="ops_decline.html",
#         )
        
#         # Send email
#         success, external_id = self._send_email(
#             to_email=recipient.email,
#             subject=subject,
#             html_body=html_body,
#             text_body=text_body,
#         )
        
#         if success:
#             self.notification_repo.mark_as_sent(notification.id, external_id)
#             return {"success": True, "notification_id": notification.id}
#         else:
#             self.notification_repo.mark_as_failed(notification.id, "SMTP send failed")
#             return {"success": False, "notification_id": notification.id}

#     def send_crew_notification(
#         self,
#         layover_id: int,
#         crew_member_id: int,
#         crew_portal_token: Optional[str] = None,
#     ) -> Dict:
#         """
#         Send layover details to crew member
        
#         Args:
#             layover_id: ID of the layover
#             crew_member_id: ID of crew member
#             crew_portal_token: Optional crew portal access token
        
#         Returns:
#             Dict with success status
#         """
#         layover = self.layover_repo.get_by_id(layover_id)
#         if not layover:
#             raise ValueError("Layover not found")

#         # Get crew member
#         from app.repositories.crew_repository import CrewRepository
#         crew_repo = CrewRepository(self.db)
#         crew_member = crew_repo.get_by_id(crew_member_id)
        
#         if not crew_member or not crew_member.email:
#             raise ValueError("Crew member not found or has no email")

#         hotel = layover.hotel
#         station = layover.station
        
#         # Build crew portal URL
#         crew_portal_url = None
#         if crew_portal_token:
#             crew_portal_url = f"{settings.FRONTEND_URL}/crew/portal/{crew_portal_token}"
        
#         # Get room details (if assigned)
#         room_details = None
#         # TODO: Query layover_crew table for room assignment
        
#         # Generate calendar data (iCal format)
#         calendar_data = self._generate_ical_data(layover, hotel, station)
        
#         # Prepare context
#         context = {
#             "layover": layover,
#             "hotel": hotel,
#             "station": station,
#             "crew_member_name": f"{crew_member.first_name} {crew_member.last_name}",
#             "room_details": room_details,
#             "crew_portal_url": crew_portal_url,
#             "calendar_data": calendar_data,
#         }
        
#         # Render template
#         html_body, text_body = self._render_template("crew_notification.html", context)
        
#         # Subject
#         subject = f"Your Layover: {layover.origin_station_code}→{layover.destination_station_code} - {layover.check_in_date.strftime('%b %d')}"
        
#         # Create notification
#         notification = self.notification_repo.create(
#             layover_id=layover_id,
#             user_id=None,  # Crew may not have user accounts
#             notification_type="crew_notification",
#             recipient_email=crew_member.email,
#             recipient_phone=crew_member.phone,
#             channel="email",
#             subject=subject,
#             body_text=text_body,
#             body_html=html_body,
#             template_name="crew_notification.html",
#         )
        
#         # Send email
#         success, external_id = self._send_email(
#             to_email=crew_member.email,
#             subject=subject,
#             html_body=html_body,
#             text_body=text_body,
#         )
        
#         if success:
#             self.notification_repo.mark_as_sent(notification.id, external_id)
#             return {"success": True, "notification_id": notification.id}
#         else:
#             self.notification_repo.mark_as_failed(notification.id, "SMTP send failed")
#             return {"success": False, "notification_id": notification.id}

#     def _generate_ical_data(self, layover, hotel, station) -> str:
#         """
#         Generate iCal format data for calendar import
        
#         Args:
#             layover: Layover object
#             hotel: Hotel object
#             station: Station object
        
#         Returns:
#             iCal formatted string (URL encoded)
#         """
#         # Simple iCal generation (in production, use icalendar library)
#         ical = f"""BEGIN:VCALENDAR
# VERSION:2.0
# PRODID:-//Airline//Layover System//EN
# BEGIN:VEVENT
# UID:{layover.uuid}@airline.com
# DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}
# DTSTART:{datetime.combine(layover.check_in_date, layover.check_in_time).strftime('%Y%m%dT%H%M%S')}
# DTEND:{datetime.combine(layover.check_out_date, layover.check_out_time).strftime('%Y%m%dT%H%M%S')}
# SUMMARY:Layover - {hotel.name}
# LOCATION:{hotel.address}, {hotel.city}
# DESCRIPTION:Layover at {station.name}. Hotel: {hotel.name}. Confirmation: {layover.hotel_confirmation_number or 'TBD'}
# END:VEVENT
# END:VCALENDAR"""
        
#         # URL encode for data URI
#         import urllib.parse
#         return urllib.parse.quote(ical)