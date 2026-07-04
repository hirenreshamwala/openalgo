"""
Context-variable based broker credential resolver.

In multi-tenant mode, credentials are loaded per-request from the
UserBrokerCredentials table and placed in a contextvars.ContextVar.
get_broker_credential() checks the context first, then falls back to
os.getenv() so single-tenant installs are unaffected.

Thread-safety: contextvars are isolated per-thread/greenlet (safe under
eventlet's single worker model and stdlib threading).
"""

import contextvars
import os

_CRED: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "broker_credentials", default=None
)


def set_broker_credentials(creds: dict) -> None:
    """Set broker credentials for the current request context."""
    _CRED.set(creds)


def clear_broker_credentials() -> None:
    """Clear credentials from context (call in teardown hooks)."""
    _CRED.set(None)


def get_broker_credential(key: str) -> str | None:
    """Resolve a broker credential by env-var name.

    Returns the context value if set, otherwise falls back to os.getenv(key).
    In single-tenant mode (MULTI_TENANT=false), context is never populated
    so this always falls back to env vars — identical to the original behavior.
    """
    creds = _CRED.get()
    if creds is not None:
        return creds.get(key) or os.getenv(key)
    return os.getenv(key)
