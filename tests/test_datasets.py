"""
Phase 3 — CSV Upload & Data Profiling Tests for DataPulse.

Verifies:
  - Successful CSV upload (creates Dataset + ProfilingReport rows)
  - Profiling accuracy with a fixture CSV (deliberate nulls + duplicates)
  - Validation: non-CSV extension rejected
  - Validation: empty file rejected
  - Validation: oversized file rejected
  - Validation: missing file field rejected
  - Unauthenticated upload redirects to login
  - Profiling service unit tests (independent of Flask)
"""
import io
import pytest
from app import create_app
from app.extensions import db
from app.models import User, Dataset, ProfilingReport
from app.services.profiling_service import profile_csv


# ==============================================================
# Fixtures
# ==============================================================

@pytest.fixture
def app():
    """Flask application configured for testing with an in-memory SQLite database."""
    test_app = create_app(config_name="testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """HTTP test client."""
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """
    Test client that is already logged in as a freshly registered test user.
    Returns the client so tests can make authenticated requests directly.
    """
    with app.app_context():
        user = User(username="csv_tester", email="csv@datapulse.test")
        user.set_password("TestPass123!")
        db.session.add(user)
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "csv@datapulse.test", "password": "TestPass123!"},
        follow_redirects=True,
    )
    return client


# ==============================================================
# Fixture CSV strings
# ==============================================================

# A perfectly clean, small CSV — no nulls, no duplicates
CLEAN_CSV = (
    "id,name,age,score\n"
    "1,Alice,30,95.5\n"
    "2,Bob,25,82.0\n"
    "3,Charlie,35,78.3\n"
)

# CSV with deliberate quality issues:
#   - Row 4 is a full duplicate of row 2
#   - "age" column has one missing value (row 3)
#   - "score" column has one missing value (row 4, which is also a duplicate)
DIRTY_CSV = (
    "id,name,age,score\n"
    "1,Alice,30,95.5\n"
    "2,Bob,,82.0\n"          # missing age
    "3,Charlie,35,\n"        # missing score
    "2,Bob,,82.0\n"          # exact duplicate of row 2
)


def _csv_file(content: str, filename: str = "test.csv"):
    """Helper: wrap a CSV string as a FileStorage-compatible BytesIO tuple."""
    return (io.BytesIO(content.encode("utf-8")), filename)


# ==============================================================
# Profiling Service Unit Tests (no Flask required)
# ==============================================================

class TestProfilingService:
    """Pure unit tests for app.services.profiling_service.profile_csv."""

    def test_clean_csv_row_and_column_count(self):
        result = profile_csv(CLEAN_CSV)
        assert result["row_count"] == 3
        assert result["column_count"] == 4

    def test_clean_csv_no_missing_cells(self):
        result = profile_csv(CLEAN_CSV)
        assert result["total_missing"] == 0

    def test_clean_csv_no_duplicate_rows(self):
        result = profile_csv(CLEAN_CSV)
        assert result["duplicate_rows"] == 0

    def test_clean_csv_health_score_is_100(self):
        result = profile_csv(CLEAN_CSV)
        # Perfect data: completeness=1, uniqueness=1, validity=1 → 100.0
        assert result["health_score"] == 100.0

    def test_dirty_csv_missing_cell_count(self):
        result = profile_csv(DIRTY_CSV)
        # 1 missing age + 1 missing score (row 4 duplicate also has missing age+score but
        # Pandas includes that row as a real row for counting purposes)
        # Rows: Alice(ok), Bob(miss age), Charlie(miss score), Bob-dup(miss age + miss score)
        # Total missing = 1 + 1 + 2 = but the duplicate row 4 is: id=2,name=Bob,age=NaN,score=82 NO
        # DIRTY_CSV row 4 is "2,Bob,,82.0" → age=NaN, same as row 2
        # DIRTY_CSV row 3 is "3,Charlie,35," → score=NaN
        # So: age missing in rows 2,4 = 2; score missing in row 3 = 1 → total 3
        assert result["total_missing"] == 3

    def test_dirty_csv_duplicate_count(self):
        result = profile_csv(DIRTY_CSV)
        # Row 4 is an exact duplicate of row 2
        assert result["duplicate_rows"] == 1

    def test_dirty_csv_health_score_below_100(self):
        result = profile_csv(DIRTY_CSV)
        assert result["health_score"] < 100.0

    def test_column_names_returned(self):
        result = profile_csv(CLEAN_CSV)
        col_names = [c["name"] for c in result["columns"]]
        assert col_names == ["id", "name", "age", "score"]

    def test_column_missing_percentages(self):
        result = profile_csv(DIRTY_CSV)
        col_map = {c["name"]: c for c in result["columns"]}
        # 4 rows, age is missing in 2 of them → 50%
        assert col_map["age"]["missing_count"] == 2
        assert col_map["age"]["missing_pct"] == 50.0
        # score is missing in 1 of 4 → 25%
        assert col_map["score"]["missing_count"] == 1
        assert col_map["score"]["missing_pct"] == 25.0

    def test_invalid_csv_raises_value_error(self):
        # A string that is not a valid CSV (deliberate junk)
        with pytest.raises(ValueError):
            profile_csv("not,a,csv\n\"unclosed quote field")

    def test_empty_csv_raises_value_error(self):
        with pytest.raises(ValueError):
            profile_csv("")


# ==============================================================
# Upload Route Integration Tests
# ==============================================================

class TestUploadRoute:
    """Integration tests for /datasets/upload (requires Flask + DB)."""

    # ---- Unauthenticated access ----

    def test_upload_page_requires_login_get(self, client):
        """GET /datasets/upload redirects unauthenticated users to login."""
        response = client.get("/datasets/upload", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_upload_post_requires_login(self, client):
        """POST /datasets/upload redirects unauthenticated users to login."""
        response = client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(CLEAN_CSV)},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    # ---- Successful upload ----

    def test_successful_upload_creates_dataset_row(self, auth_client, app):
        """A valid CSV upload creates a Dataset row in the database."""
        response = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(CLEAN_CSV, "clean_data.csv")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        # Should redirect to the profiling report page
        assert response.status_code == 302
        assert "/datasets/" in response.headers["Location"]

        with app.app_context():
            dataset = Dataset.query.first()
            assert dataset is not None
            assert dataset.filename == "clean_data.csv"
            assert dataset.row_count == 3
            assert dataset.column_count == 4

    def test_successful_upload_creates_profiling_report(self, auth_client, app):
        """A valid CSV upload creates a linked ProfilingReport row."""
        auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(CLEAN_CSV, "clean_data.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        with app.app_context():
            report = ProfilingReport.query.first()
            assert report is not None
            assert float(report.overall_health_score) == 100.0
            assert report.missing_cells_total == 0
            assert report.duplicate_rows_total == 0

    def test_successful_upload_profile_page_renders(self, auth_client):
        """After upload, the profile page renders with key metrics."""
        upload_response = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(CLEAN_CSV, "clean_data.csv")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert upload_response.status_code == 302
        profile_url = upload_response.headers["Location"]
        profile_response = auth_client.get(profile_url, follow_redirects=True)
        assert profile_response.status_code == 200
        # Key profiling metrics must appear in the rendered page
        assert b"clean_data.csv" in profile_response.data
        assert b"100" in profile_response.data          # health score
        assert b"id" in profile_response.data           # column name
        assert b"name" in profile_response.data
        assert b"age" in profile_response.data
        assert b"score" in profile_response.data

    def test_dirty_csv_profiling_accuracy(self, auth_client, app):
        """Dirty CSV (nulls + duplicate) produces correct profiling report values."""
        auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(DIRTY_CSV, "dirty_data.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        with app.app_context():
            dataset = Dataset.query.filter_by(filename="dirty_data.csv").first()
            assert dataset is not None
            assert dataset.row_count == 4   # 4 rows including the duplicate

            report = ProfilingReport.query.filter_by(dataset_id=dataset.id).first()
            assert report is not None
            assert report.missing_cells_total == 3
            assert report.duplicate_rows_total == 1
            assert float(report.overall_health_score) < 100.0

    # ---- Validation: file extension ----

    def test_non_csv_extension_rejected(self, auth_client, app):
        """Uploading a .txt file is rejected with an error flash and no DB row created."""
        response = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file("col1,col2\n1,2\n", "data.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code in (200, 400)
        assert b"Only .csv" in response.data or b"csv" in response.data.lower()
        with app.app_context():
            assert Dataset.query.count() == 0

    def test_excel_extension_rejected(self, auth_client, app):
        """Uploading a .xlsx file is rejected."""
        response = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file("fake xlsx content", "data.xlsx")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code in (200, 400, 413)
        with app.app_context():
            assert Dataset.query.count() == 0

    # ---- Validation: empty file ----

    def test_empty_file_rejected(self, auth_client, app):
        """Uploading an empty .csv file (0 bytes) is rejected."""
        response = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file("", "empty.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code in (200, 400, 413)
        with app.app_context():
            assert Dataset.query.count() == 0

    # ---- Validation: oversized file ----

    def test_oversized_file_rejected(self, auth_client, app):
        """A file larger than 16 MB is rejected without being stored."""
        # Generate a 17 MB payload
        big_content = "a,b\n" + ("x" * 1000 + "," + "y" * 1000 + "\n") * 8500
        assert len(big_content.encode("utf-8")) > 16 * 1024 * 1024, \
            "Test fixture must be larger than 16 MB"

        response = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(big_content, "huge.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code in (200, 400, 413)
        with app.app_context():
            assert Dataset.query.count() == 0

    # ---- Validation: missing file field ----

    def test_missing_file_field_rejected(self, auth_client, app):
        """Submitting the form without selecting a file is rejected."""
        response = auth_client.post(
            "/datasets/upload",
            data={},  # no csv_file key at all
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert response.status_code in (200, 400, 413)
        with app.app_context():
            assert Dataset.query.count() == 0


# ==============================================================
# Dataset List Route Tests
# ==============================================================

class TestDatasetListRoute:
    """Tests for GET /datasets/ — the dataset library page."""

    def test_list_requires_login(self, client):
        response = client.get("/datasets/", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_list_renders_for_authenticated_user(self, auth_client):
        response = auth_client.get("/datasets/", follow_redirects=True)
        assert response.status_code == 200
        assert b"Dataset Library" in response.data or b"My Datasets" in response.data

    def test_list_shows_uploaded_dataset(self, auth_client):
        auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(CLEAN_CSV, "mydata.csv")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        response = auth_client.get("/datasets/", follow_redirects=True)
        assert response.status_code == 200
        assert b"mydata.csv" in response.data


# ==============================================================
# Delete Route Tests
# ==============================================================

class TestDatasetDeleteRoute:
    """Tests for POST /datasets/<id>/delete."""

    def test_delete_requires_login(self, client):
        response = client.post("/datasets/1/delete", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_delete_removes_dataset(self, auth_client, app):
        """After deleting a dataset, it no longer exists in the database."""
        # Upload first
        upload_resp = auth_client.post(
            "/datasets/upload",
            data={"csv_file": _csv_file(CLEAN_CSV, "to_delete.csv")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        with app.app_context():
            dataset = Dataset.query.first()
            assert dataset is not None
            ds_id = dataset.id

        # Delete it
        del_resp = auth_client.post(
            f"/datasets/{ds_id}/delete",
            follow_redirects=True,
        )
        assert del_resp.status_code == 200

        with app.app_context():
            assert db.session.get(Dataset, ds_id) is None
            assert ProfilingReport.query.filter_by(dataset_id=ds_id).count() == 0

    def test_cannot_delete_another_users_dataset(self, app, client):
        """User B cannot delete a dataset owned by User A."""
        # Create User A and upload a dataset
        with app.app_context():
            user_a = User(username="user_a", email="user_a@test.com")
            user_a.set_password("PassA123!")
            db.session.add(user_a)
            db.session.commit()

            ds = Dataset(
                user_id=user_a.id,
                filename="private.csv",
                original_filename="private.csv",
                file_size_bytes=100,
                row_count=2,
                column_count=2,
                raw_csv_data="a,b\n1,2\n3,4\n",
            )
            db.session.add(ds)
            db.session.commit()
            ds_id = ds.id

        # Create User B and log in
        with app.app_context():
            user_b = User(username="user_b", email="user_b@test.com")
            user_b.set_password("PassB123!")
            db.session.add(user_b)
            db.session.commit()

        client.post(
            "/auth/login",
            data={"email": "user_b@test.com", "password": "PassB123!"},
            follow_redirects=True,
        )

        # Attempt to delete User A's dataset — should 404
        response = client.post(f"/datasets/{ds_id}/delete", follow_redirects=False)
        assert response.status_code == 404

        # Dataset must still exist
        with app.app_context():
            assert db.session.get(Dataset, ds_id) is not None
