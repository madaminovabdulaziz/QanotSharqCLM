"""
Scheduler Service - Background job scheduling for automated reminders and escalations
Uses APScheduler for reliable task scheduling
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.models.layover import Layover, LayoverStatus
from app.repositories.layover_repository import LayoverRepository
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Service for managing background scheduled tasks.

    Handles:
    - Automated reminders (12h, 24h after sending)
    - Escalation (36h after sending with no response)
    - Respects reminders_paused flag
    - Station-specific timing configurations
    """

    def __init__(self):
        """Initialize scheduler service"""
        self.scheduler = BackgroundScheduler()

        # Create engine for scheduler's own DB connection
        # Note: Scheduler runs in separate threads, needs its own sessions
        self.engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info("Scheduler service initialized")

    def start(self):
        """Start the scheduler"""
        if self.scheduler.running:
            logger.warning("Scheduler is already running")
            return

        # Add jobs
        self._add_reminder_job()
        self._add_escalation_job()

        # Start scheduler
        self.scheduler.start()
        logger.info("✅ Scheduler started successfully")

    def shutdown(self):
        """Shutdown the scheduler gracefully"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down")

    def _get_db_session(self) -> Session:
        """Get a new database session for scheduler jobs"""
        return self.SessionLocal()

    # ==================== JOB REGISTRATION ====================

    def _add_reminder_job(self):
        """
        Add reminder job to scheduler.

        Runs every 5 minutes to check for layovers needing reminders.
        """
        self.scheduler.add_job(
            func=self.process_reminders,
            trigger=IntervalTrigger(minutes=5),
            id="reminder_job",
            name="Process Layover Reminders",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping executions
        )
        logger.info("✅ Reminder job registered (runs every 5 minutes)")

    def _add_escalation_job(self):
        """
        Add escalation job to scheduler.

        Runs every 10 minutes to check for layovers needing escalation.
        """
        self.scheduler.add_job(
            func=self.process_escalations,
            trigger=IntervalTrigger(minutes=10),
            id="escalation_job",
            name="Process Layover Escalations",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping executions
        )
        logger.info("✅ Escalation job registered (runs every 10 minutes)")

    # ==================== REMINDER PROCESSING ====================

    def process_reminders(self):
        """
        Process pending layovers and send reminders if needed.

        Logic:
        - Check all layovers with status=PENDING
        - Skip if reminders_paused=True
        - Send first reminder at 12h
        - Send second reminder at 24h
        - Log all actions
        """
        db = self._get_db_session()

        try:
            logger.info("🔔 Starting reminder processing...")

            layover_repo = LayoverRepository(db)
            notification_service = NotificationService(db)

            # Get all pending layovers
            pending_layovers = layover_repo.get_by_status(LayoverStatus.PENDING)

            logger.info(f"Found {len(pending_layovers)} pending layovers")

            reminders_sent = 0

            for layover in pending_layovers:
                try:
                    # Skip if reminders paused
                    if layover.reminders_paused:
                        logger.debug(f"Layover {layover.id}: Reminders paused, skipping")
                        continue

                    # Skip if no sent_at timestamp
                    if not layover.sent_at:
                        logger.warning(f"Layover {layover.id}: Status is PENDING but no sent_at timestamp")
                        continue

                    # Calculate time since sent
                    time_since_sent = datetime.utcnow() - layover.sent_at
                    hours_since_sent = time_since_sent.total_seconds() / 3600

                    # Determine if reminder is needed
                    should_send_reminder = False
                    reminder_type = None

                    if layover.reminder_count == 0 and hours_since_sent >= 12:
                        # First reminder at 12h
                        should_send_reminder = True
                        reminder_type = "first"
                        logger.info(f"Layover {layover.id}: Sending FIRST reminder (12h elapsed)")

                    elif layover.reminder_count == 1 and hours_since_sent >= 24:
                        # Second reminder at 24h
                        should_send_reminder = True
                        reminder_type = "second"
                        logger.info(f"Layover {layover.id}: Sending SECOND reminder (24h elapsed)")

                    elif layover.reminder_count >= 2:
                        # Already sent 2 reminders, let escalation handle it
                        logger.debug(f"Layover {layover.id}: Already sent {layover.reminder_count} reminders, awaiting escalation")
                        continue

                    # Send reminder if needed
                    if should_send_reminder:
                        try:
                            result = notification_service.send_hotel_reminder(
                                layover_id=layover.id,
                                reminder_number=layover.reminder_count + 1
                            )

                            if result["success"]:
                                # Update layover
                                layover.reminder_count += 1
                                layover.last_reminder_sent_at = datetime.utcnow()
                                layover_repo.update(layover)

                                reminders_sent += 1
                                logger.info(f"✅ Layover {layover.id}: {reminder_type.upper()} reminder sent successfully")
                            else:
                                logger.error(f"❌ Layover {layover.id}: Failed to send {reminder_type} reminder")

                        except Exception as e:
                            logger.error(f"❌ Layover {layover.id}: Error sending reminder: {e}")

                except Exception as e:
                    logger.error(f"Error processing layover {layover.id}: {e}")

            logger.info(f"✅ Reminder processing complete: {reminders_sent} reminders sent")

            db.commit()

        except Exception as e:
            logger.error(f"❌ Fatal error in reminder processing: {e}")
            db.rollback()

        finally:
            db.close()

    # ==================== ESCALATION PROCESSING ====================

    def process_escalations(self):
        """
        Process pending layovers and escalate if needed.

        Logic:
        - Check all layovers with status=PENDING
        - Skip if reminders_paused=True
        - Escalate if 36h+ since sent with no response
        - Change status to ESCALATED
        - Send alerts to supervisors
        """
        db = self._get_db_session()

        try:
            logger.info("🚨 Starting escalation processing...")

            layover_repo = LayoverRepository(db)
            notification_service = NotificationService(db)

            # Get all pending layovers
            pending_layovers = layover_repo.get_by_status(LayoverStatus.PENDING)

            logger.info(f"Found {len(pending_layovers)} pending layovers to check for escalation")

            escalations_processed = 0

            for layover in pending_layovers:
                try:
                    # Skip if reminders paused (probably IRROPS)
                    if layover.reminders_paused:
                        logger.debug(f"Layover {layover.id}: Reminders paused, skipping escalation")
                        continue

                    # Skip if no sent_at timestamp
                    if not layover.sent_at:
                        logger.warning(f"Layover {layover.id}: Status is PENDING but no sent_at timestamp")
                        continue

                    # Calculate time since sent
                    time_since_sent = datetime.utcnow() - layover.sent_at
                    hours_since_sent = time_since_sent.total_seconds() / 3600

                    # Check if escalation is needed (36 hours threshold)
                    ESCALATION_THRESHOLD_HOURS = 36

                    if hours_since_sent >= ESCALATION_THRESHOLD_HOURS:
                        logger.warning(f"Layover {layover.id}: ESCALATING - {hours_since_sent:.1f}h without response")

                        try:
                            # Send escalation alert
                            result = notification_service.send_escalation_alert(layover_id=layover.id)

                            if result["success"]:
                                # Update layover status to ESCALATED
                                layover.status = LayoverStatus.ESCALATED
                                layover.escalated_at = datetime.utcnow()
                                layover_repo.update(layover)

                                escalations_processed += 1
                                logger.info(f"✅ Layover {layover.id}: Escalated successfully")
                            else:
                                logger.error(f"❌ Layover {layover.id}: Failed to send escalation alerts")

                        except Exception as e:
                            logger.error(f"❌ Layover {layover.id}: Error during escalation: {e}")

                    else:
                        # Not yet time to escalate
                        hours_remaining = ESCALATION_THRESHOLD_HOURS - hours_since_sent
                        logger.debug(f"Layover {layover.id}: {hours_remaining:.1f}h until escalation")

                except Exception as e:
                    logger.error(f"Error processing layover {layover.id} for escalation: {e}")

            logger.info(f"✅ Escalation processing complete: {escalations_processed} layovers escalated")

            db.commit()

        except Exception as e:
            logger.error(f"❌ Fatal error in escalation processing: {e}")
            db.rollback()

        finally:
            db.close()

    # ==================== MANUAL TRIGGERS ====================

    def trigger_reminder_manually(self, layover_id: int, db: Session) -> dict:
        """
        Manually trigger a reminder for a specific layover.

        Used by operators to send immediate reminders outside the schedule.

        Args:
            layover_id: ID of the layover
            db: Database session

        Returns:
            Dict with success status
        """
        try:
            layover_repo = LayoverRepository(db)
            notification_service = NotificationService(db)

            layover = layover_repo.get_by_id(layover_id)
            if not layover:
                return {"success": False, "error": "Layover not found"}

            if layover.status != LayoverStatus.PENDING:
                return {"success": False, "error": f"Cannot send reminder for layover with status {layover.status.value}"}

            if layover.reminders_paused:
                return {"success": False, "error": "Reminders are paused for this layover"}

            # Send reminder
            result = notification_service.send_hotel_reminder(
                layover_id=layover_id,
                reminder_number=layover.reminder_count + 1
            )

            if result["success"]:
                # Update layover
                layover.reminder_count += 1
                layover.last_reminder_sent_at = datetime.utcnow()
                layover_repo.update(layover)

                logger.info(f"✅ Manual reminder sent for layover {layover_id}")
                return {"success": True, "message": "Reminder sent successfully"}
            else:
                return {"success": False, "error": "Failed to send reminder"}

        except Exception as e:
            logger.error(f"Error in manual reminder trigger: {e}")
            return {"success": False, "error": str(e)}

    # ==================== STATUS & MONITORING ====================

    def get_scheduler_status(self) -> dict:
        """
        Get scheduler status and job information.

        Returns:
            Dict with scheduler status, jobs, and next run times
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })

        return {
            "running": self.scheduler.running,
            "jobs": jobs,
            "total_jobs": len(jobs),
        }


# ==================== GLOBAL INSTANCE ====================

# Singleton instance
_scheduler_service: Optional[SchedulerService] = None


def get_scheduler_service() -> SchedulerService:
    """Get the global scheduler service instance"""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service


def start_scheduler():
    """Start the global scheduler service"""
    scheduler = get_scheduler_service()
    scheduler.start()


def shutdown_scheduler():
    """Shutdown the global scheduler service"""
    global _scheduler_service
    if _scheduler_service is not None:
        _scheduler_service.shutdown()
        _scheduler_service = None
