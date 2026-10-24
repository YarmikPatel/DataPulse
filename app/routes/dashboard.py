"""
Dashboard Routes for DataPulse.
Renders authenticated control center, KPI cards, and recent pipeline activity.
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.config import Config

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def home():
    """Root landing route: redirects to dashboard if logged in, otherwise login page."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


@dashboard_bp.route("/dashboard")
@login_required
def index():
    """
    Main application dashboard.
    Displays user KPIs, pipeline counts, database status, and quick-action shortcuts.
    """
    datasets = current_user.datasets
    pipeline_runs = current_user.pipeline_runs

    # Calculate basic KPIs
    total_datasets = len(datasets)
    total_runs = len(pipeline_runs)
    successful_runs = sum(1 for run in pipeline_runs if run.status == "SUCCESS")

    return render_template(
        "dashboard/index.html",
        user=current_user,
        total_datasets=total_datasets,
        total_runs=total_runs,
        successful_runs=successful_runs,
        recent_datasets=datasets[-5:] if datasets else [],
        recent_runs=pipeline_runs[-5:] if pipeline_runs else [],
        is_supabase=Config.IS_SUPABASE_CONFIGURED,
    )
