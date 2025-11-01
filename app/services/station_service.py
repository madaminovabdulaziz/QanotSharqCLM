"""
Station Service - Business Logic Layer
Handles business logic, validation, and orchestration for Station operations.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from app.repositories.station_repository import StationRepository
from app.schemas.station import StationCreate, StationUpdate, StationResponse, StationListResponse
from app.models.station import Station
import pytz
from datetime import datetime


class StationService:
    """
    Service layer for Station business logic.
    
    Responsibilities:
    - Validate business rules
    - Coordinate between repositories
    - Handle errors and exceptions
    - Orchestrate complex workflows
    """
    
    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repository = StationRepository(db)
    
    # ========================================
    # CREATE
    # ========================================
    
    def create_station(self, station_data: StationCreate) -> StationResponse:
        """
        Create a new station with validation.
        
        Business Rules:
        - Airport code must be unique
        - Timezone must be valid IANA identifier
        - Reminder hours must be logical (2nd > 1st, escalation > 2nd)
        
        Args:
            station_data: Validated station creation data
            
        Returns:
            Created station response
            
        Raises:
            HTTPException 400: If validation fails
            HTTPException 409: If code already exists
        """
        # Check if code already exists
        if self.repository.code_exists(station_data.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Station with code '{station_data.code}' already exists"
            )
        
        # Validate timezone (additional check beyond Pydantic)
        self._validate_timezone(station_data.timezone)
        
        # Validate reminder config if provided
        if station_data.reminder_config:
            self._validate_reminder_config(station_data.reminder_config.model_dump())
        
        # Create station
        station = self.repository.create(station_data)
        
        return StationResponse.model_validate(station)
    
    # ========================================
    # READ
    # ========================================
    
    def get_station(self, station_id: int) -> StationResponse:
        """
        Get station by ID.
        
        Args:
            station_id: Station ID
            
        Returns:
            Station response
            
        Raises:
            HTTPException 404: If station not found
        """
        station = self.repository.get_by_id(station_id)
        
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {station_id} not found"
            )
        
        return StationResponse.model_validate(station)
    
    def get_station_by_code(self, code: str) -> StationResponse:
        """
        Get station by airport code.
        
        Args:
            code: Airport code (case-insensitive)
            
        Returns:
            Station response
            
        Raises:
            HTTPException 404: If station not found
        """
        station = self.repository.get_by_code(code)
        
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with code '{code}' not found"
            )
        
        return StationResponse.model_validate(station)
    
    def list_stations(
        self,
        page: int = 1,
        page_size: int = 25,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> StationListResponse:
        """
        List stations with pagination and filtering.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page (max 100)
            is_active: Filter by active status (None = all)
            search: Search in code, name, or city
            
        Returns:
            Paginated list of stations
            
        Raises:
            HTTPException 400: If pagination params invalid
        """
        # Validate pagination
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page must be >= 1"
            )
        
        if page_size < 1 or page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size must be between 1 and 100"
            )
        
        # Calculate skip
        skip = (page - 1) * page_size
        
        # Get stations
        stations, total = self.repository.get_all(
            skip=skip,
            limit=page_size,
            is_active=is_active,
            search=search
        )
        
        # Convert to response models
        station_responses = [
            StationResponse.model_validate(station) for station in stations
        ]
        
        return StationListResponse(
            stations=station_responses,
            total=total,
            page=page,
            page_size=page_size
        )
    
    def get_active_stations(self) -> List[StationResponse]:
        """
        Get all active stations (for dropdowns, selects).
        
        Returns:
            List of active stations
        """
        stations = self.repository.get_active_stations()
        
        return [StationResponse.model_validate(station) for station in stations]
    
    def get_stations_by_timezone(self, timezone: str) -> List[StationResponse]:
        """
        Get stations by timezone (useful for reminder scheduling).
        
        Args:
            timezone: IANA timezone identifier
            
        Returns:
            List of stations in that timezone
        """
        # Validate timezone
        self._validate_timezone(timezone)
        
        stations = self.repository.get_by_timezone(timezone)
        
        return [StationResponse.model_validate(station) for station in stations]
    
    # ========================================
    # UPDATE
    # ========================================
    
    def update_station(self, station_id: int, station_data: StationUpdate) -> StationResponse:
        """
        Update an existing station.
        
        Business Rules:
        - Cannot change code to one that already exists
        - Timezone must be valid if provided
        - Reminder config must be logical if provided
        
        Args:
            station_id: Station ID to update
            station_data: Update data (only provided fields)
            
        Returns:
            Updated station response
            
        Raises:
            HTTPException 404: If station not found
            HTTPException 400: If validation fails
            HTTPException 409: If code conflict
        """
        # Check if station exists
        existing_station = self.repository.get_by_id(station_id)
        if not existing_station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {station_id} not found"
            )
        
        # Validate code uniqueness if changing
        if station_data.code and station_data.code != existing_station.code:
            if self.repository.code_exists(station_data.code, exclude_id=station_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Station with code '{station_data.code}' already exists"
                )
        
        # Validate timezone if provided
        if station_data.timezone:
            self._validate_timezone(station_data.timezone)
        
        # Validate reminder config if provided
        if station_data.reminder_config:
            self._validate_reminder_config(station_data.reminder_config.model_dump())
        
        # Update station
        updated_station = self.repository.update(station_id, station_data)
        
        return StationResponse.model_validate(updated_station)
    
    def update_reminder_config(
        self, 
        station_id: int, 
        reminder_config: Dict[str, Any]
    ) -> StationResponse:
        """
        Update only the reminder configuration for a station.
        
        Args:
            station_id: Station ID
            reminder_config: New reminder configuration
            
        Returns:
            Updated station response
            
        Raises:
            HTTPException 404: If station not found
            HTTPException 400: If config invalid
        """
        # Check if station exists
        existing_station = self.repository.get_by_id(station_id)
        if not existing_station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {station_id} not found"
            )
        
        # Validate reminder config
        self._validate_reminder_config(reminder_config)
        
        # Update
        updated_station = self.repository.update_reminder_config(station_id, reminder_config)
        
        return StationResponse.model_validate(updated_station)
    
    # ========================================
    # DELETE
    # ========================================
    
    def delete_station(self, station_id: int) -> Dict[str, str]:
        """
        Soft delete a station (deactivate).
        
        Note: Soft delete is preferred to preserve historical data.
        
        Args:
            station_id: Station ID to deactivate
            
        Returns:
            Success message
            
        Raises:
            HTTPException 404: If station not found
        """
        station = self.repository.soft_delete(station_id)
        
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {station_id} not found"
            )
        
        return {"message": f"Station '{station.name}' deactivated successfully"}
    
    def hard_delete_station(self, station_id: int) -> Dict[str, str]:
        """
        Hard delete a station (permanent).
        
        Warning: Will fail if station has associated hotels or layovers.
        
        Args:
            station_id: Station ID to delete
            
        Returns:
            Success message
            
        Raises:
            HTTPException 404: If station not found
            HTTPException 409: If station has dependencies
        """
        try:
            deleted = self.repository.delete(station_id)
            
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Station with ID {station_id} not found"
                )
            
            return {"message": "Station deleted successfully"}
        
        except Exception as e:
            # Foreign key constraint violation
            if "foreign key constraint" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete station with associated hotels or layovers. Deactivate instead."
                )
            raise
    
    def activate_station(self, station_id: int) -> StationResponse:
        """
        Reactivate a deactivated station.
        
        Args:
            station_id: Station ID to activate
            
        Returns:
            Activated station response
            
        Raises:
            HTTPException 404: If station not found
        """
        station = self.repository.get_by_id(station_id)
        
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {station_id} not found"
            )
        
        # Update using repository
        update_data = StationUpdate(is_active=True)
        updated_station = self.repository.update(station_id, update_data)
        
        return StationResponse.model_validate(updated_station)
    
    # ========================================
    # STATISTICS & REPORTING
    # ========================================
    
    def get_station_statistics(self) -> Dict[str, Any]:
        """
        Get overall station statistics.
        
        Returns:
            Statistics dictionary
        """
        total_stations, _ = self.repository.get_all(limit=1000)
        active_count = self.repository.count_active_stations()
        
        # Get timezone distribution
        timezones = {}
        for station in total_stations:
            tz = station.timezone
            timezones[tz] = timezones.get(tz, 0) + 1
        
        return {
            "total_stations": len(total_stations),
            "active_stations": active_count,
            "inactive_stations": len(total_stations) - active_count,
            "timezone_distribution": timezones
        }
    
    # ========================================
    # VALIDATION HELPERS
    # ========================================
    
    def _validate_timezone(self, timezone: str) -> None:
        """
        Validate timezone is valid IANA identifier.
        
        Args:
            timezone: Timezone string
            
        Raises:
            HTTPException 400: If timezone invalid
        """
        if timezone not in pytz.all_timezones:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timezone: {timezone}. Must be valid IANA timezone."
            )
    
    def _validate_reminder_config(self, config: Dict[str, Any]) -> None:
        """
        Validate reminder configuration business rules.
        
        Args:
            config: Reminder config dictionary
            
        Raises:
            HTTPException 400: If config invalid
        """
        first = config.get('first_reminder_hours')
        second = config.get('second_reminder_hours')
        escalation = config.get('escalation_hours')
        
        # Validate logical ordering
        if second and first and second <= first:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Second reminder must be after first reminder"
            )
        
        if escalation and second and escalation <= second:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escalation must be after second reminder"
            )
        
        # Validate business hours format
        start = config.get('business_hours_start')
        end = config.get('business_hours_end')
        
        if start and end:
            try:
                start_time = datetime.strptime(start, "%H:%M").time()
                end_time = datetime.strptime(end, "%H:%M").time()
                
                if end_time <= start_time:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Business hours end must be after start"
                    )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Business hours must be in HH:MM format"
                )