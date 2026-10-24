"""
Flask Extensions Module for DataPulse.
Instantiates database and login manager extensions to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Initialize SQLAlchemy ORM instance
db = SQLAlchemy()

# Initialize Flask-Login instance
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"
