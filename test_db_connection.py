"""
Database Connection Verifier for DataPulse.
Directly tests PostgreSQL connection to Supabase and reports status.
Usage:
    python test_db_connection.py
"""
import sys
import time
from app import create_app
from app.extensions import db
from app.config import Config
from sqlalchemy import text

app = create_app()

def verify_connection():
    print("=" * 60)
    print(" DataPulse - Database Connectivity Diagnostics")
    print("=" * 60)

    if not Config.IS_SUPABASE_CONFIGURED:
        print("[STATUS] No Supabase DATABASE_URL configured in .env yet.")
        print("[INFO]   Using Local SQLite fallback for offline development.")
        print("[ACTION] To connect to Supabase:")
        print("         1. Create a free project at https://supabase.com")
        print("         2. Go to Project Settings -> Database -> Connection String")
        print("         3. Choose 'URI' (Transaction pooler, port 6543 recommended)")
        print("         4. Copy the URL into your .env file as DATABASE_URL=...")
        print("=" * 60)
        return False

    # Supabase URL is present, test the actual live connection
    masked_url = app.config['SQLALCHEMY_DATABASE_URI']
    if "@" in masked_url:
        prefix, host_part = masked_url.split("@", 1)
        scheme_user = prefix.split(":")[0] + "://***"
        masked_url = f"{scheme_user}@{host_part}"

    print(f"[TESTING] Attempting connection to: {masked_url}")
    start_time = time.time()

    with app.app_context():
        try:
            # Execute low-overhead ping query
            with db.engine.connect() as connection:
                result = connection.execute(text("SELECT version();")).fetchone()
                latency = round((time.time() - start_time) * 1000, 2)
                
                print(f"[SUCCESS] Connected successfully in {latency} ms!")
                print(f"[VERSION] {result[0]}")
                
                # Check / create tables
                db.create_all()
                print("[SUCCESS] Verified all DataPulse tables (users, datasets, etc.) in Supabase!")
                print("=" * 60)
                return True
        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            print(f"[FAILED]  Connection failed after {latency} ms.")
            print(f"[ERROR]   {e}")
            print("[ACTION]  Please verify your password and pooler port (6543) in .env.")
            print("=" * 60)
            return False

if __name__ == "__main__":
    success = verify_connection()
    sys.exit(0 if success else 1)
