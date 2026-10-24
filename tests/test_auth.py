"""
Phase 2 Authentication & Protected Route Tests for DataPulse.
Verifies registration, login, logout, password hashing, validation, and route protection.
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture
def app():
    """Create application configured for testing with in-memory database."""
    test_app = create_app(config_name="testing")
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client for simulating HTTP browser requests."""
    return app.test_client()


def test_register_page_loads(client):
    """GET /auth/register renders registration form successfully."""
    response = client.get("/auth/register")
    assert response.status_code == 200
    assert b"Create an Account" in response.data
    assert b"Username" in response.data


def test_register_success(client, app):
    """POST /auth/register creates user, hashes password, and redirects to login."""
    response = client.post(
        "/auth/register",
        data={
            "username": "alice_analyst",
            "email": "alice@datapulse.test",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        },
        follow_redirects=False,
    )
    # Should redirect to login
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    # Verify user exists in database and password is encrypted
    with app.app_context():
        user = User.query.filter_by(email="alice@datapulse.test").first()
        assert user is not None
        assert user.username == "alice_analyst"
        assert user.password_hash != "SecurePassword123!"
        assert user.check_password("SecurePassword123!") is True


def test_register_duplicate_email(client, app):
    """POST /auth/register with already existing email fails and returns 400."""
    with app.app_context():
        existing = User(username="first_user", email="duplicate@datapulse.test")
        existing.set_password("pass123456")
        db.session.add(existing)
        db.session.commit()

    response = client.post(
        "/auth/register",
        data={
            "username": "second_user",
            "email": "duplicate@datapulse.test",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 400
    assert b"An account with this email address already exists" in response.data


def test_register_duplicate_username(client, app):
    """POST /auth/register with existing username fails and returns 400."""
    with app.app_context():
        existing = User(username="taken_name", email="first@datapulse.test")
        existing.set_password("pass123456")
        db.session.add(existing)
        db.session.commit()

    response = client.post(
        "/auth/register",
        data={
            "username": "taken_name",
            "email": "second@datapulse.test",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 400
    assert b"This username is already taken" in response.data


def test_register_password_mismatch(client):
    """POST /auth/register with mismatched passwords returns 400."""
    response = client.post(
        "/auth/register",
        data={
            "username": "charlie",
            "email": "charlie@datapulse.test",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 400
    assert b"Passwords do not match" in response.data


def test_login_page_loads(client):
    """GET /auth/login renders login form successfully."""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Welcome Back" in response.data


def test_login_success(client, app):
    """POST /auth/login with valid credentials authenticates user and redirects to dashboard."""
    with app.app_context():
        user = User(username="bob_engineer", email="bob@datapulse.test")
        user.set_password("Secret123456!")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "bob@datapulse.test",
            "password": "Secret123456!",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]

    # Verify session persists into dashboard
    dash_response = client.get("/dashboard")
    assert dash_response.status_code == 200
    assert b"bob_engineer" in dash_response.data


def test_login_invalid_password(client, app):
    """POST /auth/login with incorrect password returns 401."""
    with app.app_context():
        user = User(username="diana", email="diana@datapulse.test")
        user.set_password("CorrectPassword123!")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={
            "email": "diana@datapulse.test",
            "password": "WrongPassword!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_login_nonexistent_email(client):
    """POST /auth/login with unknown email returns 401."""
    response = client.post(
        "/auth/login",
        data={
            "email": "unknown@datapulse.test",
            "password": "SomePassword123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 401
    assert b"Invalid email or password" in response.data


def test_protected_dashboard_redirects_anonymous(client):
    """Accessing /dashboard while unauthenticated redirects to login with next param."""
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_root_url_redirects_to_login_when_unauthenticated(client):
    """Accessing / while unauthenticated redirects to /auth/login."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_logout(client, app):
    """GET /auth/logout terminates session and protects dashboard again."""
    with app.app_context():
        user = User(username="eve", email="eve@datapulse.test")
        user.set_password("EvePassword123!")
        db.session.add(user)
        db.session.commit()

    # Log in
    client.post("/auth/login", data={"email": "eve@datapulse.test", "password": "EvePassword123!"})

    # Verify authenticated
    dash_response = client.get("/dashboard")
    assert dash_response.status_code == 200

    # Log out
    logout_response = client.get("/auth/logout", follow_redirects=False)
    assert logout_response.status_code == 302
    assert "/auth/login" in logout_response.headers["Location"]

    # Verify subsequent dashboard request is blocked
    after_logout = client.get("/dashboard", follow_redirects=False)
    assert after_logout.status_code == 302
    assert "/auth/login" in after_logout.headers["Location"]


def test_dashboard_and_html_views_contain_no_cache_headers(client, app):
    """Verify authenticated dashboard and HTML views serve strict no-cache headers."""
    with app.app_context():
        user = User(username="frank", email="frank@datapulse.test")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

    # Log in
    client.post("/auth/login", data={"email": "frank@datapulse.test", "password": "Password123!"})

    # Request dashboard
    response = client.get("/dashboard")
    assert response.status_code == 200

    # Check cache-prevention headers
    cache_control = response.headers.get("Cache-Control", "")
    assert "no-cache" in cache_control
    assert "no-store" in cache_control
    assert "must-revalidate" in cache_control
    assert response.headers.get("Pragma") == "no-cache"
    assert response.headers.get("Expires") == "0"


def test_logout_response_headers_and_subsequent_server_rejection(client, app):
    """Verify logout emits no-cache headers and server strictly rejects subsequent requests."""
    with app.app_context():
        user = User(username="grace", email="grace@datapulse.test")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

    # 1. Log in
    client.post("/auth/login", data={"email": "grace@datapulse.test", "password": "Password123!"})
    
    # 2. Open dashboard
    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert b"grace" in dash.data

    # 3. Log out
    logout = client.get("/auth/logout", follow_redirects=False)
    assert logout.status_code == 302
    cache_control = logout.headers.get("Cache-Control", "")
    assert "no-store" in cache_control
    assert "no-cache" in cache_control

    # 4. Immediate attempt to fetch dashboard again directly
    attempt = client.get("/dashboard", follow_redirects=False)
    assert attempt.status_code == 302
    assert "/auth/login" in attempt.headers["Location"]


def test_post_logout_redirects_and_renders_message_on_login_page(client, app):
    """Submitting POST logout redirects to /auth/login and renders flash on login page."""
    with app.app_context():
        user = User(username="henry", email="henry@datapulse.test")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

    # Log in
    client.post("/auth/login", data={"email": "henry@datapulse.test", "password": "Password123!"})

    # Submit POST to logout with follow_redirects
    response = client.post("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == "/auth/login"
    assert b"You have been logged out successfully" in response.data
    assert b"Welcome Back" in response.data
    assert b"Pipeline & Quality Control Center" not in response.data


def test_logout_with_remember_me_cookie(client, app):
    """Logout properly clears remember cookie and prevents automatic re-login."""
    with app.app_context():
        user = User(username="isla", email="isla@datapulse.test")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

    # Log in with remember=on
    client.post(
        "/auth/login",
        data={"email": "isla@datapulse.test", "password": "Password123!", "remember": "on"},
    )
    assert client.get_cookie("remember_token") is not None

    # Log out
    response = client.post("/auth/logout", follow_redirects=True)
    assert response.status_code == 200
    assert response.request.path == "/auth/login"
    assert b"You have been logged out successfully" in response.data
    assert b"Pipeline & Quality Control Center" not in response.data

    # Attempt to open dashboard directly after logout
    dash_attempt = client.get("/dashboard", follow_redirects=False)
    assert dash_attempt.status_code == 302
    assert "/auth/login" in dash_attempt.headers["Location"]


def test_login_page_with_logged_out_param_purges_any_authenticated_session(client, app):
    """Accessing /auth/login?logged_out=1 forces logout and renders login page, never redirects to dashboard."""
    with app.app_context():
        user = User(username="jack", email="jack@datapulse.test")
        user.set_password("Password123!")
        db.session.add(user)
        db.session.commit()

    # Log in
    client.post("/auth/login", data={"email": "jack@datapulse.test", "password": "Password123!"})
    assert client.get("/dashboard").status_code == 200

    # Visit login with logged_out=1 while still in session
    response = client.get("/auth/login?logged_out=1", follow_redirects=False)
    assert response.status_code == 200
    assert b"Welcome Back" in response.data
    assert b"Pipeline & Quality Control Center" not in response.data

    # Verify session was destroyed
    dash_after = client.get("/dashboard", follow_redirects=False)
    assert dash_after.status_code == 302
    assert "/auth/login" in dash_after.headers["Location"]
