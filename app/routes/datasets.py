"""
DataPulse Datasets Blueprint
==============================
Handles all CSV upload, profiling display, dataset listing, and deletion routes.

Routes:
    GET  /datasets              – list all datasets owned by the logged-in user
    GET  /datasets/upload       – render the upload form
    POST /datasets/upload       – process uploaded CSV file
    GET  /datasets/<id>/profile – view profiling report for a dataset
    POST /datasets/<id>/delete  – delete a dataset (and its profiling reports via cascade)
"""
import io
from datetime import datetime, timezone

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from app.extensions import db
from app.models import Dataset, ProfilingReport
from app.services.profiling_service import profile_csv

# ----------------------------------------------------------------
# Blueprint Registration
# ----------------------------------------------------------------
datasets_bp = Blueprint("datasets", __name__, url_prefix="/datasets")

# Maximum upload size: 16 MB expressed in bytes
MAX_UPLOAD_BYTES = 16 * 1024 * 1024  # 16 MB


# ----------------------------------------------------------------
# Error Handler: 413 Request Entity Too Large
# Flask raises this automatically when request body exceeds
# MAX_CONTENT_LENGTH set in the app config.
# ----------------------------------------------------------------
@datasets_bp.errorhandler(RequestEntityTooLarge)
def handle_oversize_upload(e):
    """Return a user-friendly 413 page with a flash message."""
    flash("File exceeds the 16 MB size limit. Please upload a smaller file.", "danger")
    return render_template("datasets/upload.html"), 413


# ----------------------------------------------------------------
# Helper: validate a Flask FileStorage object before processing
# ----------------------------------------------------------------
def _validate_upload(file_storage):
    """
    Validates the uploaded file object.

    Returns:
        (True, None) if valid
        (False, error_message_string) if invalid
    """
    # 1. A file must actually be selected
    if not file_storage or file_storage.filename == "":
        return False, "No file was selected. Please choose a CSV file."

    # 2. Extension must be .csv (case-insensitive)
    filename = file_storage.filename
    if not filename.lower().endswith(".csv"):
        return False, "Only .csv files are accepted. Please upload a valid CSV file."

    # 3. Check Content-Length header before reading the body (fast-fail for huge files)
    content_length = request.content_length
    if content_length and content_length > MAX_UPLOAD_BYTES:
        return False, "File exceeds the 16 MB size limit. Please upload a smaller file."

    return True, None


# ----------------------------------------------------------------
# GET /datasets — Dataset List
# ----------------------------------------------------------------
@datasets_bp.route("/", methods=["GET"])
@login_required
def list_datasets():
    """Display all CSV datasets uploaded by the current user, newest first."""
    datasets = (
        Dataset.query
        .filter_by(user_id=current_user.id)
        .order_by(Dataset.created_at.desc())
        .all()
    )
    return render_template("datasets/list.html", datasets=datasets)


# ----------------------------------------------------------------
# GET + POST /datasets/upload — Upload Form & Handler
# ----------------------------------------------------------------
@datasets_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Render the upload form (GET) and process CSV upload (POST)."""
    if request.method == "GET":
        return render_template("datasets/upload.html")

    # ---- POST: Process the uploaded file ----
    uploaded_file = request.files.get("csv_file")

    # Basic file object validation
    valid, error_msg = _validate_upload(uploaded_file)
    if not valid:
        flash(error_msg, "danger")
        return render_template("datasets/upload.html"), 400

    # Read file bytes into memory — no disk writes needed/wanted
    try:
        file_bytes = uploaded_file.read()
    except Exception:
        flash("Failed to read the uploaded file. Please try again.", "danger")
        return render_template("datasets/upload.html"), 500

    # Enforce size limit after reading (handles cases where Content-Length header is absent)
    if len(file_bytes) == 0:
        flash("The uploaded file is empty. Please upload a CSV file with data.", "danger")
        return render_template("datasets/upload.html"), 400

    if len(file_bytes) > MAX_UPLOAD_BYTES:
        flash("File exceeds the 16 MB size limit. Please upload a smaller file.", "danger")
        return render_template("datasets/upload.html"), 400

    # Decode bytes to UTF-8 string
    try:
        csv_text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Try latin-1 as a fallback (common for older Excel-exported CSVs)
        try:
            csv_text = file_bytes.decode("latin-1")
        except UnicodeDecodeError:
            flash(
                "Could not read the file encoding. Please save the CSV as UTF-8 and try again.",
                "danger",
            )
            return render_template("datasets/upload.html"), 400

    # Run Pandas profiling
    try:
        profile = profile_csv(csv_text)
    except ValueError as exc:
        flash(f"Invalid CSV structure: {exc}", "danger")
        return render_template("datasets/upload.html"), 400

    # Sanitize the original filename for safe storage
    safe_name = secure_filename(uploaded_file.filename)
    if not safe_name:
        safe_name = "upload.csv"

    # ---- Persist Dataset row ----
    dataset = Dataset(
        user_id=current_user.id,
        filename=safe_name,
        original_filename=uploaded_file.filename,
        file_size_bytes=len(file_bytes),
        row_count=profile["row_count"],
        column_count=profile["column_count"],
        raw_csv_data=csv_text,
    )
    db.session.add(dataset)
    db.session.flush()  # assigns dataset.id without full commit yet

    # ---- Persist ProfilingReport row ----
    report = ProfilingReport(
        dataset_id=dataset.id,
        summary_stats=profile,          # full profiling dict stored as JSON
        missing_cells_total=profile["total_missing"],
        duplicate_rows_total=profile["duplicate_rows"],
        overall_health_score=profile["health_score"],
    )
    db.session.add(report)
    db.session.commit()

    flash(
        f"Dataset '{safe_name}' uploaded successfully — {profile['row_count']:,} rows, "
        f"{profile['column_count']} columns profiled.",
        "success",
    )
    return redirect(url_for("datasets.view_profile", dataset_id=dataset.id))


# ----------------------------------------------------------------
# GET /datasets/<id>/profile — Profiling Report View
# ----------------------------------------------------------------
@datasets_bp.route("/<int:dataset_id>/profile", methods=["GET"])
@login_required
def view_profile(dataset_id):
    """Show the data profiling report for a single dataset."""
    # Fetch dataset — ensure it belongs to the logged-in user
    dataset = Dataset.query.filter_by(
        id=dataset_id, user_id=current_user.id
    ).first_or_404()

    # Fetch the most recent profiling report for this dataset
    report = (
        ProfilingReport.query
        .filter_by(dataset_id=dataset.id)
        .order_by(ProfilingReport.created_at.desc())
        .first()
    )
    if report is None:
        abort(404)

    return render_template(
        "datasets/profile.html",
        dataset=dataset,
        report=report,
    )


# ----------------------------------------------------------------
# POST /datasets/<id>/delete — Delete Dataset
# ----------------------------------------------------------------
@datasets_bp.route("/<int:dataset_id>/delete", methods=["POST"])
@login_required
def delete_dataset(dataset_id):
    """Delete a dataset and all its profiling reports (CASCADE handles DB side)."""
    dataset = Dataset.query.filter_by(
        id=dataset_id, user_id=current_user.id
    ).first_or_404()

    filename = dataset.filename
    db.session.delete(dataset)
    db.session.commit()

    flash(f"Dataset '{filename}' has been deleted.", "warning")
    return redirect(url_for("datasets.list_datasets"))
