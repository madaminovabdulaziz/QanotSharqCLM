"""
Layover Repository - Data access layer for layover operations
SQLAlchemy 2.x compatible, MySQL-safe, and includes HH:MM formatting for response time.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import (
    and_,
    or_,
    func,
    desc,
    select,
    case,
    literal_column,
)
from sqlalchemy.orm import Session, joinedload

from app.models.layover import Layover, LayoverStatus
from app.models.station import Station
from app.models.hotel import Hotel


def _seconds_to_hhmm(total_seconds: Optional[float]) -> str:
    """
    Convert seconds (possibly None) to 'HH:MM' string.
    Handles large hour counts without day wrap.
    """
    if not total_seconds or total_seconds <= 0:
        return "00:00"
    total_seconds = int(total_seconds)
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}"


class LayoverRepository:
    """Repository for layover data access operations"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create(self, layover: Layover) -> Layover:
        self.db.add(layover)
        self.db.commit()
        self.db.refresh(layover)
        return layover

    # ==================== READ ====================

    def get_by_id(
        self,
        layover_id: int,
        load_relations: bool = False
    ) -> Optional[Layover]:
        query = self.db.query(Layover).filter(Layover.id == layover_id)

        if load_relations:
            query = query.options(
                joinedload(Layover.station),
                joinedload(Layover.hotel),
                joinedload(Layover.creator),
            )

        return query.first()

    def get_by_uuid(self, uuid: str) -> Optional[Layover]:
        return self.db.query(Layover).filter(Layover.uuid == uuid).first()

    def list_layovers(
        self,
        station_ids: Optional[List[int]] = None,
        status: Optional[LayoverStatus] = None,
        statuses: Optional[List[LayoverStatus]] = None,
        check_in_date_from: Optional[datetime] = None,
        check_in_date_to: Optional[datetime] = None,
        hotel_id: Optional[int] = None,
        created_by: Optional[int] = None,
        search_query: Optional[str] = None,
        skip: int = 0,
        limit: int = 25,
        order_by: str = "check_in_date",
        order_direction: str = "desc",
    ) -> Tuple[List[Layover], int]:
        # Base query with eager loading
        query = self.db.query(Layover).options(
            joinedload(Layover.station),
            joinedload(Layover.hotel),
            joinedload(Layover.creator),
        )

        filters = []

        if station_ids:
            filters.append(Layover.station_id.in_(station_ids))

        if status:
            filters.append(Layover.status == status)

        if statuses:
            filters.append(Layover.status.in_(statuses))

        if check_in_date_from:
            filters.append(Layover.check_in_date >= check_in_date_from.date())

        if check_in_date_to:
            filters.append(Layover.check_in_date <= check_in_date_to.date())

        if hotel_id:
            filters.append(Layover.hotel_id == hotel_id)

        if created_by:
            filters.append(Layover.created_by == created_by)

        if search_query:
            route_search = f"%{search_query}%"
            search_filters = [
                Layover.origin_station_code.ilike(route_search),
                Layover.destination_station_code.ilike(route_search),
                Layover.hotel.has(Hotel.name.ilike(route_search)),
            ]
            if search_query.isdigit():
                search_filters.append(Layover.id == int(search_query))
            filters.append(or_(*search_filters))

        if filters:
            query = query.filter(and_(*filters))

        total_count = query.count()

        order_field = getattr(Layover, order_by, Layover.check_in_date)
        if order_direction.lower() == "desc":
            query = query.order_by(desc(order_field))
        else:
            query = query.order_by(order_field)

        layovers = query.offset(skip).limit(limit).all()
        return layovers, total_count

    # ==================== UPDATE ====================

    def update(self, layover: Layover) -> Layover:
        self.db.commit()
        self.db.refresh(layover)
        return layover

    def update_status(
        self,
        layover_id: int,
        new_status: LayoverStatus,
        timestamp_field: Optional[str] = None,
    ) -> Optional[Layover]:
        layover = self.get_by_id(layover_id)
        if not layover:
            return None

        layover.status = new_status

        if timestamp_field:
            setattr(layover, timestamp_field, datetime.utcnow())

        return self.update(layover)

    # ==================== DELETE ====================

    def delete(self, layover_id: int) -> bool:
        layover = self.get_by_id(layover_id)
        if not layover:
            return False
        self.db.delete(layover)
        self.db.commit()
        return True

    # ==================== SPECIALIZED QUERIES ====================

    def get_pending_reminders(
        self,
        reminder_hours: int,
        max_reminder_count: int = 2,
    ) -> List[Layover]:
        threshold_time = datetime.utcnow() - timedelta(hours=reminder_hours)

        return (
            self.db.query(Layover)
            .filter(
                and_(
                    Layover.status == LayoverStatus.PENDING,
                    Layover.sent_at <= threshold_time,
                    Layover.sent_at.isnot(None),
                    Layover.reminder_count < max_reminder_count,
                    or_(
                        Layover.last_reminder_sent_at.is_(None),
                        Layover.last_reminder_sent_at <= threshold_time,
                    ),
                    Layover.reminders_paused == False,
                )
            )
            .options(joinedload(Layover.hotel), joinedload(Layover.station))
            .all()
        )

    def get_escalation_candidates(
        self,
        escalation_hours: int = 36,
    ) -> List[Layover]:
        threshold_time = datetime.utcnow() - timedelta(hours=escalation_hours)

        return (
            self.db.query(Layover)
            .filter(
                and_(
                    Layover.status == LayoverStatus.PENDING,
                    Layover.sent_at <= threshold_time,
                    Layover.sent_at.isnot(None),
                    Layover.escalated_at.is_(None),
                    Layover.reminders_paused == False,
                )
            )
            .options(
                joinedload(Layover.hotel),
                joinedload(Layover.station),
                joinedload(Layover.creator),
            )
            .all()
        )

    def get_upcoming_layovers(
        self,
        station_ids: Optional[List[int]] = None,
        days_ahead: int = 7,
    ) -> List[Layover]:
        today = datetime.utcnow().date()
        future_date = today + timedelta(days=days_ahead)

        query = (
            self.db.query(Layover)
            .filter(
                and_(
                    Layover.check_in_date >= today,
                    Layover.check_in_date <= future_date,
                    Layover.status.in_(
                        [
                            LayoverStatus.CONFIRMED,
                            LayoverStatus.PENDING,
                            LayoverStatus.SENT,
                        ]
                    ),
                )
            )
            .options(joinedload(Layover.station), joinedload(Layover.hotel))
        )

        if station_ids:
            query = query.filter(Layover.station_id.in_(station_ids))

        return query.order_by(Layover.check_in_date).all()

    def get_escalated_layovers(
        self,
        station_ids: Optional[List[int]] = None,
    ) -> List[Layover]:
        query = (
            self.db.query(Layover)
            .filter(Layover.status == LayoverStatus.ESCALATED)
            .options(joinedload(Layover.hotel), joinedload(Layover.station))
        )

        if station_ids:
            query = query.filter(Layover.station_id.in_(station_ids))

        return query.order_by(desc(Layover.escalated_at)).all()

    def get_on_hold_layovers(
        self,
        station_ids: Optional[List[int]] = None,
    ) -> List[Layover]:
        query = (
            self.db.query(Layover)
            .filter(Layover.status == LayoverStatus.ON_HOLD)
            .options(joinedload(Layover.station), joinedload(Layover.hotel))
        )

        if station_ids:
            query = query.filter(Layover.station_id.in_(station_ids))

        return query.order_by(desc(Layover.on_hold_at)).all()

    def get_by_trip_id(self, trip_id: str) -> List[Layover]:
        return (
            self.db.query(Layover)
            .filter(Layover.trip_id == trip_id)
            .options(joinedload(Layover.station), joinedload(Layover.hotel))
            .order_by(Layover.trip_sequence)
            .all()
        )

    # ==================== STATISTICS & METRICS ====================
    # Using modern select() + case() + literal_column for MySQL compatibility.

    def get_dashboard_metrics(
        self,
        station_ids: Optional[List[int]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        # Base selectable
        base_filters = []
        if station_ids:
            base_filters.append(Layover.station_id.in_(station_ids))
        if date_from:
            base_filters.append(Layover.created_at >= date_from)
        if date_to:
            base_filters.append(Layover.created_at <= date_to)

        # Total
        total_q = select(func.count()).select_from(Layover)
        if base_filters:
            total_q = total_q.where(and_(*base_filters))
        total = self.db.execute(total_q).scalar() or 0

        # Counts by status
        def _count_status(status: LayoverStatus) -> int:
            q = select(func.count()).select_from(Layover).where(Layover.status == status)
            if base_filters:
                q = q.where(and_(*base_filters))
            return self.db.execute(q).scalar() or 0

        confirmed = _count_status(LayoverStatus.CONFIRMED)
        pending = _count_status(LayoverStatus.PENDING)
        escalated = _count_status(LayoverStatus.ESCALATED)
        on_hold = _count_status(LayoverStatus.ON_HOLD)
        declined = _count_status(LayoverStatus.DECLINED)
        completed = _count_status(LayoverStatus.COMPLETED)

        confirmation_rate = (confirmed / total * 100) if total > 0 else 0.0

        # Average response time (in seconds), for CONFIRMED only, with non-null sent/confirmed
        avg_seconds_stmt = (
            select(
                func.avg(
                    func.timestampdiff(
                        # Use SECOND to get precise duration, then format to HH:MM
                        literal_column("SECOND"),
                        Layover.sent_at,
                        Layover.confirmed_at,
                    )
                )
            )
            .select_from(Layover)
            .where(
                and_(
                    Layover.status == LayoverStatus.CONFIRMED,
                    Layover.sent_at.isnot(None),
                    Layover.confirmed_at.isnot(None),
                    *(base_filters or []),
                )
            )
        )
        avg_seconds = self.db.execute(avg_seconds_stmt).scalar()
        avg_seconds = float(avg_seconds) if avg_seconds is not None else 0.0

        # Provide both (float hours and HH:MM)
        avg_hours = round(avg_seconds / 3600.0, 2) if avg_seconds else 0.0
        avg_hhmm = _seconds_to_hhmm(avg_seconds)

        return {
            "total_requests": total,
            "confirmed_count": confirmed,
            "pending_count": pending,
            "escalated_count": escalated,
            "on_hold_count": on_hold,
            "declined_count": declined,
            "completed_count": completed,
            "confirmation_rate": round(confirmation_rate, 2),
            "avg_response_hours": avg_hours,       # keep existing numeric field
            "avg_response_hhmm": avg_hhmm,         # NEW: HH:MM format per your choice C
        }

    def get_station_performance(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        # Build base selectable from Station + Layover join
        # Use case() instead of func.if_
        confirmed_case = case((Layover.status == LayoverStatus.CONFIRMED, 1), else_=0)
        escalated_case = case((Layover.status == LayoverStatus.ESCALATED, 1), else_=0)

        avg_seconds_expr = func.avg(
            func.timestampdiff(
                literal_column("SECOND"),
                Layover.sent_at,
                Layover.confirmed_at,
            )
        )

        stmt = (
            select(
                Station.id.label("station_id"),
                Station.name.label("station_name"),
                Station.code.label("station_code"),
                func.count(Layover.id).label("total_requests"),
                func.sum(confirmed_case).label("confirmed_count"),
                # Only average where both timestamps present (MySQL IF -> SQLA case)
                func.avg(
                    case(
                        (
                            and_(
                                Layover.sent_at.isnot(None),
                                Layover.confirmed_at.isnot(None),
                            ),
                            func.timestampdiff(
                                literal_column("SECOND"),
                                Layover.sent_at,
                                Layover.confirmed_at,
                            ),
                        ),
                        else_=None,
                    )
                ).label("avg_seconds"),
                func.sum(escalated_case).label("escalated_count"),
            )
            .select_from(Station)
            .join(Layover, Station.id == Layover.station_id)
        )

        if date_from:
            stmt = stmt.where(Layover.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Layover.created_at <= date_to)

        stmt = stmt.group_by(Station.id)

        rows = self.db.execute(stmt).all()

        performance: List[Dict[str, Any]] = []
        for row in rows:
            total = row.total_requests or 0
            confirmed = row.confirmed_count or 0
            confirmation_rate = (confirmed / total * 100) if total > 0 else 0.0

            avg_seconds = float(row.avg_seconds) if row.avg_seconds is not None else 0.0
            avg_hours = round(avg_seconds / 3600.0, 2) if avg_seconds else 0.0
            avg_hhmm = _seconds_to_hhmm(avg_seconds)

            performance.append(
                {
                    "station_id": row.station_id,
                    "station_name": row.station_name,
                    "station_code": row.station_code,
                    "total_requests": total,
                    "confirmed_count": confirmed,
                    "confirmation_rate": round(confirmation_rate, 2),
                    "avg_response_hours": avg_hours,   # numeric for existing schema
                    "avg_response_hhmm": avg_hhmm,     # NEW HH:MM for UI
                    "escalated_count": row.escalated_count or 0,
                }
            )

        return sorted(performance, key=lambda x: x["confirmation_rate"], reverse=True)

    def get_hotel_performance(
        self,
        station_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_requests: int = 3,
    ) -> List[Dict[str, Any]]:
        confirmed_case = case((Layover.status == LayoverStatus.CONFIRMED, 1), else_=0)
        declined_case = case((Layover.status == LayoverStatus.DECLINED, 1), else_=0)

        avg_seconds_case = case(
            (
                and_(
                    Layover.sent_at.isnot(None),
                    Layover.confirmed_at.isnot(None),
                ),
                func.timestampdiff(
                    literal_column("SECOND"),
                    Layover.sent_at,
                    Layover.confirmed_at,
                ),
            ),
            else_=None,
        )

        stmt = (
            select(
                Hotel.id.label("hotel_id"),
                Hotel.name.label("hotel_name"),
                Station.name.label("station_name"),
                func.count(Layover.id).label("total_requests"),
                func.sum(confirmed_case).label("confirmed_count"),
                func.sum(declined_case).label("declined_count"),
                func.avg(avg_seconds_case).label("avg_seconds"),
                func.max(Layover.confirmed_at).label("last_response_date"),
            )
            .select_from(Hotel)
            .join(Layover, Hotel.id == Layover.hotel_id)
            .join(Station, Hotel.station_id == Station.id)
        )

        if station_id:
            stmt = stmt.where(Hotel.station_id == station_id)
        if date_from:
            stmt = stmt.where(Layover.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Layover.created_at <= date_to)

        stmt = stmt.group_by(Hotel.id)
        stmt = stmt.having(func.count(Layover.id) >= min_requests)

        rows = self.db.execute(stmt).all()

        performance: List[Dict[str, Any]] = []
        for row in rows:
            total = row.total_requests or 0
            confirmed = row.confirmed_count or 0
            declined = row.declined_count or 0

            confirmation_rate = (confirmed / total * 100) if total > 0 else 0.0
            decline_rate = (declined / total * 100) if total > 0 else 0.0

            avg_seconds = float(row.avg_seconds) if row.avg_seconds is not None else 0.0
            avg_hours = round(avg_seconds / 3600.0, 2) if avg_seconds else 0.0
            avg_hhmm = _seconds_to_hhmm(avg_seconds)

            # Rating rules unchanged, using numeric hours for logic
            rating = "poor"
            if confirmation_rate > 90 and avg_hours < 12:
                rating = "excellent"
            elif confirmation_rate > 80 and avg_hours < 24:
                rating = "good"
            elif confirmation_rate > 70:
                rating = "average"

            performance.append(
                {
                    "hotel_id": row.hotel_id,
                    "hotel_name": row.hotel_name,
                    "station_name": row.station_name,
                    "total_requests": total,
                    "confirmed_count": confirmed,
                    "declined_count": declined,
                    "confirmation_rate": round(confirmation_rate, 2),
                    "decline_rate": round(decline_rate, 2),
                    "avg_response_hours": avg_hours,   # numeric kept
                    "avg_response_hhmm": avg_hhmm,     # NEW HH:MM
                    "last_response_date": row.last_response_date,
                    "rating": rating,
                }
            )

        return sorted(performance, key=lambda x: x["confirmation_rate"], reverse=True)
