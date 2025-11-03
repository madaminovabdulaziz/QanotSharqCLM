# """
# Email System Diagnostic Script
# Tests all components of the email sending system
# """

# import sys
# import os
# from pathlib import Path

# # ✅ AUTO-DETECT PROJECT ROOT
# current_file = Path(__file__).resolve()
# project_root = current_file.parent  # backend/
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))
#     print(f"🔍 Project root added to PYTHONPATH: {project_root}")

# from sqlalchemy import create_engine, text
# from sqlalchemy.orm import sessionmaker
# from app.core.config import settings
# from app.services.email_service import EmailService
# from datetime import datetime

# def test_smtp_configuration():
#     print("\n" + "="*60)
#     print("TEST 1: SMTP Configuration")
#     print("="*60)

#     print(f"SMTP_HOST: {settings.SMTP_HOST}")
#     print(f"SMTP_PORT: {settings.SMTP_PORT}")
#     print(f"SMTP_TLS: {settings.SMTP_TLS}")
#     print(f"SMTP_USER: {settings.SMTP_USER}")
#     print(f"SMTP_PASSWORD: {'*' * len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else 'NOT SET'}")
#     print(f"SMTP_FROM_EMAIL: {settings.SMTP_FROM_EMAIL}")
#     print(f"SMTP_FROM_NAME: {settings.SMTP_FROM_NAME}")

#     if not settings.SMTP_HOST or not settings.SMTP_USER:
#         print("\n❌ CRITICAL: SMTP_HOST or SMTP_USER not configured!")
#         return False

#     if not settings.SMTP_PASSWORD:
#         print("\n❌ CRITICAL: SMTP_PASSWORD not set!")
#         return False

#     print("\n✅ SMTP configuration looks complete")
#     return True


# def test_smtp_connection():
#     print("\n" + "="*60)
#     print("TEST 2: SMTP Connection")
#     print("="*60)

#     import smtplib

#     try:
#         print(f"Connecting to {settings.SMTP_HOST}:{settings.SMTP_PORT}...")

#         with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
#             print("✅ Connection established")

#             if settings.SMTP_TLS:
#                 print("Starting TLS...")
#                 server.starttls()
#                 print("✅ TLS started")

#             print("Attempting login...")
#             server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
#             print("✅ Login successful")

#         print("\n✅ SMTP connection test PASSED")
#         return True

#     except smtplib.SMTPAuthenticationError as e:
#         print(f"\n❌ SMTP Authentication FAILED: {e}")
#         return False

#     except Exception as e:
#         print(f"\n❌ SMTP Error: {e}")
#         return False


# def test_database_connection():
#     print("\n" + "="*60)
#     print("TEST 3: Database Connection")
#     print("="*60)

#     try:
#         engine = create_engine(settings.DATABASE_URL)
#         Session = sessionmaker(bind=engine)
#         db = Session()

#         db.execute(text("SELECT 1"))
#         db.close()

#         print("✅ Database connection successful")
#         return True

#     except Exception as e:
#         print(f"❌ Database connection failed: {e}")
#         return False


# def test_template_exists():
#     print("\n" + "="*60)
#     print("TEST 4: Email Template")
#     print("="*60)

#     template_path = project_root / "app" / "templates" / "emails" / "hotel_request.html"

#     if template_path.exists():
#         print(f"✅ Template found at: {template_path}")
#         size = template_path.stat().st_size
#         print(f"   Template size: {size} bytes")
#         if size < 100:
#             print("   ⚠️ WARNING: Template seems very small")
#         return True

#     print("❌ Template NOT found")
#     print(f"Tried: {template_path}")
#     return False


# def test_send_simple_email(test_email: str):
#     print("\n" + "="*60)
#     print("TEST 5: Send Simple Email via EmailService")
#     print("="*60)

#     try:
#         engine = create_engine(settings.DATABASE_URL)
#         Session = sessionmaker(bind=engine)
#         db = Session()

#         email_service = EmailService(db)

#         print(f"📨 Sending test email to: {test_email} ...")

#         result = email_service.send_email(
#             to_email=test_email,
#             subject="TEST: Layover System Email (Simple)",
#             html_body=f"""
#                 <html>
#                 <body>
#                     <h2>✅ Layover System Email Test</h2>
#                     <p>This is a <b>simple test email</b> sent using EmailService.</p>
#                     <p>Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
#                 </body>
#                 </html>
#             """,
#             text_body="Layover System Email Test - This is a simple email."
#         )

#         db.close()

#         if result.get("success"):
#             print("\n✅ SIMPLE EMAIL SENT SUCCESSFULLY!")
#             print(f"   Notification ID: {result.get('notification_id')}")
#             print(f"📬 Check inbox: {test_email} (also Spam folder)")
#             return True

#         print(f"\n❌ Email sending FAILED: {result.get('message')}")
#         return False

#     except Exception as e:
#         print(f"\n❌ Error sending simple test email: {e}")
#         return False


# def main():
#     print("\n" + "🔧" * 30)
#     print("EMAIL SYSTEM DIAGNOSTIC TOOL")
#     print("Crew Layover Management System")
#     print("🔧" * 30)

#     test_email = input("\nEnter your email address for testing: ").strip()

#     if not test_email or '@' not in test_email:
#         print("❌ Invalid email address")
#         return

#     print(f"\nWill run initial tests. Will send email to: {test_email}")
#     print("="*60)

#     results = []

#     results.append(("Configuration", test_smtp_configuration()))
#     results.append(("SMTP Connection", test_smtp_connection()))
#     results.append(("Database", test_database_connection()))
#     results.append(("Templates", test_template_exists()))

#     print("\n" + "="*60)
#     print("DIAGNOSTIC SUMMARY")
#     print("="*60)

#     for test_name, passed in results:
#         print(f"{'✅ PASS' if passed else '❌ FAIL'}  {test_name}")

#     print("\n" + "="*60)

#     if all(r[1] for r in results):
#         print("\n🎉 INITIAL TESTS PASSED!")
#         print("\nYou can now run the email sending tests.")

#         run_email = input("\nRun Simple Email Test now? (y/n): ").strip().lower()
#         if run_email == "y":
#             test_send_simple_email(test_email)

#     else:
#         print("\n⚠️ SOME TESTS FAILED — Fix them before sending emails.")


# if __name__ == "__main__":
#     main()

"""
Simple Direct Email Test
Tests notification sending without importing problematic schemas
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

print("🔧 Starting simple email test...")

# Import only what we need
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

def check_layover_and_send_email():
    """Check a layover and manually trigger email"""
    print("\n" + "="*60)
    print("MANUAL EMAIL TEST FOR LAYOVER")
    print("="*60)
    
    layover_id = input("\nEnter Layover ID: ").strip()
    
    try:
        layover_id = int(layover_id)
    except ValueError:
        print("❌ Invalid layover ID")
        return
    
    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Get layover with hotel info
        query = text("""
            SELECT 
                l.id,
                l.origin_station_code,
                l.destination_station_code,
                l.check_in_date,
                l.check_in_time,
                l.check_out_date,
                l.check_out_time,
                l.crew_count,
                l.status,
                l.hotel_id,
                h.name as hotel_name,
                h.email as hotel_email,
                s.name as station_name
            FROM layovers l
            LEFT JOIN hotels h ON l.hotel_id = h.id
            LEFT JOIN stations s ON l.station_id = s.id
            WHERE l.id = :layover_id
        """)
        
        result = db.execute(query, {"layover_id": layover_id}).fetchone()
        
        if not result:
            print(f"❌ Layover {layover_id} not found")
            return
        
        print(f"\n✅ Layover Found:")
        print(f"   ID: {result[0]}")
        print(f"   Route: {result[1]} → {result[2]}")
        print(f"   Check-in: {result[3]} {result[4]}")
        print(f"   Check-out: {result[5]} {result[6]}")
        print(f"   Crew: {result[7]}")
        print(f"   Status: {result[8]}")
        print(f"   Hotel ID: {result[9]}")
        print(f"   Hotel: {result[10]}")
        print(f"   Hotel Email: {result[11]}")
        
        hotel_email = result[11]
        
        if not hotel_email:
            print("\n❌ ERROR: Hotel has no email address!")
            print(f"   Update hotel {result[9]} to add email")
            return
        
        print(f"\n✅ Hotel email is configured: {hotel_email}")
        
        # Check notifications table
        print("\n" + "-"*60)
        print("Checking existing notifications...")
        
        notif_query = text("""
            SELECT 
                id,
                notification_type,
                status,
                error_message,
                created_at,
                sent_at
            FROM notifications
            WHERE layover_id = :layover_id
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        notifications = db.execute(notif_query, {"layover_id": layover_id}).fetchall()
        
        if notifications:
            print(f"\n✅ Found {len(notifications)} notification(s):")
            for notif in notifications:
                print(f"\n   Notification ID: {notif[0]}")
                print(f"   Type: {notif[1]}")
                print(f"   Status: {notif[2]}")
                print(f"   Error: {notif[3] or 'None'}")
                print(f"   Created: {notif[4]}")
                print(f"   Sent: {notif[5] or 'NOT SENT'}")
                
                if notif[2] == 'pending':
                    print("   ⚠️  STATUS IS PENDING - Email was NOT sent!")
                elif notif[2] == 'failed':
                    print("   ❌ STATUS IS FAILED - Check error message")
                elif notif[2] == 'sent':
                    print("   ✅ STATUS IS SENT - Email was sent successfully")
        else:
            print("\n⚠️  No notifications found for this layover")
            print("   This means NotificationService was never called!")
        
        # Now try to send email manually
        print("\n" + "="*60)
        print("MANUAL EMAIL SEND TEST")
        print("="*60)
        
        proceed = input("\nSend test email to hotel now? (y/n): ").strip().lower()
        
        if proceed != 'y':
            print("Skipped")
            return
        
        # Import EmailService here (after schema issues are bypassed)
        from app.services.email_service import EmailService
        
        email_service = EmailService(db)
        
        # Create simple test email
        print(f"\n📧 Sending test email to {hotel_email}...")
        
        html_body = f"""
        <html>
        <body>
            <h2>🧪 Test Email - Layover System</h2>
            <p>This is a <b>manual test email</b> for layover #{layover_id}</p>
            <p><b>Route:</b> {result[1]} → {result[2]}</p>
            <p><b>Hotel:</b> {result[10]}</p>
            <p>If you receive this, the email system is working!</p>
        </body>
        </html>
        """
        
        send_result = email_service.send_email(
            to_email=hotel_email,
            subject=f"TEST: Layover Request #{layover_id}",
            html_body=html_body,
            text_body="Test email for layover system",
            layover_id=layover_id,
            notification_type="hotel_request"
        )
        
        print(f"\n📊 Email Send Result:")
        print(f"   Success: {send_result.get('success')}")
        print(f"   Message: {send_result.get('message')}")
        print(f"   Notification ID: {send_result.get('notification_id')}")
        
        if send_result.get('success'):
            print(f"\n✅ EMAIL SENT SUCCESSFULLY!")
            print(f"   Check {hotel_email} inbox (and spam folder)")
        else:
            print(f"\n❌ EMAIL FAILED TO SEND")
            print(f"   Reason: {send_result.get('message')}")
            
            # Check if it's SMTP config issue
            if 'SMTP not configured' in send_result.get('message', ''):
                print("\n🔧 SMTP Configuration Issue:")
                print(f"   SMTP_HOST: {settings.SMTP_HOST}")
                print(f"   SMTP_USER: {settings.SMTP_USER}")
                print(f"   SMTP_PASSWORD: {'SET' if settings.SMTP_PASSWORD else 'NOT SET'}")
                print("\n   ⚠️  Your .env settings are not loading!")
                print("   Solution: Restart your FastAPI application")
        
    finally:
        db.close()


def check_smtp_settings():
    """Quick SMTP settings check"""
    print("\n" + "="*60)
    print("SMTP CONFIGURATION CHECK")
    print("="*60)
    
    print(f"SMTP_HOST: {settings.SMTP_HOST or 'NOT SET'}")
    print(f"SMTP_PORT: {settings.SMTP_PORT}")
    print(f"SMTP_USER: {settings.SMTP_USER or 'NOT SET'}")
    print(f"SMTP_PASSWORD: {'*' * len(settings.SMTP_PASSWORD) if settings.SMTP_PASSWORD else 'NOT SET'}")
    print(f"SMTP_FROM_EMAIL: {settings.SMTP_FROM_EMAIL}")
    
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print("\n❌ SMTP NOT CONFIGURED!")
        print("   Your .env file might not be loading correctly")
        return False
    
    print("\n✅ SMTP Configuration looks OK")
    return True


def main():
    print("\n" + "🔧" * 30)
    print("SIMPLE EMAIL DIAGNOSTIC")
    print("Bypasses schema import issues")
    print("🔧" * 30)
    
    # First check SMTP
    if not check_smtp_settings():
        print("\n⚠️  Fix SMTP configuration first!")
        return
    
    # Then check layover and send
    check_layover_and_send_email()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()