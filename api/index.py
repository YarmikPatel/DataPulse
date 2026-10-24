"""
Vercel Serverless Entry Point for DataPulse.
Vercel automatically detects the 'app' WSGI variable exposed here.
"""
from app import create_app

app = create_app()

# Allows local testing if this file is run directly
if __name__ == "__main__":
    app.run()
