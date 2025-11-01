"""
Layover Service - Business logic layer for layover operations
Pydantic v2 compatible; API shows Decimal money, DB stores integer cents.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.layover import Layover, LayoverStatus
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
    RoomBreakdown,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
    BusinessRuleException,
)

import uuid


# ==================== MONEY HELPERS ====================

def _to_cents(value: Optional[Decimal]) -> Optional[int]:
    if value is None:
        return None
    # Quantize to 2 decimals then multiply by 100
    q = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((q * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _from_cents(value: Optional[int]) -> Optional[Decimal]:
    if value is None:
        return None
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LayoverService:
    """Service for layover business logic"""

    def __init__(self, db: Session, current_user: Optional[User] = None):
        self.db = db
        self.current_user = current_user
        self.repository = LayoverRepository(db)
        self.user_repository = UserRepository(db)

    # ==================== CREATE ====================

    def create_layover(self, data: LayoverCreate) -> LayoverDetailResponse:
        # Permissions
        if not self._can_create_layover():
            raise PermissionDeniedException("User cannot create layover requests")

        # Validate / accept room breakdown
        room_breakdown = self._auto_calculate_rooms(data.crew_count, data.room_breakdown)

        # Create Layover model
        layover = Layover(
            uuid=str(uuid.uuid4()),
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
            room_breakdown=room_breakdown.model_dump(),
            special_requirements=data.special_requirements,
            transport_required=data.transport_required,
            transport_details=data.transport_details,
            trip_id=data.trip_id,
            trip_sequence=data.trip_sequence,
            is_positioning=data.is_positioning,
            estimated_cost=_to_cents(data.estimated_cost),
            currency=data.currency,
            status=LayoverStatus.DRAFT,
            created_by=self.current_user.id if self.current_user else None,
        )

        layover = self.repository.create(layover)

        self._log_audit(
            layover_id=layover.id,
            action="layover_created",
            details={
                "status": LayoverStatus.DRAFT.value,
                "station_id": data.station_id,
                "crew_count": data.crew_count,
                "layover_reason": data.layover_reason.value,
            },
        )

        return self._to_detail_response(layover)

    def _auto_calculate_rooms(self, crew_count: int, provided_breakdown: RoomBreakdown) -> RoomBreakdown:
        """
        Currently just validates capacity >= crew_count.
        (If later you want to auto-derive rooms from crew_count, you can enhance here.)
        """
        total_capacity = provided_breakdown.singles + provided_breakdown.doubles * 2 + provided_breakdown.suites
        if total_capacity < crew_count:
            raise ValidationException(
                f"Room capacity ({total_capacity}) insufficient for {crew_count} crew members"
            )
        return provided_breakdown

    # ==================== READ ====================

    def get_layover_by_id(self, layover_id: int) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_access_layover(layover):
            raise PermissionDeniedException("User cannot access this layover (station restriction)")

        return self._to_detail_response(layover)

    def list_layovers(self, filters: LayoverFilterParams) -> LayoverListResponse:
        station_ids = self._get_accessible_station_ids(filters.station_ids)

        skip = (filters.page - 1) * filters.page_size

        # Build statuses as enum list (not strings)
        statuses = None
        if filters.statuses:
            statuses = filters.statuses
        elif filters.status:
            statuses = [filters.status]

        layovers, total = self.repository.list_layovers(
            station_ids=station_ids,
            status=None,                # let statuses drive filter
            statuses=statuses,
            check_in_date_from=filters.check_in_date_from,
            check_in_date_to=filters.check_in_date_to,
            hotel_id=filters.hotel_id,
            created_by=filters.created_by,
            search_query=filters.search,
            skip=skip,
            limit=filters.page_size,
            order_by=filters.order_by,
            order_direction=filters.order_direction,
        )

        items = [self._to_basic_response(l) for l in layovers]

        return LayoverListResponse(
            items=items,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    # ==================== UPDATE ====================

    def update_layover(self, layover_id: int, data: LayoverUpdate) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot edit this layover")

        if layover.status not in [LayoverStatus.DRAFT]:
            raise BusinessRuleException("Cannot update layover after sending to hotel. Use amend flow.")

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == "room_breakdown" and value:
                validated = self._auto_calculate_rooms(layover.crew_count, RoomBreakdown(**value))
                setattr(layover, field, validated.model_dump())
            elif field == "estimated_cost":
                setattr(layover, "estimated_cost", _to_cents(value))
            else:
                setattr(layover, field, value)

        layover = self.repository.update(layover)

        self._log_audit(
            layover_id=layover.id,
            action="layover_updated",
            details={"updated_fields": list(update_data.keys())},
        )

        return self._to_detail_response(layover)

    # ==================== SEND TO HOTEL ====================

    def send_to_hotel(self, layover_id: int) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot send this layover")

        if layover.status != LayoverStatus.DRAFT:
            raise BusinessRuleException(f"Cannot send layover in status {layover.status.value}")

        if not layover.hotel_id:
            raise BusinessRuleException("Hotel must be assigned before sending")

        token = self._generate_confirmation_token(layover)

        layover.status = LayoverStatus.SENT
        layover.sent_at = datetime.utcnow()
        layover = self.repository.update(layover)

        layover.status = LayoverStatus.PENDING
        layover.pending_at = datetime.utcnow()
        layover = self.repository.update(layover)

        self._log_audit(
            layover_id=layover.id,
            action="sent_to_hotel",
            details={
                "hotel_id": layover.hotel_id,
                "hotel_name": layover.hotel.name if layover.hotel else None,
                "token_expires_at": token.expires_at.isoformat(),
            },
        )

        return self._to_detail_response(layover)

    def _generate_confirmation_token(self, layover: Layover) -> ConfirmationToken:
        token = ConfirmationToken(
            token=str(uuid.uuid4()),
            token_type=TokenType.HOTEL_CONFIRMATION,
            layover_id=layover.id,
            hotel_id=layover.hotel_id,
            expires_at=datetime.utcnow() + timedelta(hours=72),
            is_valid=True,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    # ==================== DUPLICATE ====================

    def duplicate_layover(self, layover_id: int) -> LayoverDetailResponse:
        original = self.repository.get_by_id(layover_id, load_relations=True)
        if not original:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_access_layover(original):
            raise PermissionDeniedException("User cannot access this layover")

        duplicate = Layover(
            uuid=str(uuid.uuid4()),
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
            estimated_cost=original.estimated_cost,  # already in cents
            currency=original.currency,
            status=LayoverStatus.DRAFT,
            created_by=self.current_user.id if self.current_user else None,
        )

        duplicate = self.repository.create(duplicate)

        self._log_audit(
            layover_id=duplicate.id,
            action="layover_duplicated",
            details={"source_layover_id": original.id, "source_layover_uuid": original.uuid},
        )

        return self._to_detail_response(duplicate)

    # ==================== HOLD/RESUME ====================

    def put_on_hold(self, layover_id: int, data: LayoverHold) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot modify this layover")

        if layover.status not in [LayoverStatus.SENT, LayoverStatus.PENDING, LayoverStatus.CONFIRMED]:
            raise BusinessRuleException(f"Cannot hold layover in status {layover.status.value}")

        layover.status = LayoverStatus.ON_HOLD
        layover.on_hold_at = datetime.utcnow()
        layover.on_hold_reason = data.on_hold_reason

        layover.reminders_paused = True
        layover.reminders_paused_reason = data.on_hold_reason
        layover.reminders_paused_at = datetime.utcnow()

        layover = self.repository.update(layover)

        self._log_audit(layover_id=layover.id, action="layover_put_on_hold", details={"reason": data.on_hold_reason})
        return self._to_detail_response(layover)

    def resume_from_hold(self, layover_id: int) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot modify this layover")

        if layover.status != LayoverStatus.ON_HOLD:
            raise BusinessRuleException(f"Cannot resume layover in status {layover.status.value}")

        if layover.confirmed_at:
            layover.status = LayoverStatus.CONFIRMED
        else:
            layover.status = LayoverStatus.PENDING

        layover.reminders_paused = False
        layover.reminders_paused_reason = None

        layover = self.repository.update(layover)

        self._log_audit(
            layover_id=layover.id, action="layover_resumed_from_hold", details={"new_status": layover.status.value}
        )
        return self._to_detail_response(layover)

    # ==================== AMEND/FINALIZE/CANCEL ====================

    def amend_layover(self, layover_id: int, data: LayoverAmend) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot amend this layover")

        if layover.status != LayoverStatus.CONFIRMED:
            raise BusinessRuleException("Can only amend CONFIRMED layovers. Current status: " + layover.status.value)

        update_data = data.model_dump(exclude_unset=True, exclude={"amendment_reason"})
        for field, value in update_data.items():
            if field == "room_breakdown" and value:
                validated = self._auto_calculate_rooms(layover.crew_count, RoomBreakdown(**value))
                setattr(layover, field, validated.model_dump())
            else:
                setattr(layover, field, value)

        layover.status = LayoverStatus.AMENDED
        layover.amendment_count += 1
        layover.last_amended_at = datetime.utcnow()
        layover.hotel_notified_of_amendment = False

        layover = self.repository.update(layover)

        self._log_audit(
            layover_id=layover.id,
            action="layover_amended",
            details={
                "amendment_reason": data.amendment_reason,
                "amendment_number": layover.amendment_count,
                "amended_fields": list(update_data.keys()),
            },
        )

        return self._to_detail_response(layover)

    def finalize_layover(self, layover_id: int, data: LayoverFinalize) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot finalize this layover")

        if layover.status not in [LayoverStatus.CONFIRMED, LayoverStatus.AMENDED]:
            raise BusinessRuleException(
                f"Can only finalize CONFIRMED or AMENDED layovers. Current status: {layover.status.value}"
            )

        layover.status = LayoverStatus.COMPLETED
        layover.completed_at = datetime.utcnow()
        layover.hotel_confirmation_number = data.hotel_confirmation_number

        layover = self.repository.update(layover)

        self._log_audit(
            layover_id=layover.id,
            action="layover_finalized",
            details={
                "confirmation_number": data.hotel_confirmation_number,
                "final_notes": data.final_notes,
                "sms_notification": data.send_sms_notification,
            },
        )

        return self._to_detail_response(layover)

    def cancel_layover(self, layover_id: int, data: LayoverCancel) -> LayoverDetailResponse:
        layover = self.repository.get_by_id(layover_id, load_relations=True)
        if not layover:
            raise NotFoundException(f"Layover {layover_id} not found")

        if not self._can_edit_layover(layover):
            raise PermissionDeniedException("User cannot cancel this layover")

        if layover.status == LayoverStatus.COMPLETED:
            raise BusinessRuleException("Cannot cancel completed layovers")

        now = datetime.utcnow()
        check_in_datetime = datetime.combine(layover.check_in_date, layover.check_in_time)
        notice_hours = int((check_in_datetime - now).total_seconds() // 3600)

        # Airline-standard tiers (Option D)
        if notice_hours > 48:
            charge_applies, policy, percent = (False, "no_charge", 0)
        elif 24 < notice_hours <= 48:
            charge_applies, policy, percent = (True, "24_48h_50", 50)
        else:  # <= 24h
            charge_applies, policy, percent = (True, "lt_24h_100", 100)

        fee_cents = None  # compute later if you have per-night rates

        layover.status = LayoverStatus.CANCELLED
        layover.cancelled_at = now
        layover.cancellation_reason = data.cancellation_reason.value
        layover.cancellation_notice_hours = notice_hours
        layover.cancellation_charge_applies = charge_applies
        layover.cancellation_charge_policy = policy
        layover.cancellation_charge_percent = percent
        layover.cancellation_fee_cents = fee_cents

        layover.reminders_paused = True
        layover.reminders_paused_reason = f"Cancelled: {data.cancellation_reason.value}"

        layover = self.repository.update(layover)

        self._log_audit(
            layover_id=layover.id,
            action="layover_cancelled",
            details={
                "cancellation_reason": data.cancellation_reason.value,
                "cancellation_note": data.cancellation_note,
                "notice_hours": notice_hours,
                "policy": policy,
                "percent": percent,
                "fee_cents": fee_cents
            }
        )

        return self._to_detail_response(layover)


    # ==================== METRICS ====================

    def get_dashboard_metrics(
        self,
        station_ids: Optional[List[int]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> DashboardMetrics:
        accessible_station_ids = self._get_accessible_station_ids(station_ids)
        metrics = self.repository.get_dashboard_metrics(
            station_ids=accessible_station_ids, date_from=date_from, date_to=date_to
        )
        return DashboardMetrics(**metrics)

    def get_station_performance(
        self, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None
    ) -> List[StationPerformance]:
        performance = self.repository.get_station_performance(date_from=date_from, date_to=date_to)
        return [StationPerformance(**p) for p in performance]

    def get_hotel_performance(
        self,
        station_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_requests: int = 3,
    ) -> List[HotelPerformance]:
        performance = self.repository.get_hotel_performance(
            station_id=station_id, date_from=date_from, date_to=date_to, min_requests=min_requests
        )
        return [HotelPerformance(**p) for p in performance]

    # ==================== PERMISSIONS ====================

    def _can_create_layover(self) -> bool:
        if not self.current_user:
            return False
        return self.current_user.role in ["admin", "ops_coordinator"]

    def _can_access_layover(self, layover: Layover) -> bool:
        if not self.current_user:
            return False
        if self.current_user.role in ["admin", "supervisor", "ops_coordinator"]:
            return True
        if self.current_user.role == "station_user":
            return bool(self.current_user.station_ids and layover.station_id in self.current_user.station_ids)
        return False

    def _can_edit_layover(self, layover: Layover) -> bool:
        if not self.current_user:
            return False
        if not self._can_access_layover(layover):
            return False
        if self.current_user.role in ["admin", "ops_coordinator"]:
            return True
        if self.current_user.role == "station_user":
            return bool(self.current_user.station_ids and layover.station_id in self.current_user.station_ids)
        return False

    def _get_accessible_station_ids(self, requested_ids: Optional[List[int]]) -> Optional[List[int]]:
        if not self.current_user:
            return []
        if self.current_user.role in ["admin", "supervisor", "ops_coordinator"]:
            return requested_ids
        if self.current_user.role == "station_user":
            user_stations = self.current_user.station_ids or []
            if requested_ids:
                return list(set(user_stations) & set(requested_ids))
            return user_stations
        return []

    # ==================== AUDIT & RESPONSE CONVERSION ====================

    def _log_audit(self, layover_id: int, action: str, details: Optional[Dict[str, Any]] = None):
        from app.models.audit_log import AuditLog

        ip_address = None  # TODO: capture from request context if available
        audit = AuditLog(
            user_id=self.current_user.id if self.current_user else None,
            user_role=self.current_user.role if self.current_user else None,
            action_type=action,
            entity_type="layover",
            entity_id=layover_id,
            details=details,
            ip_address=ip_address,
        )
        self.db.add(audit)
        self.db.commit()

    def _to_basic_response(self, layover: Layover) -> LayoverResponse:
        # No cost fields in LayoverResponse; safe to validate from attributes
        return LayoverResponse.model_validate(layover, from_attributes=True)

    def _to_detail_response(self, layover: Layover) -> LayoverDetailResponse:
        # Start with attribute-based validation
        resp = LayoverDetailResponse.model_validate(layover, from_attributes=True)
        # Override cost fields (convert DB cents -> API decimals)
        resp.estimated_cost = _from_cents(layover.estimated_cost)
        resp.actual_cost = _from_cents(layover.actual_cost)
        return resp
