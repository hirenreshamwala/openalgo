import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_user_status.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)

import pytest
from database.user_db import User, add_user, find_user_by_exact_username, init_db

def setup_module():
    init_db()

def test_user_has_status_and_role():
    u = add_user("testuser1", "t1@test.com", "Password1!", is_admin=False)
    assert u is not None
    assert u.status == "pending"
    assert u.role == "user"

def test_admin_has_approved_status():
    u = add_user("adminuser1", "a1@test.com", "Password1!", is_admin=True)
    assert u is not None
    assert u.status == "approved"
    assert u.role == "admin"

def teardown_module():
    import os
    if os.path.exists("test_user_status.db"):
        os.remove("test_user_status.db")
