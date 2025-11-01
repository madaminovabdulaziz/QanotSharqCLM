"""
Hotel Repository - Database Access Layer
Handles all database operations for Hotel entity.
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.hotel import Hotel
from app.models.station import Station
from app.schemas.hotel import HotelCreate, HotelUpdate


class HotelRepository:
    """
    Repository for Hotel database operations.
    
    Provides clean separation between business logic and data access.
    All database queries for hotels go through this repository.
    """
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    # ========================================
    # CREATE
    # ========================================
    
    def create(self, hotel_data: HotelCreate, created_by: Optional[int] = None) -> Hotel:
        """
        Create a new hotel.
        
        Args:
            hotel_data: Validated hotel creation data
            created_by: User ID of creator (optional)
            
        Returns:
            Created hotel instance
        """
        # Convert Pydantic model to dict
        data_dict = hotel_data.model_dump()
        
        # Add created_by if provided
        if created_by:
            data_dict['created_by'] = created_by
        
        # Convert performance_metrics to dict if provided (should use default)
        if 'performance_metrics' not in data_dict or data_dict['performance_metrics'] is None:
            data_dict['performance_metrics'] = {
                "total_requests": 0,
                "confirmed_count": 0,
                "declined_count": 0,
                "avg_response_hours": 0.0,
                "last_updated": None
            }
        
        # Create hotel instance
        hotel = Hotel(**data_dict)
        
        self.db.add(hotel)
        self.db.commit()
        self.db.refresh(hotel)
        
        return hotel
    
    # ========================================
    # READ
    # ========================================
    
    def get_by_id(self, hotel_id: int, include_station: bool = False) -> Optional[Hotel]:
        """
        Get hotel by ID.
        
        Args:
            hotel_id: Hotel ID
            include_station: Whether to eagerly load station relationship
            
        Returns:
            Hotel instance or None if not found
        """
        query = self.db.query(Hotel).filter(Hotel.id == hotel_id)
        
        if include_station:
            query = query.options(joinedload(Hotel.station))
        
        return query.first()
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        station_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        include_station: bool = False
    ) -> tuple[List[Hotel], int]:
        """
        Get all hotels with filtering and pagination.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            station_id: Filter by station ID (None = all stations)
            is_active: Filter by active status (None = all)
            search: Search in name, city, or email (case-insensitive)
            include_station: Whether to eagerly load station relationship
            
        Returns:
            Tuple of (list of hotels, total count)
        """
        # Base query
        query = self.db.query(Hotel)
        
        # Apply filters
        filters = []
        
        if station_id is not None:
            filters.append(Hotel.station_id == station_id)
        
        if is_active is not None:
            filters.append(Hotel.is_active == is_active)
        
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    Hotel.name.ilike(search_pattern),
                    Hotel.city.ilike(search_pattern),
                    Hotel.email.ilike(search_pattern)
                )
            )
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Eagerly load station if requested
        if include_station:
            query = query.options(joinedload(Hotel.station))
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination and ordering
        hotels = query.order_by(Hotel.name).offset(skip).limit(limit).all()
        
        return hotels, total
    
    def get_by_station(
        self, 
        station_id: int, 
        is_active: Optional[bool] = True
    ) -> List[Hotel]:
        """
        Get all hotels for a specific station.
        
        Args:
            station_id: Station ID
            is_active: Filter by active status (None = all)
            
        Returns:
            List of hotels at that station
        """
        query = self.db.query(Hotel).filter(Hotel.station_id == station_id)
        
        if is_active is not None:
            query = query.filter(Hotel.is_active == is_active)
        
        return query.order_by(Hotel.name).all()
    
    def get_by_email(self, email: str) -> Optional[Hotel]:
        """
        Get hotel by primary email (case-insensitive).
        
        Args:
            email: Hotel email address
            
        Returns:
            Hotel instance or None if not found
        """
        return self.db.query(Hotel).filter(
            func.lower(Hotel.email) == email.lower()
        ).first()
    
    def get_with_contract(self, station_id: Optional[int] = None) -> List[Hotel]:
        """
        Get hotels with active contract rates.
        
        Args:
            station_id: Optional filter by station
            
        Returns:
            List of hotels with contract_type != 'ad_hoc' and valid contracts
        """
        query = self.db.query(Hotel).filter(
            Hotel.is_active == True,
            Hotel.contract_type != 'ad_hoc',
            Hotel.contract_rate.isnot(None)
        )
        
        if station_id:
            query = query.filter(Hotel.station_id == station_id)
        
        # Filter by valid contract (not expired)
        query = query.filter(
            or_(
                Hotel.contract_valid_until.is_(None),  # No expiry
                Hotel.contract_valid_until >= datetime.now().date()  # Not expired
            )
        )
        
        return query.order_by(Hotel.name).all()
    
    # ========================================
    # UPDATE
    # ========================================
    
    def update(self, hotel_id: int, hotel_data: HotelUpdate) -> Optional[Hotel]:
        """
        Update an existing hotel.
        
        Args:
            hotel_id: Hotel ID to update
            hotel_data: Validated update data (only provided fields)
            
        Returns:
            Updated hotel instance or None if not found
        """
        hotel = self.get_by_id(hotel_id)
        if not hotel:
            return None
        
        # Get update data, excluding unset fields
        update_data = hotel_data.model_dump(exclude_unset=True)
        
        # Update fields
        for field, value in update_data.items():
            setattr(hotel, field, value)
        
        self.db.commit()
        self.db.refresh(hotel)
        
        return hotel
    
    def update_performance_metrics(
        self, 
        hotel_id: int, 
        metrics: Dict[str, Any]
    ) -> Optional[Hotel]:
        """
        Update hotel performance metrics (called by nightly cron job).
        
        Args:
            hotel_id: Hotel ID
            metrics: Performance metrics dict
            
        Returns:
            Updated hotel or None if not found
        """
        hotel = self.get_by_id(hotel_id)
        if not hotel:
            return None
        
        # Add last_updated timestamp
        metrics['last_updated'] = datetime.now().isoformat()
        
        hotel.performance_metrics = metrics
        
        self.db.commit()
        self.db.refresh(hotel)
        
        return hotel
    
    # ========================================
    # DELETE
    # ========================================
    
    def delete(self, hotel_id: int) -> bool:
        """
        Delete a hotel (hard delete).
        
        Note: Will fail if hotel has associated layovers
        due to foreign key constraints (ON DELETE RESTRICT).
        
        Args:
            hotel_id: Hotel ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        hotel = self.get_by_id(hotel_id)
        if not hotel:
            return False
        
        self.db.delete(hotel)
        self.db.commit()
        
        return True
    
    def soft_delete(self, hotel_id: int) -> Optional[Hotel]:
        """
        Soft delete a hotel (set is_active = False).
        
        Preferred over hard delete to preserve historical data.
        
        Args:
            hotel_id: Hotel ID to deactivate
            
        Returns:
            Deactivated hotel or None if not found
        """
        hotel = self.get_by_id(hotel_id)
        if not hotel:
            return None
        
        hotel.is_active = False
        
        self.db.commit()
        self.db.refresh(hotel)
        
        return hotel
    
    # ========================================
    # VALIDATION HELPERS
    # ========================================
    
    def email_exists(self, email: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if a hotel email already exists (case-insensitive).
        
        Args:
            email: Email to check
            exclude_id: Hotel ID to exclude from check (for updates)
            
        Returns:
            True if email exists, False otherwise
        """
        query = self.db.query(Hotel).filter(
            func.lower(Hotel.email) == email.lower()
        )
        
        if exclude_id:
            query = query.filter(Hotel.id != exclude_id)
        
        return query.first() is not None
    
    def count_by_station(self, station_id: int, is_active: Optional[bool] = True) -> int:
        """
        Count hotels at a specific station.
        
        Args:
            station_id: Station ID
            is_active: Filter by active status (None = all)
            
        Returns:
            Count of hotels
        """
        query = self.db.query(Hotel).filter(Hotel.station_id == station_id)
        
        if is_active is not None:
            query = query.filter(Hotel.is_active == is_active)
        
        return query.count()
    
    # ========================================
    # PERFORMANCE & REPORTING
    # ========================================
    
    def get_top_performers(
        self, 
        station_id: Optional[int] = None,
        limit: int = 10
    ) -> List[Hotel]:
        """
        Get top performing hotels by confirmation rate.
        
        Args:
            station_id: Optional filter by station
            limit: Number of hotels to return
            
        Returns:
            List of top performing hotels
        """
        query = self.db.query(Hotel).filter(Hotel.is_active == True)
        
        if station_id:
            query = query.filter(Hotel.station_id == station_id)
        
        # Filter hotels with at least 3 requests (statistical significance)
        # Ordering by confirmation rate calculated from performance_metrics JSON
        hotels = query.all()
        
        # Calculate confirmation rate and sort
        hotels_with_rate = []
        for hotel in hotels:
            metrics = hotel.performance_metrics or {}
            total = metrics.get('total_requests', 0)
            confirmed = metrics.get('confirmed_count', 0)
            
            if total >= 3:  # Minimum 3 requests for inclusion
                rate = (confirmed / total * 100) if total > 0 else 0
                hotels_with_rate.append((hotel, rate))
        
        # Sort by confirmation rate (descending)
        hotels_with_rate.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N hotels
        return [hotel for hotel, rate in hotels_with_rate[:limit]]
    
    def get_low_performers(
        self, 
        station_id: Optional[int] = None,
        threshold: float = 70.0,
        limit: int = 10
    ) -> List[Hotel]:
        """
        Get hotels with confirmation rate below threshold.
        
        Args:
            station_id: Optional filter by station
            threshold: Confirmation rate threshold (default 70%)
            limit: Number of hotels to return
            
        Returns:
            List of low performing hotels
        """
        query = self.db.query(Hotel).filter(Hotel.is_active == True)
        
        if station_id:
            query = query.filter(Hotel.station_id == station_id)
        
        hotels = query.all()
        
        # Calculate confirmation rate and filter
        low_performers = []
        for hotel in hotels:
            metrics = hotel.performance_metrics or {}
            total = metrics.get('total_requests', 0)
            confirmed = metrics.get('confirmed_count', 0)
            
            if total >= 5:  # Minimum 5 requests for meaningful data
                rate = (confirmed / total * 100) if total > 0 else 0
                if rate < threshold:
                    low_performers.append((hotel, rate))
        
        # Sort by confirmation rate (ascending - worst first)
        low_performers.sort(key=lambda x: x[1])
        
        return [hotel for hotel, rate in low_performers[:limit]]
    
    # ========================================
    # BULK OPERATIONS
    # ========================================
    
    def bulk_activate(self, hotel_ids: List[int]) -> int:
        """
        Activate multiple hotels at once.
        
        Args:
            hotel_ids: List of hotel IDs to activate
            
        Returns:
            Number of hotels activated
        """
        count = self.db.query(Hotel).filter(
            Hotel.id.in_(hotel_ids)
        ).update(
            {"is_active": True},
            synchronize_session=False
        )
        
        self.db.commit()
        return count
    
    def bulk_deactivate(self, hotel_ids: List[int]) -> int:
        """
        Deactivate multiple hotels at once.
        
        Args:
            hotel_ids: List of hotel IDs to deactivate
            
        Returns:
            Number of hotels deactivated
        """
        count = self.db.query(Hotel).filter(
            Hotel.id.in_(hotel_ids)
        ).update(
            {"is_active": False},
            synchronize_session=False
        )
        
        self.db.commit()
        return count