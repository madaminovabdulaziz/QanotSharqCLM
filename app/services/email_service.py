"""
Email Service
Handles SMTP email sending with template rendering and delivery tracking
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.notification_repository import NotificationRepository
from app.core.exceptions import BusinessRuleException

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service for sending emails via SMTP
    
    Features:
    - Template rendering with Jinja2
    - SMTP connection with TLS
    - Delivery tracking
    - Error handling and logging
    - Plain text fallback
    """
    
    def __init__(self, db: Session):
        """
        Initialize email service
        
        Args:
            db: Database session for logging notifications
        """
        self.db = db
        self.notification_repo = NotificationRepository(db)
        
        # Setup Jinja2 template environment
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        template_dir.mkdir(parents=True, exist_ok=True)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Validate SMTP configuration
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.warning("SMTP not configured - emails will be logged but not sent")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        layover_id: Optional[int] = None,
        user_id: Optional[int] = None,
        notification_type: str = "email",
    ) -> Dict:
        """
        Send an email via SMTP
        
        Args:
            to_email: Primary recipient email
            subject: Email subject line
            html_body: HTML email body
            text_body: Plain text email body (fallback)
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            layover_id: Associated layover ID (for tracking)
            user_id: Associated user ID (for tracking)
            notification_type: Type of notification (for logging)
        
        Returns:
            Dict with success status and message
        
        Raises:
            BusinessRuleException: If email sending fails critically
        """
        # Create notification record
        notification = self.notification_repo.create(
            layover_id=layover_id,
            user_id=user_id,
            notification_type=notification_type,
            recipient_email=to_email,
            channel="email",
            subject=subject,
            body_html=html_body,
            body_text=text_body or self._html_to_text(html_body),
            status="pending"
        )
        
        try:
            # Build MIME message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Attach plain text version
            text_part = MIMEText(text_body or self._html_to_text(html_body), 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Attach HTML version
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Prepare recipient list
            recipients = [to_email]
            if cc_emails:
                recipients.extend(cc_emails)
            if bcc_emails:
                recipients.extend(bcc_emails)
            
            # Send via SMTP
            if settings.SMTP_HOST and settings.SMTP_USER:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    if settings.SMTP_TLS:
                        server.starttls()
                    
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(
                        settings.SMTP_FROM_EMAIL,
                        recipients,
                        msg.as_string()
                    )
                
                # Update notification status
                self.notification_repo.update(
                    notification.id,
                    status="sent",
                    sent_at=datetime.utcnow()
                )
                
                logger.info(f"Email sent successfully to {to_email} - Notification ID: {notification.id}")
                
                return {
                    "success": True,
                    "message": "Email sent successfully",
                    "notification_id": notification.id
                }
            else:
                # SMTP not configured - log only
                logger.warning(f"SMTP not configured - Email to {to_email} logged but not sent")
                
                self.notification_repo.update(
                    notification.id,
                    status="failed",
                    error_message="SMTP not configured",
                    failed_at=datetime.utcnow()
                )
                
                return {
                    "success": False,
                    "message": "SMTP not configured",
                    "notification_id": notification.id
                }
        
        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {str(e)}"
            logger.error(error_msg)
            
            self.notification_repo.update(
                notification.id,
                status="failed",
                error_message=error_msg,
                failed_at=datetime.utcnow()
            )
            
            raise BusinessRuleException(error_msg)
        
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            
            self.notification_repo.update(
                notification.id,
                status="failed",
                error_message=error_msg,
                failed_at=datetime.utcnow(),
                retry_count=notification.retry_count + 1
            )
            
            return {
                "success": False,
                "message": error_msg,
                "notification_id": notification.id
            }
        
        except Exception as e:
            error_msg = f"Unexpected error sending email: {str(e)}"
            logger.error(error_msg)
            
            self.notification_repo.update(
                notification.id,
                status="failed",
                error_message=error_msg,
                failed_at=datetime.utcnow()
            )
            
            return {
                "success": False,
                "message": error_msg,
                "notification_id": notification.id
            }
    
    def render_template(
        self,
        template_name: str,
        context: Dict,
    ) -> Tuple[str, str]:
        """
        Render email template to HTML and plain text
        
        Args:
            template_name: Name of the template file (e.g., 'hotel_request.html')
            context: Template context variables
        
        Returns:
            Tuple of (html_body, text_body)
        
        Raises:
            TemplateNotFound: If template doesn't exist
        """
        try:
            template = self.jinja_env.get_template(template_name)
            html_body = template.render(**context)
            
            # Generate plain text version
            text_body = self._html_to_text(html_body)
            
            return html_body, text_body
        
        except TemplateNotFound:
            logger.error(f"Email template not found: {template_name}")
            raise
    
    def send_templated_email(
        self,
        to_email: str,
        template_name: str,
        context: Dict,
        subject: str,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        layover_id: Optional[int] = None,
        user_id: Optional[int] = None,
        notification_type: str = "email",
    ) -> Dict:
        """
        Render template and send email in one call
        
        Args:
            to_email: Recipient email
            template_name: Jinja2 template filename
            context: Template context variables
            subject: Email subject
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            layover_id: Associated layover ID
            user_id: Associated user ID
            notification_type: Notification type for logging
        
        Returns:
            Dict with success status and message
        """
        try:
            html_body, text_body = self.render_template(template_name, context)
            
            return self.send_email(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                layover_id=layover_id,
                user_id=user_id,
                notification_type=notification_type
            )
        
        except Exception as e:
            logger.error(f"Failed to send templated email: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def _html_to_text(self, html: str) -> str:
        """
        Convert HTML to plain text (simple version)
        
        Args:
            html: HTML string
        
        Returns:
            Plain text version
        """
        # Simple HTML stripping - in production, use html2text or similar
        import re
        
        # Remove HTML tags
        text = re.sub('<[^<]+?>', '', html)
        
        # Replace multiple spaces/newlines with single
        text = re.sub(r'\s+', ' ', text)
        
        # Trim
        text = text.strip()
        
        return text
    
    def test_smtp_connection(self) -> Dict:
        """
        Test SMTP connection and authentication
        
        Returns:
            Dict with connection status
        """
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            return {
                "success": False,
                "message": "SMTP not configured"
            }
        
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                
                return {
                    "success": True,
                    "message": "SMTP connection successful"
                }
        
        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "message": "SMTP authentication failed - check credentials"
            }
        
        except smtplib.SMTPException as e:
            return {
                "success": False,
                "message": f"SMTP error: {str(e)}"
            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }