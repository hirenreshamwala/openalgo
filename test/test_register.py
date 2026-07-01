"""
Tests for multi-tenant registration and login gate.

Run with:
    DATABASE_URL='sqlite:///./test_register.db' \
    API_KEY_PEPPER=$(python3 -c "print('a'*32)") \
    FERNET_SALT=$(python3 -c "print('b'*32)") \
    /Users/hirenreshamwala/anaconda3/bin/python -m pytest test/test_register.py -v
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_register.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)
os.environ.setdefault("MULTI_TENANT", "true")
os.environ.setdefault("SECRET_KEY", "testsecret")

import uuid

from database.user_db import (
    Base,
    add_user,
    approve_user,
    check_mt_login_allowed,
    db_session,
    engine,
    reject_user,
)


def _init_db():
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Unit tests: add_user and status field
# ---------------------------------------------------------------------------

def test_non_admin_user_gets_pending_status():
    _init_db()
    uname = f"testuser_{uuid.uuid4().hex[:8]}"
    user = add_user(uname, f"{uname}@example.com", "Password1!")
    assert user is not None
    assert user.status == "pending"
    db_session.remove()


def test_admin_user_gets_approved_status():
    _init_db()
    uname = f"adminuser_{uuid.uuid4().hex[:8]}"
    user = add_user(uname, f"{uname}@example.com", "Password1!", is_admin=True)
    assert user is not None
    assert user.status == "approved"
    db_session.remove()


# ---------------------------------------------------------------------------
# Unit tests: check_mt_login_allowed helper (in database/user_db.py)
# ---------------------------------------------------------------------------

def test_check_mt_login_allowed_pending():
    _init_db()
    uname = f"pending_{uuid.uuid4().hex[:8]}"
    add_user(uname, f"{uname}@example.com", "Password1!")

    allowed, msg = check_mt_login_allowed(uname)
    assert allowed is False
    assert "pending" in msg.lower()
    db_session.remove()


def test_check_mt_login_allowed_approved():
    _init_db()
    uname = f"approved_{uuid.uuid4().hex[:8]}"
    add_user(uname, f"{uname}@example.com", "Password1!")
    approve_user(uname)

    allowed, msg = check_mt_login_allowed(uname)
    assert allowed is True
    assert msg == ""
    db_session.remove()


def test_check_mt_login_allowed_rejected():
    _init_db()
    uname = f"rejected_{uuid.uuid4().hex[:8]}"
    add_user(uname, f"{uname}@example.com", "Password1!")
    reject_user(uname)

    allowed, msg = check_mt_login_allowed(uname)
    assert allowed is False
    assert "rejected" in msg.lower()
    db_session.remove()


def test_check_mt_login_allowed_nonexistent_user():
    """Unknown username should not block (authenticate_user handles that)."""
    _init_db()
    allowed, msg = check_mt_login_allowed("no_such_user_xyz")
    assert allowed is True
    db_session.remove()
