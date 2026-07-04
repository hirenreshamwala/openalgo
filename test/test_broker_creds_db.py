import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_broker_creds.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)

from database.broker_creds_db import (
    init_db,
    save_broker_credentials,
    get_broker_credentials,
)

def setup_module():
    init_db()

def test_save_and_retrieve_credentials():
    result = save_broker_credentials(
        username="testuser",
        broker="zerodha",
        api_key="my_api_key",
        api_secret="my_secret",
        extras={"redirect_url": "http://localhost/callback"},
    )
    assert result is True
    creds = get_broker_credentials("testuser", "zerodha")
    assert creds is not None
    assert creds["api_key"] == "my_api_key"
    assert creds["api_secret"] == "my_secret"
    assert creds["extras"]["redirect_url"] == "http://localhost/callback"

def test_missing_credentials_returns_none():
    creds = get_broker_credentials("nonexistent", "zerodha")
    assert creds is None

def teardown_module():
    if os.path.exists("test_broker_creds.db"):
        os.remove("test_broker_creds.db")
