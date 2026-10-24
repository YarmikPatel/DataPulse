"""
Database Models for DataPulse.
Defines schema for Users, Datasets, Profiling Reports, Pipeline Runs, and Activity Logs.
"""
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    """Loads a user from database by ID for Flask-Login session management."""
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """User account model for authentication and data ownership."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    datasets = db.relationship("Dataset", backref="owner", lazy=True, cascade="all, delete-orphan")
    pipeline_runs = db.relationship("PipelineRun", backref="user", lazy=True, cascade="all, delete-orphan")
    activity_logs = db.relationship("ActivityLog", backref="user", lazy=True)

    def set_password(self, password: str):
        """Hashes the password with scrypt/pbkdf2 before saving."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies candidate password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}'>"


class Dataset(db.Model):
    """Stores uploaded dataset metadata and raw CSV text for serverless durability."""
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.Integer, nullable=False, default=0)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    column_count = db.Column(db.Integer, nullable=False, default=0)

    # In-Database CSV storage: guarantees datasets survive serverless restarts without cloud S3 costs
    raw_csv_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    profiling_reports = db.relationship(
        "ProfilingReport", backref="dataset", lazy=True, cascade="all, delete-orphan"
    )
    pipeline_runs = db.relationship(
        "PipelineRun", backref="dataset", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Dataset id={self.id} filename='{self.filename}' rows={self.row_count}>"


class ProfilingReport(db.Model):
    """Stores dataset health statistics, null percentages, and quality metrics as JSON."""
    __tablename__ = "profiling_reports"

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    summary_stats = db.Column(db.JSON, nullable=False)  # Dictionary of column types, null counts, stats
    missing_cells_total = db.Column(db.Integer, nullable=False, default=0)
    duplicate_rows_total = db.Column(db.Integer, nullable=False, default=0)
    overall_health_score = db.Column(db.Numeric(5, 2), nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<ProfilingReport id={self.id} dataset_id={self.dataset_id} score={self.overall_health_score}%>"


class PipelineRun(db.Model):
    """Tracks individual cleaning pipeline executions, before/after counts, and downloads."""
    __tablename__ = "pipeline_runs"

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pipeline_name = db.Column(db.String(120), nullable=False, default="Default Pipeline")
    status = db.Column(db.String(20), nullable=False, default="RUNNING")  # RUNNING, SUCCESS, WARNING, FAILED

    rows_before = db.Column(db.Integer, nullable=False, default=0)
    rows_after = db.Column(db.Integer, nullable=False, default=0)
    duplicates_removed = db.Column(db.Integer, nullable=False, default=0)
    missing_imputed = db.Column(db.Integer, nullable=False, default=0)
    rows_dropped = db.Column(db.Integer, nullable=False, default=0)

    # In-memory streaming targets (stored in DB for instant download on Vercel)
    cleaned_csv_data = db.Column(db.Text, nullable=True)
    error_report_data = db.Column(db.Text, nullable=True)

    execution_time_ms = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<PipelineRun id={self.id} status='{self.status}' duration={self.execution_time_ms}ms>"


class ActivityLog(db.Model):
    """
    Durable Audit Trail.
    Records every critical event in Supabase first, then safely syncs to Google Sheets.
    """
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = db.Column(db.String(120), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  # e.g., USER_REGISTER, CSV_UPLOAD, PIPELINE_RUN
    status = db.Column(db.String(20), nullable=False, default="SUCCESS")  # SUCCESS, FAILED
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)  # Safe metadata only (no passwords/data)
    ip_address = db.Column(db.String(45), nullable=True)

    # Synchronization tracking for Google Sheets
    synced_to_sheets = db.Column(db.Boolean, default=False, nullable=False, index=True)
    sheets_synced_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def to_sheets_row(self):
        """Converts model to a clean list matching Google Sheet columns."""
        import json
        return [
            str(self.id),
            self.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            self.user_email or "anonymous",
            self.event_type,
            self.status,
            json.dumps(self.metadata_json) if self.metadata_json else "{}",
            self.ip_address or "unknown"
        ]

    def __repr__(self):
        return f"<ActivityLog id={self.id} event='{self.event_type}' synced={self.synced_to_sheets}>"
