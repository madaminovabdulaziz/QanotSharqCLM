"""
Layover Repository - Data access layer for layover operations
Handles all database queries for layovers with filtering, pagination, and specialized queries
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session, joinedload

from app.models.layover import Layover, LayoverStatus, LayoverReason
from app.models.station import Station
from app.models.hotel import Hotel
from app.models.user import User


class LayoverRepository:
    """Repository for layover data access operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== CREATE ====================
    
    def create(self, layover: Layover) -> Layover:
        """
        Create a new layover request
        
        Args:
            layover: Layover model instance
            
        Returns:
            Created layover with generated ID
        """
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
        """
        Get layover by ID
        
        Args:
            layover_id: Layover ID
            load_relations: If True, eagerly load station, hotel, creator
            
        Returns:
            Layover or None if not found
        """
        query = self.db.query(Layover).filter(Layover.id == layover_id)
        
        if load_relations:
            query = query.options(
                joinedload(Layover.station),
                joinedload(Layover.hotel),
                joinedload(Layover.creator)
            )
        
        return query.first()
    
    def get_by_uuid(self, uuid: str) -> Optional[Layover]:
        """
        Get layover by UUID (for external references)
        
        Args:
            uuid: Layover UUID
            
        Returns:
            Layover or None if not found
        """
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
        order_direction: str = "desc"
    ) -> tuple[List[Layover], int]:
        """
        List layovers with comprehensive filtering and pagination
        
        Args:
            station_ids: Filter by station IDs (for station users)
            status: Filter by single status
            statuses: Filter by multiple statuses
            check_in_date_from: Filter by check-in date range start
            check_in_date_to: Filter by check-in date range end
            hotel_id: Filter by hotel
            created_by: Filter by creator user ID
            search_query: Search in route, hotel name, request ID
            skip: Pagination offset
            limit: Pagination limit
            order_by: Sort field (check_in_date, created_at, status)
            order_direction: Sort direction (asc, desc)
            
        Returns:
            Tuple of (layovers list, total count)
        """
        # Base query with eager loading
        query = self.db.query(Layover).options(
            joinedload(Layover.station),
            joinedload(Layover.hotel),
            joinedload(Layover.creator)
        )
        
        # Apply filters
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
        
        # Search query (route, hotel name, request ID)
        if search_query:
            search_filters = []
            
            # Search in route
            route_search = f"%{search_query}%"
            search_filters.append(Layover.origin_station_code.ilike(route_search))
            search_filters.append(Layover.destination_station_code.ilike(route_search))
            
            # Search in hotel name (join)
            search_filters.append(
                Layover.hotel.has(Hotel.name.ilike(route_search))
            )
            
            # Search by ID if numeric
            if search_query.isdigit():
                search_filters.append(Layover.id == int(search_query))
            
            filters.append(or_(*search_filters))
        
        # Apply all filters
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply ordering
        order_field = getattr(Layover, order_by, Layover.check_in_date)
        if order_direction.lower() == "desc":
            query = query.order_by(desc(order_field))
        else:
            query = query.order_by(order_field)
        
        # Apply pagination
        layovers = query.offset(skip).limit(limit).all()
        
        return layovers, total_count
    
    # ==================== UPDATE ====================
    
    def update(self, layover: Layover) -> Layover:
        """
        Update layover
        
        Args:
            layover: Layover model instance with updated fields
            
        Returns:
            Updated layover
        """
        self.db.commit()
        self.db.refresh(layover)
        return layover
    
    def update_status(
        self, 
        layover_id: int, 
        new_status: LayoverStatus,
        timestamp_field: Optional[str] = None
    ) -> Optional[Layover]:
        """
        Update layover status with automatic timestamp
        
        Args:
            layover_id: Layover ID
            new_status: New status
            timestamp_field: Optional timestamp field to update (e.g., 'sent_at', 'confirmed_at')
            
        Returns:
            Updated layover or None if not found
        """
        layover = self.get_by_id(layover_id)
        if not layover:
            return None
        
        layover.status = new_status
        
        # Update corresponding timestamp field
        if timestamp_field:
            setattr(layover, timestamp_field, datetime.utcnow())
        
        return self.update(layover)
    
    # ==================== DELETE ====================
    
    def delete(self, layover_id: int) -> bool:
        """
        Hard delete a layover (only for drafts)
        
        Args:
            layover_id: Layover ID
            
        Returns:
            True if deleted, False if not found
        """
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
        max_reminder_count: int = 2
    ) -> List[Layover]:
        """
        Get layovers that need reminder emails
        
        Args:
            reminder_hours: Hours since sent (e.g., 12 for 1st reminder, 24 for 2nd)
            max_reminder_count: Maximum reminder count (default 2)
            
        Returns:
            List of layovers needing reminders
        """
        threshold_time = datetime.utcnow() - timedelta(hours=reminder_hours)
        
        return self.db.query(Layover).filter(
            and_(
                Layover.status == LayoverStatus.PENDING,
                Layover.sent_at <= threshold_time,
                Layover.sent_at.isnot(None),
                Layover.reminder_count < max_reminder_count,
                or_(
                    Layover.last_reminder_sent_at.is_(None),
                    Layover.last_reminder_sent_at <= threshold_time
                ),
                Layover.reminders_paused == False  # Not paused for IRROPS
            )
        ).options(
            joinedload(Layover.hotel),
            joinedload(Layover.station)
        ).all()
    
    def get_escalation_candidates(
        self, 
        escalation_hours: int = 36
    ) -> List[Layover]:
        """
        Get layovers that need escalation (no hotel response after threshold)
        
        Args:
            escalation_hours: Hours since sent without response (default 36)
            
        Returns:
            List of layovers needing escalation
        """
        threshold_time = datetime.utcnow() - timedelta(hours=escalation_hours)
        
        return self.db.query(Layover).filter(
            and_(
                Layover.status == LayoverStatus.PENDING,
                Layover.sent_at <= threshold_time,
                Layover.sent_at.isnot(None),
                Layover.escalated_at.is_(None),  # Not already escalated
                Layover.reminders_paused == False  # Not paused
            )
        ).options(
            joinedload(Layover.hotel),
            joinedload(Layover.station),
            joinedload(Layover.creator)
        ).all()
    
    def get_upcoming_layovers(
        self,
        station_ids: Optional[List[int]] = None,
        days_ahead: int = 7
    ) -> List[Layover]:
        """
        Get upcoming layovers for proactive monitoring
        
        Args:
            station_ids: Filter by station IDs
            days_ahead: Look ahead days (default 7)
            
        Returns:
            List of upcoming layovers
        """
        today = datetime.utcnow().date()
        future_date = today + timedelta(days=days_ahead)
        
        query = self.db.query(Layover).filter(
            and_(
                Layover.check_in_date >= today,
                Layover.check_in_date <= future_date,
                Layover.status.in_([
                    LayoverStatus.CONFIRMED,
                    LayoverStatus.PENDING,
                    LayoverStatus.SENT
                ])
            )
        ).options(
            joinedload(Layover.station),
            joinedload(Layover.hotel)
        )
        
        if station_ids:
            query = query.filter(Layover.station_id.in_(station_ids))
        
        return query.order_by(Layover.check_in_date).all()
    
    def get_escalated_layovers(
        self,
        station_ids: Optional[List[int]] = None
    ) -> List[Layover]:
        """
        Get all escalated layovers (for dashboard alert widget)
        
        Args:
            station_ids: Filter by station IDs
            
        Returns:
            List of escalated layovers
        """
        query = self.db.query(Layover).filter(
            Layover.status == LayoverStatus.ESCALATED
        ).options(
            joinedload(Layover.hotel),
            joinedload(Layover.station)
        )
        
        if station_ids:
            query = query.filter(Layover.station_id.in_(station_ids))
        
        return query.order_by(desc(Layover.escalated_at)).all()
    
    def get_on_hold_layovers(
        self,
        station_ids: Optional[List[int]] = None
    ) -> List[Layover]:
        """
        Get all layovers on hold (for IRROPS monitoring)
        
        Args:
            station_ids: Filter by station IDs
            
        Returns:
            List of on-hold layovers
        """
        query = self.db.query(Layover).filter(
            Layover.status == LayoverStatus.ON_HOLD
        ).options(
            joinedload(Layover.station),
            joinedload(Layover.hotel)
        )
        
        if station_ids:
            query = query.filter(Layover.station_id.in_(station_ids))
        
        return query.order_by(desc(Layover.on_hold_at)).all()
    
    def get_by_trip_id(self, trip_id: str) -> List[Layover]:
        """
        Get all layovers in a multi-leg trip
        
        Args:
            trip_id: Trip identifier (e.g., 'AA-JAN25-P001')
            
        Returns:
            List of layovers in trip, ordered by sequence
        """
        return self.db.query(Layover).filter(
            Layover.trip_id == trip_id
        ).options(
            joinedload(Layover.station),
            joinedload(Layover.hotel)
        ).order_by(Layover.trip_sequence).all()
    
    # ==================== STATISTICS & METRICS ====================
    
    def get_dashboard_metrics(
        self,
        station_ids: Optional[List[int]] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get dashboard summary metrics
        
        Args:
            station_ids: Filter by station IDs
            date_from: Start date for metrics
            date_to: End date for metrics
            
        Returns:
            Dictionary with metrics
        """
        # Base query
        query = self.db.query(Layover)
        
        # Apply filters
        filters = []
        if station_ids:
            filters.append(Layover.station_id.in_(station_ids))
        if date_from:
            filters.append(Layover.created_at >= date_from)
        if date_to:
            filters.append(Layover.created_at <= date_to)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Total count
        total = query.count()
        
        # Count by status
        confirmed = query.filter(Layover.status == LayoverStatus.CONFIRMED).count()
        pending = query.filter(Layover.status == LayoverStatus.PENDING).count()
        escalated = query.filter(Layover.status == LayoverStatus.ESCALATED).count()
        on_hold = query.filter(Layover.status == LayoverStatus.ON_HOLD).count()
        declined = query.filter(Layover.status == LayoverStatus.DECLINED).count()
        completed = query.filter(Layover.status == LayoverStatus.COMPLETED).count()
        
        # Calculate confirmation rate
        confirmation_rate = (confirmed / total * 100) if total > 0 else 0
        
        # Average response time (hours) for confirmed layovers
        avg_response_time = self.db.query(
            func.avg(
                func.timestampdiff(
                    'HOUR',
                    Layover.sent_at,
                    Layover.confirmed_at
                )
            )
        ).filter(
            and_(
                Layover.status == LayoverStatus.CONFIRMED,
                Layover.sent_at.isnot(None),
                Layover.confirmed_at.isnot(None),
                *filters
            )
        ).scalar() or 0
        
        return {
            "total_requests": total,
            "confirmed_count": confirmed,
            "pending_count": pending,
            "escalated_count": escalated,
            "on_hold_count": on_hold,
            "declined_count": declined,
            "completed_count": completed,
            "confirmation_rate": round(confirmation_rate, 2),
            "avg_response_hours": round(avg_response_time, 2)
        }
    
    def get_station_performance(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics by station
        
        Args:
            date_from: Start date
            date_to: End date
            
        Returns:
            List of station performance dictionaries
        """
        # Base query with station join
        query = self.db.query(
            Station.id,
            Station.name,
            Station.code,
            func.count(Layover.id).label('total_requests'),
            func.sum(
                func.if_(Layover.status == LayoverStatus.CONFIRMED, 1, 0)
            ).label('confirmed_count'),
            func.avg(
                func.if_(
                    and_(
                        Layover.sent_at.isnot(None),
                        Layover.confirmed_at.isnot(None)
                    ),
                    func.timestampdiff('HOUR', Layover.sent_at, Layover.confirmed_at),
                    None
                )
            ).label('avg_response_hours'),
            func.sum(
                func.if_(Layover.status == LayoverStatus.ESCALATED, 1, 0)
            ).label('escalated_count')
        ).join(
            Layover, Station.id == Layover.station_id
        )
        
        # Apply date filters
        if date_from:
            query = query.filter(Layover.created_at >= date_from)
        if date_to:
            query = query.filter(Layover.created_at <= date_to)
        
        # Group by station
        results = query.group_by(Station.id).all()
        
        # Format results
        performance = []
        for row in results:
            total = row.total_requests or 0
            confirmed = row.confirmed_count or 0
            confirmation_rate = (confirmed / total * 100) if total > 0 else 0
            
            performance.append({
                "station_id": row.id,
                "station_name": row.name,
                "station_code": row.code,
                "total_requests": total,
                "confirmed_count": confirmed,
                "confirmation_rate": round(confirmation_rate, 2),
                "avg_response_hours": round(row.avg_response_hours or 0, 2),
                "escalated_count": row.escalated_count or 0
            })
        
        return sorted(performance, key=lambda x: x['confirmation_rate'], reverse=True)
    
    def get_hotel_performance(
        self,
        station_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_requests: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get performance metrics by hotel
        
        Args:
            station_id: Filter by station
            date_from: Start date
            date_to: End date
            min_requests: Minimum requests to include hotel (default 3)
            
        Returns:
            List of hotel performance dictionaries
        """
        # Base query with hotel join
        query = self.db.query(
            Hotel.id,
            Hotel.name,
            Station.name.label('station_name'),
            func.count(Layover.id).label('total_requests'),
            func.sum(
                func.if_(Layover.status == LayoverStatus.CONFIRMED, 1, 0)
            ).label('confirmed_count'),
            func.sum(
                func.if_(Layover.status == LayoverStatus.DECLINED, 1, 0)
            ).label('declined_count'),
            func.avg(
                func.if_(
                    and_(
                        Layover.sent_at.isnot(None),
                        Layover.confirmed_at.isnot(None)
                    ),
                    func.timestampdiff('HOUR', Layover.sent_at, Layover.confirmed_at),
                    None
                )
            ).label('avg_response_hours'),
            func.max(Layover.confirmed_at).label('last_response_date')
        ).join(
            Layover, Hotel.id == Layover.hotel_id
        ).join(
            Station, Hotel.station_id == Station.id
        )
        
        # Apply filters
        if station_id:
            query = query.filter(Hotel.station_id == station_id)
        if date_from:
            query = query.filter(Layover.created_at >= date_from)
        if date_to:
            query = query.filter(Layover.created_at <= date_to)
        
        # Group by hotel
        query = query.group_by(Hotel.id)
        
        # Filter by minimum requests
        query = query.having(func.count(Layover.id) >= min_requests)
        
        results = query.all()
        
        # Format results
        performance = []
        for row in results:
            total = row.total_requests or 0
            confirmed = row.confirmed_count or 0
            declined = row.declined_count or 0
            confirmation_rate = (confirmed / total * 100) if total > 0 else 0
            decline_rate = (declined / total * 100) if total > 0 else 0
            
            # Rating: Excellent (>90% confirm, <12h response), Good, Average, Poor
            rating = "poor"
            if confirmation_rate > 90 and (row.avg_response_hours or 999) < 12:
                rating = "excellent"
            elif confirmation_rate > 80 and (row.avg_response_hours or 999) < 24:
                rating = "good"
            elif confirmation_rate > 70:
                rating = "average"
            
            performance.append({
                "hotel_id": row.id,
                "hotel_name": row.name,
                "station_name": row.station_name,
                "total_requests": total,
                "confirmed_count": confirmed,
                "declined_count": declined,
                "confirmation_rate": round(confirmation_rate, 2),
                "decline_rate": round(decline_rate, 2),
                "avg_response_hours": round(row.avg_response_hours or 0, 2),
                "last_response_date": row.last_response_date,
                "rating": rating
            })
        
        return sorted(performance, key=lambda x: x['confirmation_rate'], reverse=True)