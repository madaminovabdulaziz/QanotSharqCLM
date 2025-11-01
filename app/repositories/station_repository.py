"""
Station Repository - Database Access Layer
Handles all database operations for Station entity.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any
from app.models.station import Station
from app.schemas.station import StationCreate, StationUpdate


class StationRepository:
    """
    Repository for Station database operations.
    
    Provides clean separation between business logic and data access.
    All database queries for stations go through this repository.
    """
    
    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db
    
    # ========================================
    # CREATE
    # ========================================
    
    def create(self, station_data: StationCreate) -> Station:
        """
        Create a new station.
        
        Args:
            station_data: Validated station creation data
            
        Returns:
            Created station instance
        """
        # Convert Pydantic model to dict
        data_dict = station_data.model_dump()
        
        # Convert reminder_config to dict if provided
        if data_dict.get('reminder_config'):
            data_dict['reminder_config'] = station_data.reminder_config.model_dump()
        
        # Create station instance
        station = Station(**data_dict)
        
        self.db.add(station)
        self.db.commit()
        self.db.refresh(station)
        
        return station
    
    # ========================================
    # READ
    # ========================================
    
    def get_by_id(self, station_id: int) -> Optional[Station]:
        """
        Get station by ID.
        
        Args:
            station_id: Station ID
            
        Returns:
            Station instance or None if not found
        """
        return self.db.query(Station).filter(Station.id == station_id).first()
    
    def get_by_code(self, code: str) -> Optional[Station]:
        """
        Get station by airport code (case-insensitive).
        
        Args:
            code: Airport code (e.g., 'LHR', 'JFK')
            
        Returns:
            Station instance or None if not found
        """
        return self.db.query(Station).filter(
            func.upper(Station.code) == code.upper()
        ).first()
    
    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> tuple[List[Station], int]:
        """
        Get all stations with filtering and pagination.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            is_active: Filter by active status (None = all)
            search: Search in code, name, or city (case-insensitive)
            
        Returns:
            Tuple of (list of stations, total count)
        """
        # Base query
        query = self.db.query(Station)
        
        # Apply filters
        filters = []
        
        if is_active is not None:
            filters.append(Station.is_active == is_active)
        
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    Station.code.ilike(search_pattern),
                    Station.name.ilike(search_pattern),
                    Station.city.ilike(search_pattern)
                )
            )
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination and ordering
        stations = query.order_by(Station.name).offset(skip).limit(limit).all()
        
        return stations, total
    
    def get_active_stations(self) -> List[Station]:
        """
        Get all active stations (for dropdowns, selects).
        
        Returns:
            List of active stations ordered by name
        """
        return self.db.query(Station).filter(
            Station.is_active == True
        ).order_by(Station.name).all()
    
    def get_by_timezone(self, timezone: str) -> List[Station]:
        """
        Get stations by timezone (useful for reminder scheduling).
        
        Args:
            timezone: IANA timezone (e.g., 'Europe/London')
            
        Returns:
            List of stations in that timezone
        """
        return self.db.query(Station).filter(
            Station.timezone == timezone,
            Station.is_active == True
        ).all()
    
    # ========================================
    # UPDATE
    # ========================================
    
    def update(self, station_id: int, station_data: StationUpdate) -> Optional[Station]:
        """
        Update an existing station.
        
        Args:
            station_id: Station ID to update
            station_data: Validated update data (only provided fields)
            
        Returns:
            Updated station instance or None if not found
        """
        station = self.get_by_id(station_id)
        if not station:
            return None
        
        # Get update data, excluding unset fields
        update_data = station_data.model_dump(exclude_unset=True)
        
        # Convert reminder_config to dict if provided
        if 'reminder_config' in update_data and update_data['reminder_config']:
            update_data['reminder_config'] = station_data.reminder_config.model_dump()
        
        # Update fields
        for field, value in update_data.items():
            setattr(station, field, value)
        
        self.db.commit()
        self.db.refresh(station)
        
        return station
    
    def update_reminder_config(
        self, 
        station_id: int, 
        reminder_config: Dict[str, Any]
    ) -> Optional[Station]:
        """
        Update only the reminder configuration for a station.
        
        Args:
            station_id: Station ID
            reminder_config: New reminder configuration dict
            
        Returns:
            Updated station or None if not found
        """
        station = self.get_by_id(station_id)
        if not station:
            return None
        
        station.reminder_config = reminder_config
        
        self.db.commit()
        self.db.refresh(station)
        
        return station
    
    # ========================================
    # DELETE
    # ========================================
    
    def delete(self, station_id: int) -> bool:
        """
        Delete a station (hard delete).
        
        Note: Will fail if station has associated hotels or layovers
        due to foreign key constraints (ON DELETE RESTRICT).
        
        Args:
            station_id: Station ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        station = self.get_by_id(station_id)
        if not station:
            return False
        
        self.db.delete(station)
        self.db.commit()
        
        return True
    
    def soft_delete(self, station_id: int) -> Optional[Station]:
        """
        Soft delete a station (set is_active = False).
        
        Preferred over hard delete to preserve historical data.
        
        Args:
            station_id: Station ID to deactivate
            
        Returns:
            Deactivated station or None if not found
        """
        station = self.get_by_id(station_id)
        if not station:
            return None
        
        station.is_active = False
        
        self.db.commit()
        self.db.refresh(station)
        
        return station
    
    # ========================================
    # VALIDATION HELPERS
    # ========================================
    
    def code_exists(self, code: str, exclude_id: Optional[int] = None) -> bool:
        """
        Check if a station code already exists.
        
        Args:
            code: Airport code to check
            exclude_id: Station ID to exclude from check (for updates)
            
        Returns:
            True if code exists, False otherwise
        """
        query = self.db.query(Station).filter(
            func.upper(Station.code) == code.upper()
        )
        
        if exclude_id:
            query = query.filter(Station.id != exclude_id)
        
        return query.first() is not None
    
    def count_active_stations(self) -> int:
        """
        Count total number of active stations.
        
        Returns:
            Count of active stations
        """
        return self.db.query(Station).filter(Station.is_active == True).count()
    
    # ========================================
    # BULK OPERATIONS
    # ========================================
    
    def bulk_activate(self, station_ids: List[int]) -> int:
        """
        Activate multiple stations at once.
        
        Args:
            station_ids: List of station IDs to activate
            
        Returns:
            Number of stations activated
        """
        count = self.db.query(Station).filter(
            Station.id.in_(station_ids)
        ).update(
            {"is_active": True},
            synchronize_session=False
        )
        
        self.db.commit()
        return count
    
    def bulk_deactivate(self, station_ids: List[int]) -> int:
        """
        Deactivate multiple stations at once.
        
        Args:
            station_ids: List of station IDs to deactivate
            
        Returns:
            Number of stations deactivated
        """
        count = self.db.query(Station).filter(
            Station.id.in_(station_ids)
        ).update(
            {"is_active": False},
            synchronize_session=False
        )
        
        self.db.commit()
        return count