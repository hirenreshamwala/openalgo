import os

# Set environment variables before any imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_admin_users.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)
os.environ.setdefault("MULTI_TENANT", "true")
os.environ.setdefault("SECRET_KEY", "testsecret")

import pytest
from database.user_db import add_user, approve_user, reject_user, get_all_users, get_pending_users, init_db


@pytest.fixture(scope="session")
def setup_db():
    """Initialize the test database once per test session."""
    init_db()
    yield
    # Cleanup: delete the test database file after tests
    if os.path.exists("test_admin_users.db"):
        os.remove("test_admin_users.db")


@pytest.fixture(autouse=True)
def clean_db_before_test(setup_db):
    """Clean up the database before each test."""
    from database.user_db import db_session, User
    db_session.query(User).delete()
    db_session.commit()
    yield


def test_approve_user_success(setup_db):
    """Test approving a pending user."""
    # Create a pending user
    user = add_user("pendinguser1", "p1@test.com", "Password1!", is_admin=False)
    assert user is not None
    assert user.status == "pending"

    # Approve the user
    result = approve_user("pendinguser1")
    assert result is True

    # Verify the user status changed
    from database.user_db import find_user_by_exact_username
    updated_user = find_user_by_exact_username("pendinguser1")
    assert updated_user is not None
    assert updated_user.status == "approved"


def test_approve_user_not_found(setup_db):
    """Test approving a non-existent user."""
    result = approve_user("nonexistent")
    assert result is False


def test_reject_user_success(setup_db):
    """Test rejecting a pending user."""
    # Create a pending user
    user = add_user("pendinguser2", "p2@test.com", "Password1!", is_admin=False)
    assert user is not None
    assert user.status == "pending"

    # Reject the user
    result = reject_user("pendinguser2")
    assert result is True

    # Verify the user status changed
    from database.user_db import find_user_by_exact_username
    updated_user = find_user_by_exact_username("pendinguser2")
    assert updated_user is not None
    assert updated_user.status == "rejected"


def test_reject_user_not_found(setup_db):
    """Test rejecting a non-existent user."""
    result = reject_user("nonexistent")
    assert result is False


def test_get_all_users(setup_db):
    """Test getting all users."""
    # Add multiple users
    add_user("user1", "u1@test.com", "Password1!", is_admin=False)
    add_user("user2", "u2@test.com", "Password1!", is_admin=False)
    add_user("admin1", "admin@test.com", "Password1!", is_admin=True)

    # Get all users (should only return non-admin users)
    users = get_all_users()
    assert len(users) == 2
    usernames = {u.username for u in users}
    assert usernames == {"user1", "user2"}


def test_get_pending_users(setup_db):
    """Test getting pending users."""
    # Add users with different statuses
    add_user("pending1", "p1@test.com", "Password1!", is_admin=False)
    add_user("pending2", "p2@test.com", "Password1!", is_admin=False)

    # Approve one user
    approve_user("pending1")

    # Get pending users
    pending = get_pending_users()
    assert len(pending) == 1
    assert pending[0].username == "pending2"
    assert pending[0].status == "pending"


def test_get_pending_users_empty(setup_db):
    """Test getting pending users when none exist."""
    add_user("approved_user", "a@test.com", "Password1!", is_admin=False)
    approve_user("approved_user")

    pending = get_pending_users()
    assert len(pending) == 0


def test_approve_then_reject_user(setup_db):
    """Test that a user can be rejected after being approved."""
    # Create and approve a user
    add_user("testuser", "t@test.com", "Password1!", is_admin=False)
    approve_user("testuser")

    # Verify approved
    from database.user_db import find_user_by_exact_username
    user = find_user_by_exact_username("testuser")
    assert user.status == "approved"

    # Now reject
    result = reject_user("testuser")
    assert result is True

    # Verify rejected
    user = find_user_by_exact_username("testuser")
    assert user.status == "rejected"
