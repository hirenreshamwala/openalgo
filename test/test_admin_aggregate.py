"""Unit tests for admin aggregate helpers in blueprints/admin.py."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_admin_agg.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)
os.environ["MULTI_TENANT"] = "true"

from unittest.mock import MagicMock, patch


def test_fetch_user_data_empty_list():
    """_fetch_user_data returns empty list when no users passed."""
    from blueprints.admin import _fetch_user_data

    result = _fetch_user_data(lambda tok, broker: {"ok": True}, [])
    assert result == []


def test_fetch_user_data_single_user():
    """_fetch_user_data calls fetch_fn and wraps result per-user."""
    from blueprints.admin import _fetch_user_data

    def mock_fetch(auth_token, broker):
        return {"orders": []}

    result = _fetch_user_data(mock_fetch, [("alice", "tok123", "zerodha")])
    assert len(result) == 1
    assert result[0]["username"] == "alice"
    assert result[0]["data"] == {"orders": []}


def test_fetch_user_data_multiple_users():
    """_fetch_user_data fans out to all users concurrently."""
    from blueprints.admin import _fetch_user_data

    calls = []

    def mock_fetch(auth_token, broker):
        calls.append((auth_token, broker))
        return {"result": "ok"}

    users = [
        ("alice", "tok_a", "zerodha"),
        ("bob", "tok_b", "angel"),
        ("carol", "tok_c", "dhan"),
    ]
    result = _fetch_user_data(mock_fetch, users)
    assert len(result) == 3
    usernames = {r["username"] for r in result}
    assert usernames == {"alice", "bob", "carol"}
    # All calls were made
    assert len(calls) == 3


def test_fetch_user_data_handles_exception():
    """_fetch_user_data captures per-user exceptions without crashing."""
    from blueprints.admin import _fetch_user_data

    def failing_fetch(auth_token, broker):
        raise RuntimeError("broker down")

    result = _fetch_user_data(failing_fetch, [("dave", "tok_d", "zerodha")])
    assert len(result) == 1
    assert result[0]["username"] == "dave"
    assert result[0]["data"] is None
    assert "broker down" in result[0]["error"]


def test_get_approved_users_auth_returns_list():
    """_get_approved_users_auth returns a list (mocked DB)."""
    from blueprints.admin import _get_approved_users_auth

    mock_user = MagicMock()
    mock_user.username = "alice"
    mock_user.status = "approved"

    mock_auth_row = MagicMock()
    mock_auth_row.broker = "zerodha"

    with (
        patch("blueprints.admin.get_all_users", return_value=[mock_user]),
        patch("database.auth_db.Auth.query") as mock_query,
        patch("database.auth_db.get_auth_token", return_value="decrypted_tok"),
    ):
        mock_query.filter_by.return_value.filter_by.return_value.first.return_value = mock_auth_row
        result = _get_approved_users_auth()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == ("alice", "decrypted_tok", "zerodha")


def test_get_approved_users_auth_skips_non_approved():
    """_get_approved_users_auth skips users whose status is not 'approved'."""
    from blueprints.admin import _get_approved_users_auth

    pending = MagicMock()
    pending.username = "pending_user"
    pending.status = "pending"

    with patch("blueprints.admin.get_all_users", return_value=[pending]):
        result = _get_approved_users_auth()

    assert result == []


def test_get_approved_users_auth_skips_no_auth_row():
    """_get_approved_users_auth skips users with no auth record."""
    from blueprints.admin import _get_approved_users_auth

    user = MagicMock()
    user.username = "nologin"
    user.status = "approved"

    with (
        patch("blueprints.admin.get_all_users", return_value=[user]),
        patch("database.auth_db.Auth.query") as mock_query,
    ):
        mock_query.filter_by.return_value.filter_by.return_value.first.return_value = None
        result = _get_approved_users_auth()

    assert result == []
