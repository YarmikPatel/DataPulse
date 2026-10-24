"""
Local Development Server Runner for DataPulse.
Usage:
    python run.py
"""
import os
from app import create_app
from app.extensions import db

# Determine environment from FLASK_ENV or default to development
env_name = os.environ.get("FLASK_ENV", "development")
app = create_app(config_name=env_name)

if __name__ == "__main__":
    with app.app_context():
        # Automatically creates tables if they don't exist yet
        db.create_all()
        print("DataPulse database tables checked and synchronized.")
    
    print("\n=======================================================")
    print("  DataPulse Local Development Server Started")
    print("  Access dashboard at: http://127.0.0.1:5000")
    print("  Health endpoint at:  http://127.0.0.1:5000/api/health")
    print("=======================================================\n")
    
    app.run(host="127.0.0.1", port=5000, debug=True)
