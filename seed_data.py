"""
Seed Data Script
Populates database with realistic stations and hotels for testing/development.

Usage:
    python seed_data.py
"""
import asyncio
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models.station import Station
from app.models.hotel import Hotel
from app.models.user import User
from app.core.security import hash_password
import sys





def seed_stations(db: Session):
    """Create realistic airline stations."""
    print("🔹 Seeding stations...")
    
    stations_data = [
        {
            "code": "LHR",
            "name": "London Heathrow",
            "city": "London",
            "country": "United Kingdom",
            "timezone": "Europe/London",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "18:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "JFK",
            "name": "John F Kennedy International",
            "city": "New York",
            "country": "United States",
            "timezone": "America/New_York",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "18:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "DXB",
            "name": "Dubai International",
            "city": "Dubai",
            "country": "United Arab Emirates",
            "timezone": "Asia/Dubai",
            "reminder_config": {
                "first_reminder_hours": 8,
                "second_reminder_hours": 16,
                "escalation_hours": 24,
                "business_hours_start": "09:00",
                "business_hours_end": "17:00",
                "pause_on_weekends": True
            }
        },
        {
            "code": "SIN",
            "name": "Singapore Changi",
            "city": "Singapore",
            "country": "Singapore",
            "timezone": "Asia/Singapore",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "20:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "HKG",
            "name": "Hong Kong International",
            "city": "Hong Kong",
            "country": "Hong Kong",
            "timezone": "Asia/Hong_Kong",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "20:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "LAX",
            "name": "Los Angeles International",
            "city": "Los Angeles",
            "country": "United States",
            "timezone": "America/Los_Angeles",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "18:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "FRA",
            "name": "Frankfurt Airport",
            "city": "Frankfurt",
            "country": "Germany",
            "timezone": "Europe/Berlin",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "18:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "SYD",
            "name": "Sydney Kingsford Smith",
            "city": "Sydney",
            "country": "Australia",
            "timezone": "Australia/Sydney",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "18:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "CDG",
            "name": "Paris Charles de Gaulle",
            "city": "Paris",
            "country": "France",
            "timezone": "Europe/Paris",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "09:00",
                "business_hours_end": "17:00",
                "pause_on_weekends": False
            }
        },
        {
            "code": "NRT",
            "name": "Tokyo Narita International",
            "city": "Tokyo",
            "country": "Japan",
            "timezone": "Asia/Tokyo",
            "reminder_config": {
                "first_reminder_hours": 12,
                "second_reminder_hours": 24,
                "escalation_hours": 36,
                "business_hours_start": "08:00",
                "business_hours_end": "20:00",
                "pause_on_weekends": False
            }
        }
    ]
    
    created_count = 0
    for station_data in stations_data:
        # Check if station exists
        existing_station = db.query(Station).filter(Station.code == station_data["code"]).first()
        if existing_station:
            print(f"  ⚠️  Station {station_data['code']} already exists, skipping...")
            continue
        
        # Create station
        station = Station(**station_data)
        db.add(station)
        created_count += 1
        print(f"  ✅ Created station: {station_data['code']} - {station_data['name']}")
    
    db.commit()
    print(f"✅ Stations seeded: {created_count} created\n")


def seed_hotels(db: Session):
    """Create realistic hotels for each station."""
    print("🔹 Seeding hotels...")
    
    # Get all stations
    stations = db.query(Station).all()
    
    if not stations:
        print("  ⚠️  No stations found. Please seed stations first.")
        return
    
    # Get admin user for created_by
    admin_user = db.query(User).filter(User.email == "admin@airline.com").first()
    admin_id = admin_user.id if admin_user else None
    
    # Hotel data per station
    hotels_data = {
        "LHR": [
            {
                "name": "Heathrow Hilton",
                "address": "Terminal 4, Heathrow Airport",
                "city": "London",
                "postal_code": "TW6 3AF",
                "phone": "+44-20-8759-7755",
                "email": "reservations@heathrow-hilton.com",
                "contract_type": "preferred_rate",
                "contract_rate": 120.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Close to T4. Prefers 24h notice for large groups."
            },
            {
                "name": "Sofitel London Heathrow",
                "address": "Terminal 5, Heathrow Airport",
                "city": "London",
                "postal_code": "TW6 2GD",
                "phone": "+44-20-8757-7777",
                "email": "h6214@sofitel.com",
                "contract_type": "block_booking",
                "contract_rate": 135.00,
                "contract_valid_until": "2026-06-30",
                "notes": "Connected to T5. Excellent for early departures."
            },
            {
                "name": "Premier Inn Heathrow Bath Road",
                "address": "Bath Road, Longford",
                "city": "London",
                "postal_code": "UB7 0DU",
                "phone": "+44-333-777-3717",
                "email": "bookings@premierinn-lhr.com",
                "contract_type": "ad_hoc",
                "notes": "Budget option. Free shuttle service."
            }
        ],
        "JFK": [
            {
                "name": "TWA Hotel",
                "address": "JFK Airport, Terminal 5",
                "city": "New York",
                "postal_code": "11430",
                "phone": "+1-212-806-9000",
                "email": "groups@twahotel.com",
                "contract_type": "preferred_rate",
                "contract_rate": 150.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Inside JFK. No shuttle needed. Iconic property."
            },
            {
                "name": "Hilton Garden Inn JFK",
                "address": "148-18 134th Street, Jamaica",
                "city": "New York",
                "postal_code": "11436",
                "phone": "+1-718-322-4448",
                "email": "reservations@hgi-jfk.com",
                "contract_type": "block_booking",
                "contract_rate": 140.00,
                "contract_valid_until": "2026-03-31",
                "notes": "5 min shuttle. Reliable service."
            },
            {
                "name": "Courtyard JFK Airport",
                "address": "145-11 North Conduit Avenue",
                "city": "New York",
                "postal_code": "11436",
                "phone": "+1-718-848-2121",
                "email": "reservations@courtyard-jfk.com",
                "contract_type": "ad_hoc",
                "notes": "Good backup option."
            }
        ],
        "DXB": [
            {
                "name": "Dubai International Hotel",
                "address": "Terminal 3, Concourse B",
                "city": "Dubai",
                "postal_code": "DXB",
                "phone": "+971-4-224-5555",
                "email": "reservations@dubaiintlhotel.com",
                "contract_type": "preferred_rate",
                "contract_rate": 180.00,
                "contract_valid_until": "2025-12-31",
                "whatsapp_number": "+971-50-123-4567",
                "whatsapp_enabled": True,
                "notes": "Inside terminal. Premium rates. Immediate access."
            },
            {
                "name": "Millennium Airport Hotel Dubai",
                "address": "Near Terminal 3",
                "city": "Dubai",
                "postal_code": "DXB",
                "phone": "+971-4-702-2222",
                "email": "reservations@millenniumhotels-dxb.com",
                "contract_type": "block_booking",
                "contract_rate": 160.00,
                "contract_valid_until": "2026-01-31",
                "whatsapp_number": "+971-50-234-5678",
                "whatsapp_enabled": True,
                "notes": "Walking distance. Good for long layovers."
            }
        ],
        "SIN": [
            {
                "name": "Crowne Plaza Changi Airport",
                "address": "75 Airport Boulevard",
                "city": "Singapore",
                "postal_code": "819664",
                "phone": "+65-6823-5300",
                "email": "reservations@crowneplaza-sin.com",
                "contract_type": "preferred_rate",
                "contract_rate": 130.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Connected to T3. Excellent for crew rest."
            },
            {
                "name": "YOTELAIR Singapore Changi",
                "address": "78 Airport Boulevard, Terminal 1",
                "city": "Singapore",
                "postal_code": "819666",
                "phone": "+65-6551-1711",
                "email": "reservations@yotelair-sin.com",
                "contract_type": "ad_hoc",
                "notes": "Transit hotel. Hourly rates available."
            }
        ],
        "HKG": [
            {
                "name": "Regal Airport Hotel",
                "address": "9 Cheong Tat Road, Hong Kong International Airport",
                "city": "Hong Kong",
                "postal_code": "HKG",
                "phone": "+852-2286-8888",
                "email": "reservations@regalairport.com",
                "contract_type": "preferred_rate",
                "contract_rate": 145.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Directly connected to terminal. Premium choice."
            }
        ],
        "LAX": [
            {
                "name": "Hilton Los Angeles Airport",
                "address": "5711 West Century Boulevard",
                "city": "Los Angeles",
                "postal_code": "90045",
                "phone": "+1-310-410-4000",
                "email": "reservations@hilton-lax.com",
                "contract_type": "block_booking",
                "contract_rate": 155.00,
                "contract_valid_until": "2026-02-28",
                "notes": "Free shuttle. 5 min from terminals."
            }
        ],
        "FRA": [
            {
                "name": "Hilton Frankfurt Airport",
                "address": "The Squaire, Am Flughafen",
                "city": "Frankfurt",
                "postal_code": "60549",
                "phone": "+49-69-2713-0",
                "email": "reservations@hilton-frankfurt.com",
                "contract_type": "preferred_rate",
                "contract_rate": 125.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Above railway station. Walking distance to terminals."
            }
        ],
        "SYD": [
            {
                "name": "Rydges Sydney Airport",
                "address": "8 Arrival Court, Mascot",
                "city": "Sydney",
                "postal_code": "2020",
                "phone": "+61-2-9313-2500",
                "email": "reservations@rydges-sydney.com",
                "contract_type": "preferred_rate",
                "contract_rate": 140.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Walking distance to international terminal."
            }
        ],
        "CDG": [
            {
                "name": "Sheraton Paris Airport",
                "address": "Tremblay-en-France, Terminal 2",
                "city": "Paris",
                "postal_code": "95716",
                "phone": "+33-1-49-19-70-70",
                "email": "reservations@sheraton-cdg.com",
                "contract_type": "block_booking",
                "contract_rate": 135.00,
                "contract_valid_until": "2026-04-30",
                "notes": "Connected to T2. Excellent for early flights."
            }
        ],
        "NRT": [
            {
                "name": "Narita Tobu Hotel Airport",
                "address": "320-1 Tokko, Narita",
                "city": "Tokyo",
                "postal_code": "286-0106",
                "phone": "+81-476-32-1234",
                "email": "reservations@tobuhotel-narita.com",
                "contract_type": "preferred_rate",
                "contract_rate": 110.00,
                "contract_valid_until": "2025-12-31",
                "notes": "Free shuttle. Traditional Japanese option available."
            }
        ]
    }
    
    created_count = 0
    for station in stations:
        station_hotels = hotels_data.get(station.code, [])
        
        for hotel_data in station_hotels:
            # Check if hotel exists
            existing_hotel = db.query(Hotel).filter(
                Hotel.email == hotel_data["email"]
            ).first()
            
            if existing_hotel:
                print(f"  ⚠️  Hotel {hotel_data['name']} already exists, skipping...")
                continue
            
            # Add station_id and created_by
            hotel_data["station_id"] = station.id
            if admin_id:
                hotel_data["created_by"] = admin_id
            
            # Set defaults for optional fields
            if "contract_type" not in hotel_data:
                hotel_data["contract_type"] = "ad_hoc"
            if "contract_rate" not in hotel_data:
                hotel_data["contract_rate"] = None
            if "contract_valid_until" not in hotel_data:
                hotel_data["contract_valid_until"] = None
            if "whatsapp_number" not in hotel_data:
                hotel_data["whatsapp_number"] = None
            if "whatsapp_enabled" not in hotel_data:
                hotel_data["whatsapp_enabled"] = False
            if "notes" not in hotel_data:
                hotel_data["notes"] = None
            
            # Create hotel
            hotel = Hotel(**hotel_data)
            db.add(hotel)
            created_count += 1
            print(f"  ✅ Created hotel: {hotel_data['name']} at {station.code}")
    
    db.commit()
    print(f"✅ Hotels seeded: {created_count} created\n")


def main():
    """Main seed function."""
    print("\n" + "="*60)
    print("🌱 SEED DATA SCRIPT - Layover Management System")
    print("="*60 + "\n")
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Seed in order (users → stations → hotels)
        seed_stations(db)
        seed_hotels(db)
        
        print("\n" + "="*60)
        print("✅ SEEDING COMPLETE!")
        print("="*60)
        print("\n📊 Summary:")
        print(f"  Users:    {db.query(User).count()}")
        print(f"  Stations: {db.query(Station).count()}")
        print(f"  Hotels:   {db.query(Hotel).count()}")
        print("\n🔑 Test User Credentials:")
        print("  Admin:      admin@airline.com / admin123")
        print("  Ops:        ops@airline.com / ops123")
        print("  Supervisor: supervisor@airline.com / supervisor123")
        print("  Station:    station.lhr@airline.com / station123")
        print("  Finance:    finance@airline.com / finance123")
        print("\n🚀 You can now start using the API!")
        print("   Swagger UI: http://localhost:8000/docs\n")
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        db.rollback()
        sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    main()