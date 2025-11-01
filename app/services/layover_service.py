"""
Layover Service - Business logic layer for layover operations
Handles validation, state transitions, notifications, and audit logging
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.layover import Layover, LayoverStatus, LayoverReason
from app.models.user import User
from app.models.confirmation_token import ConfirmationToken, TokenType
from app.repositories.layover_repository import LayoverRepository
from app.repositories.user_repository import UserRepository
from app.schemas.layover import (
    LayoverCreate,
    LayoverUpdate,
    LayoverAmend,
    LayoverHold,
    LayoverFinalize,
    LayoverCancel,
    LayoverFilterParams,
    LayoverResponse,
    LayoverDetailResponse,
    LayoverListResponse,
    DashboardMetrics,
    StationPerformance,
    HotelPerformance,
    RoomBreakdown
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
    BusinessRuleException
)


class LayoverService:
    """Service for layover business logic"""
    
    def __init__(
        self, 
        db: Session,
        current_user: Optional[User] = None
    ):
        self.db = db
        self.current_user = current_user
        self.repository = LayoverRepository(db)
        self.user_repository = UserRepository(db)
    
    # ==================== CREATE ====================
    
    def create_layover(
        self, 
        data: LayoverCreate
    ) -> LayoverDetailResponse:
        """
        Create a new layover request
        
        Business Rules:
        - Auto-calculate room breakdown if not provided
        - Validate station and hotel exist
        - Set initial status to DRAFT
        - Log audit trail
        
        Args:
            data: Layover creation data
            
        Returns:
            Created layover detail
            
        Raises:
            ValidationException: If validation fails
            PermissionDeniedException: If user lacks permission
        """
        # Permission check
        if not self._can_create_layover():
            raise PermissionDeniedException("User cannot create layover requests")
        
        # Auto-calculate room breakdown if needed
        room_breakdown = self._auto_calculate_rooms(
            data.crew_count, 
            data.room_breakdown
        )
        
        # Create layover model
        layover = Layover(
            origin_station_code=data.origin_station_code,
            destination_station_code=data.destination_station_code,
            station_id=data.station_id,
            hotel_id=data.hotel_id,
            layover_reason=data.layover_reason.value,
            operational_flight_number=data.operational_flight_number,
            check_in_date=data.check_in_date,
            check_in_time=data.check_in_time,
            check_out_date=data.check_out_date,
            check_out_time=data.check_out_time,
            crew_count=data.crew_count,
            room_breakdown=room_breakdown.dict(),
            special_requirements=data.special_requirements,
            transport_required=data.transport_required,
            transport_details=data.transport_details,
            trip_id=data.trip_id,
            trip_sequence=data.trip_sequence,
            is_positioning=data.is_positioning,
            estimated_cost=data.estimated_cost,
            currency=data.currency,
            status=LayoverStatus.DRAFT,
            created_by=self.current_user.id
        )
        
        # Save to database
        layover = self.repository.create(layover)
        
        # Log audit trail
        self._log_audit(
            layover_id=layover.id,
            action="layover_created",
            details={
                "status": LayoverStatus.DRAFT.value,
                "station_id": data.station_id,
                "crew_count": data.crew_count,
                "layover_reason": data.layover_reason.value
            }
        )
        
        return self._to_detail_response(layover)
    
    def _auto_calculate_rooms(
        self, 
        crew_count: int, 
        provided_breakdown: RoomBreakdown
    ) -> RoomBreakdown:
        """
        Auto-calculate or validate room breakdown
        
        Default: 1 single per crew member (ops can override)
        
        Args:
            crew_count: Number of crew
            provided_breakdown: User-provided breakdown
            
        Returns:
            Validated room breakdown
            
        Raises:
            ValidationException: If total rooms don't match crew count
        """
        total_rooms = (
            provided_breakdown.singles + 
            provided_breakdown.doubles * 2 + 
            provided_breakdown.suites
        )
        
        # Validate total capacity matches crew count
        if total_rooms < crew_count:
            raise ValidationException(
                f"Room capacity ({total_rooms}) insufficient for {crew_count} crew members"
            )
        
        return provided_breakdown
    
    # ==================== READ ====================
    
    def get_layover_by_id(
        self, 
        layover_id: int
    ) -> LayoverDetailResponse:
        """
        Get layover by ID with permission check
        
        Args:
            layover_id: Layover ID
            
        Returns:
            Layover detail
            
        Raises:
            NotFoundException: If layover not found
            PermissionDeniedException: If user cannot access this layover
        """
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_access_layover(layover):
            raise PermissionDeniedException(
                "User cannot access this layover (station restriction)"
            )
        
        return self._to_detail_response(layover)
    
    def list_layovers(
        self, 
        filters: LayoverFilterParams
    ) -> LayoverListResponse:
        """
        List layovers with filtering and pagination
        
        Args:
            filters: Filter parameters
            
        Returns:
            Paginated layover list
        """
        # Apply station filter based on user role
        station_ids = self._get_accessible_station_ids(filters.station_ids)
        
        # Calculate pagination
        skip = (filters.page - 1) * filters.page_size
        
        # Build status filter
        statuses = None
        if filters.statuses:
            statuses = [s.value for s in filters.statuses]
        elif filters.status:
            statuses = [filters.status.value]
        
        # Query repository
        layovers, total = self.repository.list_layovers(
            station_ids=station_ids,
            statuses=statuses,
            check_in_date_from=filters.check_in_date_from,
            check_in_date_to=filters.check_in_date_to,
            hotel_id=filters.hotel_id,
            created_by=filters.created_by,
            search_query=filters.search,
            skip=skip,
            limit=filters.page_size,
            order_by=filters.order_by,
            order_direction=filters.order_direction
        )
        
        # Convert to response
        items = [self._to_basic_response(l) for l in layovers]
        
        return LayoverListResponse(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=0  # Calculated by validator
        )
    
    # ==================== UPDATE ====================
    
    def update_layover(
        self, 
        layover_id: int, 
        data: LayoverUpdate
    ) -> LayoverDetailResponse:
        """
        Update layover (draft only or specific fields)
        
        Business Rules:
        - Only drafts can be fully edited
        - Confirmed layovers require amendment flow
        - Cannot change route or dates without hotel re-confirmation
        
        Args:
            layover_id: Layover ID
            data: Update data
            
        Returns:
            Updated layover
            
        Raises:
            NotFoundException: If layover not found
            BusinessRuleException: If update not allowed
        """
        layover = self.repository.get_by_id(layover_id)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot edit this layover")
        
        # Status check
        if layover.status not in [LayoverStatus.DRAFT]:
            raise BusinessRuleException(
                "Cannot update layover after sending to hotel. Use amend flow."
            )
        
        # Update allowed fields
        update_data = data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "room_breakdown" and value:
                # Validate room breakdown
                validated = self._auto_calculate_rooms(
                    layover.crew_count, 
                    RoomBreakdown(**value)
                )
                setattr(layover, field, validated.dict())
            else:
                setattr(layover, field, value)
        
        # Save
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="layover_updated",
            details={"updated_fields": list(update_data.keys())}
        )
        
        return self._to_detail_response(layover)
    
    # ==================== SEND TO HOTEL ====================
    
    def send_to_hotel(
        self, 
        layover_id: int
    ) -> LayoverDetailResponse:
        """
        Send layover request to hotel
        
        Business Rules:
        - Only drafts can be sent
        - Hotel must be assigned
        - Generate confirmation token
        - Send email notification
        - Schedule reminders
        - Update status to SENT → PENDING
        
        Args:
            layover_id: Layover ID
            
        Returns:
            Updated layover
            
        Raises:
            BusinessRuleException: If cannot send
        """
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot send this layover")
        
        # Validation
        if layover.status != LayoverStatus.DRAFT:
            raise BusinessRuleException(
                f"Cannot send layover in status {layover.status.value}"
            )
        
        if not layover.hotel_id:
            raise BusinessRuleException("Hotel must be assigned before sending")
        
        # Generate confirmation token
        token = self._generate_confirmation_token(layover)
        
        # Update status
        layover.status = LayoverStatus.SENT
        layover.sent_at = datetime.utcnow()
        layover = self.repository.update(layover)
        
        # Change to PENDING (waiting for hotel response)
        layover.status = LayoverStatus.PENDING
        layover.pending_at = datetime.utcnow()
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="sent_to_hotel",
            details={
                "hotel_id": layover.hotel_id,
                "hotel_name": layover.hotel.name if layover.hotel else None,
                "token_expires_at": token.expires_at.isoformat()
            }
        )
        
        # TODO: Send email notification (Phase 3)
        # self.notification_service.send_hotel_request(layover, token)
        
        # TODO: Schedule reminders (Phase 4)
        # self.reminder_service.schedule_reminders(layover)
        
        return self._to_detail_response(layover)
    
    def _generate_confirmation_token(self, layover: Layover) -> ConfirmationToken:
        """
        Generate confirmation token for hotel
        
        Args:
            layover: Layover instance
            
        Returns:
            Confirmation token
        """
        import uuid
        
        token = ConfirmationToken(
            token=str(uuid.uuid4()),
            token_type=TokenType.HOTEL_CONFIRMATION,
            layover_id=layover.id,
            hotel_id=layover.hotel_id,
            expires_at=datetime.utcnow() + timedelta(hours=72),
            is_valid=True
        )
        
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        
        return token
    
    # ==================== DUPLICATE ====================
    
    def duplicate_layover(
        self, 
        layover_id: int
    ) -> LayoverDetailResponse:
        """
        Duplicate an existing layover
        
        Business Rules:
        - Copy all fields except: ID, UUID, dates, status, timestamps
        - Reset to DRAFT status
        - Log duplication source
        
        Args:
            layover_id: Original layover ID
            
        Returns:
            New layover (draft)
        """
        original = self.repository.get_by_id(layover_id, load_relations=True)
        
        if not original:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_access_layover(original):
            raise PermissionDeniedException("User cannot access this layover")
        
        # Create duplicate
        duplicate = Layover(
            # Copy these fields
            origin_station_code=original.origin_station_code,
            destination_station_code=original.destination_station_code,
            station_id=original.station_id,
            hotel_id=original.hotel_id,
            layover_reason=original.layover_reason,
            operational_flight_number=original.operational_flight_number,
            crew_count=original.crew_count,
            room_breakdown=original.room_breakdown,
            special_requirements=original.special_requirements,
            transport_required=original.transport_required,
            transport_details=original.transport_details,
            trip_id=original.trip_id,
            is_positioning=original.is_positioning,
            estimated_cost=original.estimated_cost,
            currency=original.currency,
            
            # Reset these fields
            status=LayoverStatus.DRAFT,
            created_by=self.current_user.id,
            # check_in_date, check_in_time, check_out_date, check_out_time = None (user must set)
        )
        
        duplicate = self.repository.create(duplicate)
        
        # Log audit
        self._log_audit(
            layover_id=duplicate.id,
            action="layover_duplicated",
            details={
                "source_layover_id": original.id,
                "source_layover_uuid": original.uuid
            }
        )
        
        return self._to_detail_response(duplicate)
    
    # ==================== HOLD & RESUME (IRROPS) ====================
    
    def put_on_hold(
        self, 
        layover_id: int, 
        data: LayoverHold
    ) -> LayoverDetailResponse:
        """
        Put layover on hold (irregular operations)
        
        Business Rules:
        - Can only hold SENT, PENDING, or CONFIRMED layovers
        - Pause reminders automatically
        - Notify hotel (if confirmed)
        
        Args:
            layover_id: Layover ID
            data: Hold reason
            
        Returns:
            Updated layover
        """
        layover = self.repository.get_by_id(layover_id)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot modify this layover")
        
        # Status check
        allowed_statuses = [
            LayoverStatus.SENT,
            LayoverStatus.PENDING,
            LayoverStatus.CONFIRMED
        ]
        
        if layover.status not in allowed_statuses:
            raise BusinessRuleException(
                f"Cannot hold layover in status {layover.status.value}"
            )
        
        # Update status
        layover.status = LayoverStatus.ON_HOLD
        layover.on_hold_at = datetime.utcnow()
        layover.on_hold_reason = data.on_hold_reason
        
        # Pause reminders
        layover.reminders_paused = True
        layover.reminders_paused_reason = data.on_hold_reason
        layover.reminders_paused_at = datetime.utcnow()
        
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="layover_put_on_hold",
            details={"reason": data.on_hold_reason}
        )
        
        # TODO: Notify hotel if confirmed (Phase 3)
        
        return self._to_detail_response(layover)
    
    def resume_from_hold(
        self, 
        layover_id: int
    ) -> LayoverDetailResponse:
        """
        Resume layover from hold
        
        Business Rules:
        - Can only resume ON_HOLD layovers
        - Restore previous status (or PENDING if unknown)
        - Resume reminders if not yet confirmed
        
        Args:
            layover_id: Layover ID
            
        Returns:
            Updated layover
        """
        layover = self.repository.get_by_id(layover_id)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot modify this layover")
        
        # Status check
        if layover.status != LayoverStatus.ON_HOLD:
            raise BusinessRuleException(
                f"Cannot resume layover in status {layover.status.value}"
            )
        
        # Restore status (default to PENDING)
        if layover.confirmed_at:
            layover.status = LayoverStatus.CONFIRMED
        else:
            layover.status = LayoverStatus.PENDING
        
        # Resume reminders
        layover.reminders_paused = False
        layover.reminders_paused_reason = None
        
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="layover_resumed_from_hold",
            details={"new_status": layover.status.value}
        )
        
        return self._to_detail_response(layover)
    
    # ==================== AMEND (POST-CONFIRMATION) ====================
    
    def amend_layover(
        self, 
        layover_id: int, 
        data: LayoverAmend
    ) -> LayoverDetailResponse:
        """
        Amend a confirmed layover (post-confirmation changes)
        
        Business Rules:
        - Can only amend CONFIRMED layovers
        - Increment amendment counter
        - Mark hotel notification pending
        - Log amendment reason
        
        Args:
            layover_id: Layover ID
            data: Amendment data
            
        Returns:
            Updated layover
        """
        layover = self.repository.get_by_id(layover_id)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot amend this layover")
        
        # Status check
        if layover.status != LayoverStatus.CONFIRMED:
            raise BusinessRuleException(
                "Can only amend CONFIRMED layovers. Current status: " +
                layover.status.value
            )
        
        # Apply amendments
        update_data = data.dict(exclude_unset=True, exclude={'amendment_reason'})
        
        for field, value in update_data.items():
            if field == "room_breakdown" and value:
                validated = self._auto_calculate_rooms(
                    layover.crew_count,
                    RoomBreakdown(**value)
                )
                setattr(layover, field, validated.dict())
            else:
                setattr(layover, field, value)
        
        # Update amendment tracking
        layover.status = LayoverStatus.AMENDED
        layover.amendment_count += 1
        layover.last_amended_at = datetime.utcnow()
        layover.hotel_notified_of_amendment = False
        
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="layover_amended",
            details={
                "amendment_reason": data.amendment_reason,
                "amendment_number": layover.amendment_count,
                "amended_fields": list(update_data.keys())
            }
        )
        
        # TODO: Notify hotel of amendment (Phase 3)
        
        return self._to_detail_response(layover)
    
    # ==================== FINALIZE ====================
    
    def finalize_layover(
        self, 
        layover_id: int, 
        data: LayoverFinalize
    ) -> LayoverDetailResponse:
        """
        Finalize layover and notify crew
        
        Business Rules:
        - Can only finalize CONFIRMED or AMENDED layovers
        - Update status to COMPLETED
        - Log confirmation number
        - Trigger crew notifications
        
        Args:
            layover_id: Layover ID
            data: Finalization data
            
        Returns:
            Completed layover
        """
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot finalize this layover")
        
        # Status check
        allowed_statuses = [LayoverStatus.CONFIRMED, LayoverStatus.AMENDED]
        
        if layover.status not in allowed_statuses:
            raise BusinessRuleException(
                f"Can only finalize CONFIRMED or AMENDED layovers. " +
                f"Current status: {layover.status.value}"
            )
        
        # Update layover
        layover.status = LayoverStatus.COMPLETED
        layover.completed_at = datetime.utcnow()
        layover.hotel_confirmation_number = data.hotel_confirmation_number
        
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="layover_finalized",
            details={
                "confirmation_number": data.hotel_confirmation_number,
                "final_notes": data.final_notes,
                "sms_notification": data.send_sms_notification
            }
        )
        
        # TODO: Notify crew (Phase 3)
        # self.notification_service.notify_crew(layover, data.send_sms_notification)
        
        return self._to_detail_response(layover)
    
    # ==================== CANCEL ====================
    
    def cancel_layover(
        self, 
        layover_id: int, 
        data: LayoverCancel
    ) -> LayoverDetailResponse:
        """
        Cancel a layover
        
        Business Rules:
        - Calculate cancellation notice hours
        - Determine if charge applies (<24h = charge)
        - Notify hotel if confirmed
        - Log cancellation reason
        
        Args:
            layover_id: Layover ID
            data: Cancellation data
            
        Returns:
            Cancelled layover
        """
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot cancel this layover")
        
        # Status check (cannot cancel COMPLETED)
        if layover.status == LayoverStatus.COMPLETED:
            raise BusinessRuleException("Cannot cancel completed layovers")
        
        # Calculate notice hours
        now = datetime.utcnow()
        check_in_datetime = datetime.combine(
            layover.check_in_date,
            layover.check_in_time
        )
        notice_hours = int((check_in_datetime - now).total_seconds() / 3600)
        
        # Determine if charge applies (<24h notice)
        charge_applies = notice_hours < 24
        
        # Update layover
        layover.status = LayoverStatus.CANCELLED
        layover.cancelled_at = now
        layover.cancellation_reason = data.cancellation_reason.value
        layover.cancellation_notice_hours = notice_hours
        layover.cancellation_charge_applies = charge_applies
        
        # Pause reminders
        layover.reminders_paused = True
        layover.reminders_paused_reason = f"Cancelled: {data.cancellation_reason.value}"
        
        layover = self.repository.update(layover)
        
        # Log audit
        self._log_audit(
            layover_id=layover.id,
            action="layover_cancelled",
            details={
                "cancellation_reason": data.cancellation_reason.value,
                "cancellation_note": data.cancellation_note,
                "notice_hours": notice_hours,
                "charge_applies": charge_applies
            }
        )
        
        # TODO: Notify hotel (Phase 3)
        
        return self._to_detail_response(layover)
    
    # ==================== DELETE ====================
    
    def delete_layover(self, layover_id: int) -> bool:
        """
        Delete a layover (drafts only)
        
        Args:
            layover_id: Layover ID
            
        Returns:
            True if deleted
            
        Raises:
            BusinessRuleException: If not a draft
        """
        layover = self.repository.get_by_id(layover_id)
        
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")
        
        # Permission check
        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot delete this layover")
        
        # Only drafts can be deleted
        if layover.status != LayoverStatus.DRAFT:
            raise BusinessRuleException(
                "Can only delete drafts. Use cancel for sent requests."
            )
        
        # Log audit before deletion
        self._log_audit(
            layover_id=layover.id,
            action="layover_deleted",
            details={"status_at_deletion": layover.status.value}
        )
        
        return self.repository.delete(layover_id)
    
    # ==================== METRICS & ANALYTICS ====================
    
    def get_dashboard_metrics(
        self,
        station_ids: Optional[List[int]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> DashboardMetrics:
        """Get dashboard summary metrics"""
        
        # Apply station filter based on user role
        accessible_station_ids = self._get_accessible_station_ids(station_ids)
        
        metrics = self.repository.get_dashboard_metrics(
            station_ids=accessible_station_ids,
            date_from=date_from,
            date_to=date_to
        )
        
        return DashboardMetrics(**metrics)
    
    def get_station_performance(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[StationPerformance]:
        """Get station performance report"""
        
        performance = self.repository.get_station_performance(
            date_from=date_from,
            date_to=date_to
        )
        
        return [StationPerformance(**p) for p in performance]
    
    def get_hotel_performance(
        self,
        station_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_requests: int = 3
    ) -> List[HotelPerformance]:
        """Get hotel performance report"""
        
        performance = self.repository.get_hotel_performance(
            station_id=station_id,
            date_from=date_from,
            date_to=date_to,
            min_requests=min_requests
        )
        
        return [HotelPerformance(**p) for p in performance]
    
    # ==================== PERMISSION HELPERS ====================
    
    def _can_create_layover(self) -> bool:
        """Check if user can create layovers"""
        if not self.current_user:
            return False
        
        allowed_roles = ['admin', 'ops_coordinator']
        return self.current_user.role in allowed_roles
    
    def _can_access_layover(self, layover: Layover) -> bool:
        """Check if user can access this layover"""
        if not self.current_user:
            return False
        
        # Admins and supervisors see all
        if self.current_user.role in ['admin', 'supervisor']:
            return True
        
        # Station users see only their stations
        if self.current_user.role == 'station_user':
            if self.current_user.station_ids:
                return layover.station_id in self.current_user.station_ids
            return False
        
        # Ops coordinators see all
        if self.current_user.role == 'ops_coordinator':
            return True
        
        return False
    
    def _can_edit_layover(self, layover: Layover) -> bool:
        """Check if user can edit this layover"""
        if not self.current_user:
            return False
        
        # Must be able to access first
        if not self._can_access_layover(layover):
            return False
        
        # Only admins and ops coordinators can edit
        allowed_roles = ['admin', 'ops_coordinator']
        
        # Station users can edit their own station's layovers
        if self.current_user.role == 'station_user':
            if self.current_user.station_ids:
                return layover.station_id in self.current_user.station_ids
        
        return self.current_user.role in allowed_roles
    
    def _get_accessible_station_ids(
        self, 
        requested_ids: Optional[List[int]]
    ) -> Optional[List[int]]:
        """
        Get station IDs accessible to current user
        
        Args:
            requested_ids: User-requested station filter
            
        Returns:
            List of accessible station IDs or None (all)
        """
        if not self.current_user:
            return []
        
        # Admins and supervisors see all
        if self.current_user.role in ['admin', 'supervisor', 'ops_coordinator']:
            return requested_ids  # Use user's filter or None (all)
        
        # Station users see only their stations
        if self.current_user.role == 'station_user':
            user_stations = self.current_user.station_ids or []
            
            if requested_ids:
                # Intersection of user's stations and requested
                return list(set(user_stations) & set(requested_ids))
            
            return user_stations
        
        return []
    
    # ==================== AUDIT LOGGING ====================
    
    def _log_audit(
        self, 
        layover_id: int, 
        action: str, 
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log audit trail entry
        
        Args:
            layover_id: Layover ID
            action: Action type
            details: Additional details
        """
        from app.models.audit_log import AuditLog
        
        # TODO: Get IP address from request context
        ip_address = None
        
        audit = AuditLog(
            user_id=self.current_user.id if self.current_user else None,
            user_role=self.current_user.role if self.current_user else None,
            action_type=action,
            entity_type='layover',
            entity_id=layover_id,
            details=details,
            ip_address=ip_address
        )
        
        self.db.add(audit)
        self.db.commit()
    
    # ==================== RESPONSE CONVERTERS ====================
    
    def _to_basic_response(self, layover: Layover) -> LayoverResponse:
        """Convert layover model to basic response"""
        return LayoverResponse.from_orm(layover)
    
    def _to_detail_response(self, layover: Layover) -> LayoverDetailResponse:
        """Convert layover model to detail response"""
        return LayoverDetailResponse.from_orm(layover)