"""
Hotel Service - Business Logic Layer
Handles business logic, validation, and orchestration for Hotel operations.
"""
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from app.repositories.hotel_repository import HotelRepository
from app.repositories.station_repository import StationRepository
from app.schemas.hotel import (
    HotelCreate, HotelUpdate, HotelResponse, 
    HotelWithStationResponse, HotelListResponse, PerformanceMetrics
)
from app.models.hotel import Hotel
from datetime import date, datetime


class HotelService:
    """
    Service layer for Hotel business logic.
    
    Responsibilities:
    - Validate business rules
    - Coordinate between repositories
    - Handle errors and exceptions
    - Calculate performance metrics
    - Manage hotel contracts
    """
    
    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repository = HotelRepository(db)
        self.station_repository = StationRepository(db)
    
    # ========================================
    # CREATE
    # ========================================
    
    def create_hotel(
        self, 
        hotel_data: HotelCreate, 
        created_by: Optional[int] = None
    ) -> HotelResponse:
        """
        Create a new hotel with validation.
        
        Business Rules:
        - Station must exist
        - Email must be unique
        - Contract rate requires non-ad_hoc contract type
        - WhatsApp number must be valid if provided
        
        Args:
            hotel_data: Validated hotel creation data
            created_by: User ID of creator (optional)
            
        Returns:
            Created hotel response
            
        Raises:
            HTTPException 400: If validation fails
            HTTPException 404: If station not found
            HTTPException 409: If email already exists
        """
        # Validate station exists
        station = self.station_repository.get_by_id(hotel_data.station_id)
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {hotel_data.station_id} not found"
            )
        
        # Check if email already exists
        if self.repository.email_exists(hotel_data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Hotel with email '{hotel_data.email}' already exists"
            )
        
        # Validate contract logic
        self._validate_contract_logic(
            hotel_data.contract_type,
            hotel_data.contract_rate,
            hotel_data.contract_valid_until
        )
        
        # Create hotel
        hotel = self.repository.create(hotel_data, created_by)
        
        return self._hotel_to_response(hotel)
    
    # ========================================
    # READ
    # ========================================
    
    def get_hotel(
        self, 
        hotel_id: int, 
        include_station: bool = False
    ) -> HotelResponse | HotelWithStationResponse:
        """
        Get hotel by ID.
        
        Args:
            hotel_id: Hotel ID
            include_station: Whether to include station details
            
        Returns:
            Hotel response (with or without station)
            
        Raises:
            HTTPException 404: If hotel not found
        """
        hotel = self.repository.get_by_id(hotel_id, include_station=include_station)
        
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ID {hotel_id} not found"
            )
        
        if include_station:
            return self._hotel_to_response_with_station(hotel)
        
        return self._hotel_to_response(hotel)
    
    def list_hotels(
        self,
        page: int = 1,
        page_size: int = 25,
        station_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        include_station: bool = False
    ) -> HotelListResponse:
        """
        List hotels with pagination and filtering.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page (max 100)
            station_id: Filter by station ID
            is_active: Filter by active status
            search: Search in name, city, or email
            include_station: Whether to include station details
            
        Returns:
            Paginated list of hotels
            
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
        
        # Get hotels
        hotels, total = self.repository.get_all(
            skip=skip,
            limit=page_size,
            station_id=station_id,
            is_active=is_active,
            search=search,
            include_station=include_station
        )
        
        # Convert to response models with proper performance_metrics handling
        hotel_responses = [
            self._hotel_to_response(hotel) for hotel in hotels
        ]
        
        return HotelListResponse(
            hotels=hotel_responses,
            total=total,
            page=page,
            page_size=page_size
        )
    
    def get_hotels_by_station(
        self, 
        station_id: int, 
        is_active: Optional[bool] = True
    ) -> List[HotelResponse]:
        """
        Get all hotels for a specific station.
        
        Args:
            station_id: Station ID
            is_active: Filter by active status (None = all)
            
        Returns:
            List of hotels at that station
            
        Raises:
            HTTPException 404: If station not found
        """
        # Validate station exists
        station = self.station_repository.get_by_id(station_id)
        if not station:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Station with ID {station_id} not found"
            )
        
        hotels = self.repository.get_by_station(station_id, is_active)
        
        return [self._hotel_to_response(hotel) for hotel in hotels]
    
    def get_hotels_with_contracts(
        self, 
        station_id: Optional[int] = None
    ) -> List[HotelResponse]:
        """
        Get hotels with active contract rates.
        
        Args:
            station_id: Optional filter by station
            
        Returns:
            List of hotels with active contracts
        """
        hotels = self.repository.get_with_contract(station_id)
        
        return [self._hotel_to_response(hotel) for hotel in hotels]
    
    # ========================================
    # UPDATE
    # ========================================
    
    def update_hotel(self, hotel_id: int, hotel_data: HotelUpdate) -> HotelResponse:
        """
        Update an existing hotel.
        
        Business Rules:
        - Hotel must exist
        - If email changed, must be unique
        - Contract logic must be valid
        - Cannot change station_id (business rule)
        
        Args:
            hotel_id: Hotel ID to update
            hotel_data: Validated update data
            
        Returns:
            Updated hotel response
            
        Raises:
            HTTPException 404: If hotel not found
            HTTPException 409: If new email already exists
            HTTPException 400: If validation fails
        """
        # Check hotel exists
        hotel = self.repository.get_by_id(hotel_id)
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ID {hotel_id} not found"
            )
        
        # Check email uniqueness if email is being changed
        if hotel_data.email and hotel_data.email != hotel.email:
            if self.repository.email_exists(hotel_data.email, exclude_id=hotel_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Hotel with email '{hotel_data.email}' already exists"
                )
        
        # Validate contract logic if contract fields are being updated
        if any([
            hotel_data.contract_type is not None,
            hotel_data.contract_rate is not None,
            hotel_data.contract_valid_until is not None
        ]):
            # Get current values
            new_type = hotel_data.contract_type or hotel.contract_type
            new_rate = hotel_data.contract_rate if hotel_data.contract_rate is not None else hotel.contract_rate
            new_valid_until = hotel_data.contract_valid_until if hotel_data.contract_valid_until is not None else hotel.contract_valid_until
            
            self._validate_contract_logic(new_type, new_rate, new_valid_until)
        
        # Update hotel
        updated_hotel = self.repository.update(hotel_id, hotel_data)
        
        return self._hotel_to_response(updated_hotel)
    
    def update_performance_metrics(
        self, 
        hotel_id: int, 
        metrics: Dict[str, Any]
    ) -> HotelResponse:
        """
        Update hotel performance metrics (called by background jobs).
        
        Args:
            hotel_id: Hotel ID
            metrics: Performance metrics dict
            
        Returns:
            Updated hotel response
            
        Raises:
            HTTPException 404: If hotel not found
        """
        updated_hotel = self.repository.update_performance_metrics(hotel_id, metrics)
        
        if not updated_hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ID {hotel_id} not found"
            )
        
        return self._hotel_to_response(updated_hotel)
    
    # ========================================
    # DELETE
    # ========================================
    
    def deactivate_hotel(self, hotel_id: int) -> Dict[str, str]:
        """
        Soft delete a hotel (set is_active = False).
        
        Args:
            hotel_id: Hotel ID to deactivate
            
        Returns:
            Success message
            
        Raises:
            HTTPException 404: If hotel not found
        """
        hotel = self.repository.soft_delete(hotel_id)
        
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ID {hotel_id} not found"
            )
        
        return {"message": f"Hotel '{hotel.name}' deactivated successfully"}
    
    def hard_delete_hotel(self, hotel_id: int) -> Dict[str, str]:
        """
        Hard delete a hotel (permanent).
        
        Warning: Will fail if hotel has associated layovers.
        
        Args:
            hotel_id: Hotel ID to delete
            
        Returns:
            Success message
            
        Raises:
            HTTPException 404: If hotel not found
            HTTPException 409: If hotel has dependencies
        """
        try:
            deleted = self.repository.delete(hotel_id)
            
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Hotel with ID {hotel_id} not found"
                )
            
            return {"message": "Hotel deleted successfully"}
        
        except Exception as e:
            # Foreign key constraint violation
            if "foreign key constraint" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete hotel with associated layovers. Deactivate instead."
                )
            raise
    
    def activate_hotel(self, hotel_id: int) -> HotelResponse:
        """
        Reactivate a deactivated hotel.
        
        Args:
            hotel_id: Hotel ID to activate
            
        Returns:
            Activated hotel response
            
        Raises:
            HTTPException 404: If hotel not found
        """
        hotel = self.repository.get_by_id(hotel_id)
        
        if not hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ID {hotel_id} not found"
            )
        
        # Update using repository
        update_data = HotelUpdate(is_active=True)
        updated_hotel = self.repository.update(hotel_id, update_data)
        
        return self._hotel_to_response(updated_hotel)
    
    # ========================================
    # PERFORMANCE & REPORTING
    # ========================================
    
    def get_top_performers(
        self, 
        station_id: Optional[int] = None,
        limit: int = 10
    ) -> List[HotelResponse]:
        """
        Get top performing hotels by confirmation rate.
        
        Args:
            station_id: Optional filter by station
            limit: Number of hotels to return
            
        Returns:
            List of top performing hotels
        """
        hotels = self.repository.get_top_performers(station_id, limit)
        
        return [self._hotel_to_response(hotel) for hotel in hotels]
    
    def get_low_performers(
        self, 
        station_id: Optional[int] = None,
        threshold: float = 70.0,
        limit: int = 10
    ) -> List[HotelResponse]:
        """
        Get hotels with confirmation rate below threshold.
        
        Args:
            station_id: Optional filter by station
            threshold: Confirmation rate threshold (default 70%)
            limit: Number of hotels to return
            
        Returns:
            List of low performing hotels
        """
        hotels = self.repository.get_low_performers(station_id, threshold, limit)
        
        return [self._hotel_to_response(hotel) for hotel in hotels]
    
    def get_hotel_statistics(self, station_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get hotel statistics (overall or by station).
        
        Args:
            station_id: Optional filter by station
            
        Returns:
            Statistics dictionary
        """
        # Get hotels
        hotels, total = self.repository.get_all(
            station_id=station_id,
            limit=1000
        )
        
        active_count = sum(1 for h in hotels if h.is_active)
        with_contracts = sum(1 for h in hotels if h.contract_type != 'ad_hoc')
        whatsapp_enabled = sum(1 for h in hotels if h.whatsapp_enabled)
        
        # Calculate average performance - use get_performance_metrics property
        total_requests = 0
        total_confirmed = 0
        
        for h in hotels:
            metrics = h.get_performance_metrics  # Use the property instead of direct access
            total_requests += metrics.get('total_requests', 0)
            total_confirmed += metrics.get('confirmed_count', 0)
        
        avg_confirmation_rate = (
            (total_confirmed / total_requests * 100) if total_requests > 0 else 0
        )
        
        return {
            "total_hotels": total,
            "active_hotels": active_count,
            "inactive_hotels": total - active_count,
            "hotels_with_contracts": with_contracts,
            "hotels_with_whatsapp": whatsapp_enabled,
            "total_layover_requests": total_requests,
            "avg_confirmation_rate": round(avg_confirmation_rate, 2)
        }
    
    # ========================================
    # CONTRACT MANAGEMENT
    # ========================================
    
    def check_expired_contracts(self) -> List[HotelResponse]:
        """
        Get hotels with expired contracts.
        
        Returns:
            List of hotels with expired contracts
        """
        hotels, _ = self.repository.get_all(limit=1000)
        
        today = date.today()
        expired_hotels = []
        
        for hotel in hotels:
            if not hotel.is_active or not hotel.contract_valid_until:
                continue
            
            # Parse date field safely
            valid_until = self._parse_date_field(hotel.contract_valid_until)
            if valid_until and valid_until < today:
                expired_hotels.append(hotel)
        
        return [self._hotel_to_response(hotel) for hotel in expired_hotels]
    
    def get_expiring_contracts(self, days: int = 30) -> List[HotelResponse]:
        """
        Get hotels with contracts expiring soon.
        
        Args:
            days: Number of days to look ahead (default 30)
            
        Returns:
            List of hotels with expiring contracts
        """
        from datetime import timedelta
        
        hotels, _ = self.repository.get_all(limit=1000)
        
        today = date.today()
        threshold = today + timedelta(days=days)
        
        expiring_hotels = []
        
        for hotel in hotels:
            if not hotel.is_active or not hotel.contract_valid_until:
                continue
            
            # Parse date field safely
            valid_until = self._parse_date_field(hotel.contract_valid_until)
            if valid_until and today <= valid_until <= threshold:
                expiring_hotels.append(hotel)
        
        return [self._hotel_to_response(hotel) for hotel in expiring_hotels]
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _parse_date_field(self, date_value: Any) -> Optional[date]:
        """
        Safely parse a date field that might be a string or date object.
        
        Args:
            date_value: Date as string (YYYY-MM-DD) or date object or None
            
        Returns:
            date object or None if invalid/None
        """
        if date_value is None:
            return None
        
        # Already a date object
        if isinstance(date_value, date):
            return date_value
        
        # String format - try to parse
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return None
        
        return None
    
    def _hotel_to_response(self, hotel: Hotel) -> HotelResponse:
        """
        Convert Hotel model to HotelResponse with proper performance_metrics handling.
        
        Args:
            hotel: Hotel model instance
            
        Returns:
            HotelResponse with guaranteed performance_metrics
        """
        # Get performance metrics with defaults if None
        metrics_data = hotel.get_performance_metrics
        
        # Create PerformanceMetrics object
        performance_metrics = PerformanceMetrics(
            total_requests=metrics_data.get('total_requests', 0),
            confirmed_count=metrics_data.get('confirmed_count', 0),
            declined_count=metrics_data.get('declined_count', 0),
            avg_response_hours=metrics_data.get('avg_response_hours', 0.0),
            last_updated=metrics_data.get('last_updated')
        )
        
        # Handle None contract_type - default to ad_hoc
        from app.schemas.hotel import ContractType
        contract_type = hotel.contract_type if hotel.contract_type else ContractType.AD_HOC
        
        # Build response dict
        response_data = {
            "id": hotel.id,
            "station_id": hotel.station_id,
            "name": hotel.name,
            "address": hotel.address,
            "city": hotel.city,
            "postal_code": hotel.postal_code,
            "phone": hotel.phone,
            "email": hotel.email,
            "secondary_emails": hotel.secondary_emails,
            "whatsapp_number": hotel.whatsapp_number,
            "whatsapp_enabled": hotel.whatsapp_enabled,
            "contract_type": contract_type,
            "contract_rate": hotel.contract_rate,
            "contract_valid_until": hotel.contract_valid_until,
            "notes": hotel.notes,
            "performance_metrics": performance_metrics,
            "is_active": hotel.is_active,
            "created_at": hotel.created_at,
            "updated_at": hotel.updated_at
        }
        
        return HotelResponse(**response_data)
    
    def _hotel_to_response_with_station(self, hotel: Hotel) -> HotelWithStationResponse:
        """
        Convert Hotel model to HotelWithStationResponse.
        
        Args:
            hotel: Hotel model instance with station relationship loaded
            
        Returns:
            HotelWithStationResponse
        """
        # Get performance metrics with defaults if None
        metrics_data = hotel.get_performance_metrics
        
        # Create PerformanceMetrics object
        performance_metrics = PerformanceMetrics(
            total_requests=metrics_data.get('total_requests', 0),
            confirmed_count=metrics_data.get('confirmed_count', 0),
            declined_count=metrics_data.get('declined_count', 0),
            avg_response_hours=metrics_data.get('avg_response_hours', 0.0),
            last_updated=metrics_data.get('last_updated')
        )
        
        # Handle None contract_type - default to ad_hoc
        from app.schemas.hotel import ContractType
        contract_type = hotel.contract_type if hotel.contract_type else ContractType.AD_HOC
        
        # Build station dict
        station_data = {
            "id": hotel.station.id,
            "iata_code": hotel.station.iata_code,
            "name": hotel.station.name,
            "city": hotel.station.city,
            "country": hotel.station.country
        }
        
        # Build response dict
        response_data = {
            "id": hotel.id,
            "station_id": hotel.station_id,
            "name": hotel.name,
            "address": hotel.address,
            "city": hotel.city,
            "postal_code": hotel.postal_code,
            "phone": hotel.phone,
            "email": hotel.email,
            "secondary_emails": hotel.secondary_emails,
            "whatsapp_number": hotel.whatsapp_number,
            "whatsapp_enabled": hotel.whatsapp_enabled,
            "contract_type": contract_type,
            "contract_rate": hotel.contract_rate,
            "contract_valid_until": hotel.contract_valid_until,
            "notes": hotel.notes,
            "performance_metrics": performance_metrics,
            "is_active": hotel.is_active,
            "created_at": hotel.created_at,
            "updated_at": hotel.updated_at,
            "station": station_data
        }
        
        return HotelWithStationResponse(**response_data)
    
    # ========================================
    # VALIDATION HELPERS
    # ========================================
    
    def _validate_contract_logic(
        self,
        contract_type: str,
        contract_rate: Optional[float],
        contract_valid_until: Optional[Any]  # Can be date, str, or None
    ) -> None:
        """
        Validate contract business rules.
        
        Rules:
        - If contract_type is 'ad_hoc', contract_rate must be None
        - If contract_rate is provided, contract_type cannot be 'ad_hoc'
        - If contract_valid_until is in the past, raise error
        
        Args:
            contract_type: Contract type
            contract_rate: Contract rate (if any)
            contract_valid_until: Contract expiry (if any)
            
        Raises:
            HTTPException 400: If validation fails
        """
        # Check contract rate logic
        if contract_type == 'ad_hoc' and contract_rate is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="contract_rate cannot be set for ad_hoc contract type"
            )
        
        if contract_rate is not None and contract_type == 'ad_hoc':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contract rate requires non-ad_hoc contract type"
            )
        
        # Check expiry date
        if contract_valid_until:
            # Parse date field safely
            valid_until = self._parse_date_field(contract_valid_until)
            if valid_until and valid_until < date.today():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="contract_valid_until cannot be in the past"
                )