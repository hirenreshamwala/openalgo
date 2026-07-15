import os
os.environ["TEST_KEY"] = "env_value"

from utils.broker_context import get_broker_credential, set_broker_credentials


def test_fallback_to_env():
    """When no context is set, get_broker_credential falls back to os.getenv."""
    # No context set
    assert get_broker_credential("TEST_KEY") == "env_value"


def test_context_overrides_env():
    """When context is set, it overrides environment variables."""
    set_broker_credentials({"TEST_KEY": "context_value"})
    assert get_broker_credential("TEST_KEY") == "context_value"


def test_missing_key_returns_none():
    """When a key is missing from both context and env, returns None."""
    set_broker_credentials({})
    assert get_broker_credential("NONEXISTENT_KEY_XYZ") is None
