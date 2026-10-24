"""
Flask Application Factory for DataPulse.
Assembles extensions, configuration, blueprints, and core endpoints.
"""
from flask import Flask, jsonify
from app.config import config_by_name, Config
from app.extensions import db, login_manager


def create_app(config_name="default"):
    """
    Application Factory Pattern.
    Creates and configures an instance of the Flask application.
    """
    app = Flask(__name__)

    # Apply configuration
    cfg = config_by_name.get(config_name, Config)
    app.config.from_object(cfg)

    # Initialize extensions with this app instance
    db.init_app(app)
    login_manager.init_app(app)

    # Import models so SQLAlchemy and Flask-Login are aware of them
    with app.app_context():
        from app import models  # noqa: F401

    # Register application blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.datasets import datasets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(datasets_bp)

    # -------------------------------------------------------------
    # Security & Cache Control Headers
    # -------------------------------------------------------------
    @app.after_request
    def set_cache_and_security_headers(response):
        """
        Prevents browser disk and bfcache reuse of authenticated pages.
        Ensures clicking browser 'Back' after logout revalidates with the server.
        """
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # -------------------------------------------------------------
    # Core Health Check & Status Endpoints
    # -------------------------------------------------------------
    @app.route("/api/health")
    def health_check():
        """Returns application status and database configuration state."""
        db_type = "Supabase PostgreSQL" if Config.IS_SUPABASE_CONFIGURED else "Local SQLite Fallback"
        return jsonify({
            "status": "healthy",
            "service": "DataPulse - Data Quality & Pipeline Monitoring Platform",
            "phase": "Phase 3: CSV Upload & Data Profiling",
            "database": {
                "type": db_type,
                "configured": Config.IS_SUPABASE_CONFIGURED,
                "uri_scheme": app.config["SQLALCHEMY_DATABASE_URI"].split("://")[0]
            }
        }), 200

    # CLI command to create all tables
    @app.cli.command("init-db")
    def init_db():
        """CLI helper: Initializes all database tables defined in models."""
        db.create_all()
        print("Initialized all database tables successfully.")

    return app
