"""
Phase 1 Unit & Sanity Tests for DataPulse.
Verifies application factory, database models, relationships, and health endpoints.
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import User, Dataset, ProfilingReport, PipelineRun, ActivityLog


@pytest.fixture
def app():
    """Create application configured for testing."""
    test_app = create_app(config_name="testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for HTTP requests."""
    return app.test_client()


def test_health_check_endpoint(client):
    """Test that /api/health responds with 200 OK and valid JSON structure."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "database" in data


def test_user_creation_and_password_hashing(app):
    """Test User model creation and secure password hashing."""
    with app.app_context():
        user = User(username="student_tester", email="student@example.com")
        user.set_password("SecurePassword123!")
        db.session.add(user)
        db.session.commit()

        # Verify password is not stored in plaintext
        assert user.password_hash != "SecurePassword123!"
        assert user.check_password("SecurePassword123!") is True
        assert user.check_password("WrongPassword") is False
        assert user.id is not None


def test_dataset_and_profiling_relationship(app):
    """Test Dataset model with in-database raw CSV storage and ProfilingReport."""
    with app.app_context():
        user = User(username="data_analyst", email="analyst@example.com")
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()

        # Add Dataset with raw CSV content
        raw_csv = "id,name,score\n1,Alice,95\n2,Bob,88\n"
        dataset = Dataset(
            user_id=user.id,
            filename="student_scores.csv",
            original_filename="student_scores.csv",
            file_size_bytes=len(raw_csv.encode("utf-8")),
            row_count=2,
            column_count=3,
            raw_csv_data=raw_csv
        )
        db.session.add(dataset)
        db.session.commit()

        # Add ProfilingReport
        report = ProfilingReport(
            dataset_id=dataset.id,
            summary_stats={"id": "int64", "name": "object", "score": "int64"},
            missing_cells_total=0,
            duplicate_rows_total=0,
            overall_health_score=100.00
        )
        db.session.add(report)
        db.session.commit()

        # Verify query and cascading relations
        saved_dataset = Dataset.query.filter_by(filename="student_scores.csv").first()
        assert saved_dataset is not None
        assert saved_dataset.owner.username == "data_analyst"
        assert len(saved_dataset.profiling_reports) == 1
        assert saved_dataset.profiling_reports[0].overall_health_score == 100.00


def test_activity_log_sheets_serialization(app):
    """Test ActivityLog model and its Google Sheets row converter."""
    with app.app_context():
        log = ActivityLog(
            user_email="student@example.com",
            event_type="CSV_UPLOAD",
            status="SUCCESS",
            metadata_json={"filename": "test.csv", "rows": 100},
            ip_address="127.0.0.1"
        )
        db.session.add(log)
        db.session.commit()

        assert log.synced_to_sheets is False
        row = log.to_sheets_row()

        # Check expected columns: [ID, Timestamp, Email, Event, Status, MetadataJSON, IP]
        assert len(row) == 7
        assert row[2] == "student@example.com"
        assert row[3] == "CSV_UPLOAD"
        assert row[4] == "SUCCESS"
        assert '"rows": 100' in row[5]
