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
    HotelWithStationResponse, HotelListResponse
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
        
        return HotelResponse.model_validate(hotel)
    
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
            return HotelWithStationResponse.model_validate(hotel)
        
        return HotelResponse.model_validate(hotel)
    
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
        
        # Convert to response models
        hotel_responses = [
            HotelResponse.model_validate(hotel) for hotel in hotels
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
        
        return [HotelResponse.model_validate(hotel) for hotel in hotels]
    
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
        
        return [HotelResponse.model_validate(hotel) for hotel in hotels]
    
    # ========================================
    # UPDATE
    # ========================================
    
    def update_hotel(self, hotel_id: int, hotel_data: HotelUpdate) -> HotelResponse:
        """
        Update an existing hotel.
        
        Business Rules:
        - Cannot change email to one that already exists
        - Contract logic must be valid
        
        Args:
            hotel_id: Hotel ID to update
            hotel_data: Update data (only provided fields)
            
        Returns:
            Updated hotel response
            
        Raises:
            HTTPException 404: If hotel not found
            HTTPException 400: If validation fails
            HTTPException 409: If email conflict
        """
        # Check if hotel exists
        existing_hotel = self.repository.get_by_id(hotel_id)
        if not existing_hotel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hotel with ID {hotel_id} not found"
            )
        
        # Validate email uniqueness if changing
        if hotel_data.email and hotel_data.email != existing_hotel.email:
            if self.repository.email_exists(hotel_data.email, exclude_id=hotel_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Hotel with email '{hotel_data.email}' already exists"
                )
        
        # Validate contract logic if any contract fields provided
        contract_type = hotel_data.contract_type or existing_hotel.contract_type
        contract_rate = (
            hotel_data.contract_rate 
            if hotel_data.contract_rate is not None 
            else existing_hotel.contract_rate
        )
        contract_valid_until = (
            hotel_data.contract_valid_until 
            if hotel_data.contract_valid_until is not None 
            else existing_hotel.contract_valid_until
        )
        
        if any([
            hotel_data.contract_type is not None,
            hotel_data.contract_rate is not None,
            hotel_data.contract_valid_until is not None
        ]):
            self._validate_contract_logic(contract_type, contract_rate, contract_valid_until)
        
        # Update hotel
        updated_hotel = self.repository.update(hotel_id, hotel_data)
        
        return HotelResponse.model_validate(updated_hotel)
    
    def update_performance_metrics(
        self, 
        hotel_id: int, 
        metrics: Dict[str, Any]
    ) -> HotelResponse:
        """
        Update hotel performance metrics (called by nightly cron job).
        
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
        
        return HotelResponse.model_validate(updated_hotel)
    
    # ========================================
    # DELETE
    # ========================================
    
    def delete_hotel(self, hotel_id: int) -> Dict[str, str]:
        """
        Soft delete a hotel (deactivate).
        
        Note: Soft delete is preferred to preserve historical data.
        
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
        
        return HotelResponse.model_validate(updated_hotel)
    
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
        
        return [HotelResponse.model_validate(hotel) for hotel in hotels]
    
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
        
        return [HotelResponse.model_validate(hotel) for hotel in hotels]
    
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
        
        # Calculate average performance
        total_requests = sum(h.performance_metrics.get('total_requests', 0) for h in hotels)
        total_confirmed = sum(h.performance_metrics.get('confirmed_count', 0) for h in hotels)
        
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
        expired_hotels = [
            hotel for hotel in hotels
            if hotel.contract_valid_until 
            and hotel.contract_valid_until < today
            and hotel.is_active
        ]
        
        return [HotelResponse.model_validate(hotel) for hotel in expired_hotels]
    
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
        
        expiring_hotels = [
            hotel for hotel in hotels
            if hotel.contract_valid_until
            and today <= hotel.contract_valid_until <= threshold
            and hotel.is_active
        ]
        
        return [HotelResponse.model_validate(hotel) for hotel in expiring_hotels]
    
    # ========================================
    # VALIDATION HELPERS
    # ========================================
    
    def _validate_contract_logic(
        self,
        contract_type: str,
        contract_rate: Optional[float],
        contract_valid_until: Optional[date]
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
        if contract_valid_until and contract_valid_until < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="contract_valid_until cannot be in the past"
            )