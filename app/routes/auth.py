"""
Authentication Routes for DataPulse.
Handles user registration, login, logout, and session lifecycle.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Renders registration form and creates new user accounts."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Form Validation
        if not username or not email or not password or not confirm_password:
            flash("All fields are required. Please fill in all fields.", "warning")
            return render_template("auth/register.html", username=username, email=email), 400

        if "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "warning")
            return render_template("auth/register.html", username=username, email=email), 400

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template("auth/register.html", username=username, email=email), 400

        if password != confirm_password:
            flash("Passwords do not match. Please re-enter carefully.", "danger")
            return render_template("auth/register.html", username=username, email=email), 400

        # Uniqueness Checks
        if User.query.filter_by(email=email).first():
            flash("An account with this email address already exists.", "danger")
            return render_template("auth/register.html", username=username, email=email), 400

        if User.query.filter_by(username=username).first():
            flash("This username is already taken. Please choose another.", "danger")
            return render_template("auth/register.html", username=username, email=email), 400

        # Create user with hashed password
        new_user = User(username=username, email=email)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Account registered successfully! You can now log in.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return render_template("auth/register.html", username=username, email=email), 500

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticates existing users and starts a session."""
    # If explicitly redirected from logout, ensure session is purged
    if request.args.get("logged_out"):
        if current_user.is_authenticated:
            logout_user()
    elif current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        if not email or not password:
            flash("Please enter both email and password.", "warning")
            return render_template("auth/login.html", email=email), 400

        user = User.query.filter_by(email=email).first()

        # Secure check: checks both existence and password hash
        if not user or not user.check_password(password):
            flash("Invalid email or password. Please try again.", "danger")
            return render_template("auth/login.html", email=email), 401

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.username}!", "success")

        # Redirect to intended URL if protected route redirected here
        next_page = request.args.get("next")
        if not next_page or not next_page.startswith("/"):
            next_page = url_for("dashboard.index")

        return redirect(next_page)

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Terminates user session, clears remember cookie, and redirects to login."""
    if current_user.is_authenticated:
        logout_user()

    flash("You have been logged out successfully.", "info")
    response = redirect(url_for("auth.login", logged_out=1))

    # Comprehensive cookie invalidation with full attribute matching
    config = current_app.config
    cookie_name = config.get("REMEMBER_COOKIE_NAME", "remember_token")
    session_cookie = config.get("SESSION_COOKIE_NAME", "session")
    domain = config.get("REMEMBER_COOKIE_DOMAIN")
    path = config.get("REMEMBER_COOKIE_PATH", "/")
    secure = config.get("REMEMBER_COOKIE_SECURE", False)
    httponly = config.get("REMEMBER_COOKIE_HTTPONLY", True)
    samesite = config.get("REMEMBER_COOKIE_SAMESITE", None)

    response.delete_cookie(
        cookie_name,
        path=path,
        domain=domain,
        secure=secure,
        httponly=httponly,
        samesite=samesite,
    )
    response.delete_cookie(session_cookie, path=path, domain=domain)

    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
