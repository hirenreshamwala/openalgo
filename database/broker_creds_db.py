# database/broker_creds_db.py
"""Per-user encrypted broker credential storage."""

import json
import os

from sqlalchemy import Column, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy.pool import NullPool

from utils.logging import get_logger

logger = get_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL, poolclass=NullPool, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL, pool_size=50, max_overflow=100, pool_timeout=10)

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


class UserBrokerCredentials(Base):
    __tablename__ = "user_broker_credentials"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, index=True)
    broker = Column(String(50), nullable=False, index=True)
    api_key_enc = Column(Text, nullable=False)      # Fernet-encrypted
    api_secret_enc = Column(Text, nullable=False)   # Fernet-encrypted
    extras_enc = Column(Text, nullable=True)         # Fernet-encrypted JSON
    __table_args__ = (
        UniqueConstraint("username", "broker", name="uq_user_broker"),
    )


def init_db():
    from database.db_init_helper import init_db_with_logging
    init_db_with_logging(Base, engine, "Broker Creds DB", logger)


def save_broker_credentials(
    username: str,
    broker: str,
    api_key: str,
    api_secret: str,
    extras: dict | None = None,
) -> bool:
    """Encrypt and persist per-user broker credentials. Upserts on (username, broker)."""
    from database.auth_db import encrypt_token

    try:
        row = UserBrokerCredentials.query.filter_by(username=username, broker=broker).first()
        if row is None:
            row = UserBrokerCredentials(username=username, broker=broker)
            db_session.add(row)
        row.api_key_enc = encrypt_token(api_key)
        row.api_secret_enc = encrypt_token(api_secret)
        row.extras_enc = encrypt_token(json.dumps(extras or {}))
        db_session.commit()
        return True
    except Exception:
        logger.exception("Failed to save broker credentials for %s/%s", username, broker)
        db_session.rollback()
        return False


def get_broker_credentials(username: str, broker: str) -> dict | None:
    """Return decrypted credentials dict or None if not found."""
    from database.auth_db import safe_decrypt_token

    row = UserBrokerCredentials.query.filter_by(username=username, broker=broker).first()
    if row is None:
        return None
    return {
        "api_key": safe_decrypt_token(row.api_key_enc) or row.api_key_enc,
        "api_secret": safe_decrypt_token(row.api_secret_enc) or row.api_secret_enc,
        "extras": json.loads(safe_decrypt_token(row.extras_enc) or "{}"),
    }


def list_user_brokers(username: str) -> list[str]:
    """Return the list of broker names the user has saved credentials for."""
    rows = (
        UserBrokerCredentials.query.filter_by(username=username)
        .order_by(UserBrokerCredentials.broker)
        .all()
    )
    return [r.broker for r in rows]


def delete_broker_credentials(username: str, broker: str) -> bool:
    """Delete a user's stored credentials for a broker. Returns True if a row was removed."""
    try:
        row = UserBrokerCredentials.query.filter_by(username=username, broker=broker).first()
        if row is None:
            return False
        db_session.delete(row)
        db_session.commit()
        return True
    except Exception:
        logger.exception("Failed to delete broker credentials for %s/%s", username, broker)
        db_session.rollback()
        return False
