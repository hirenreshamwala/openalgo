"""Parent-child symbol schema with deduplication."""

import os

from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint, create_engine
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


class Symbol(Base):
    __tablename__ = "symbols"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    name = Column(String)
    instrumenttype = Column(String)
    expiry = Column(String)
    strike = Column(Float)
    lotsize = Column(Integer)
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_symbol_identity"),)


class BrokerSymbol(Base):
    __tablename__ = "broker_symbols"
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=False, index=True)
    broker = Column(String, nullable=False, index=True)
    brsymbol = Column(String, nullable=False, index=True)
    brexchange = Column(String, index=True)
    token = Column(String, index=True)
    tick_size = Column(Float)
    contract_value = Column(Float)
    __table_args__ = (
        UniqueConstraint("broker", "brexchange", "token", name="uq_broker_token"),
        UniqueConstraint("broker", "brsymbol", "brexchange", name="uq_broker_brsymbol"),
    )


def init_db():
    from database.db_init_helper import init_db_with_logging
    init_db_with_logging(Base, engine, "Symbols DB", logger)


def upsert_symbol(
    exchange: str,
    symbol: str,
    name: str | None,
    instrumenttype: str | None,
    expiry: str | None,
    strike: float | None,
    lotsize: int | None,
) -> int:
    """Upsert canonical parent symbol. Returns the symbol_id (dedup point)."""
    row = Symbol.query.filter_by(exchange=exchange, symbol=symbol).first()
    if row is None:
        row = Symbol(
            exchange=exchange,
            symbol=symbol,
            name=name,
            instrumenttype=instrumenttype,
            expiry=expiry,
            strike=strike,
            lotsize=lotsize,
        )
        db_session.add(row)
        db_session.flush()
    else:
        # Update mutable canonical fields if changed
        row.name = name or row.name
        row.instrumenttype = instrumenttype or row.instrumenttype
        row.expiry = expiry or row.expiry
        if strike is not None:
            row.strike = strike
        if lotsize is not None:
            row.lotsize = lotsize
    db_session.commit()
    return row.id


def upsert_broker_symbol(
    symbol_id: int,
    broker: str,
    brsymbol: str,
    brexchange: str | None,
    token: str | None,
    tick_size: float | None,
    contract_value: float | None,
) -> int:
    """Upsert broker-specific child row. Returns broker_symbol id."""
    row = BrokerSymbol.query.filter_by(
        broker=broker, brsymbol=brsymbol, brexchange=brexchange
    ).first()
    if row is None:
        row = BrokerSymbol(
            symbol_id=symbol_id,
            broker=broker,
            brsymbol=brsymbol,
            brexchange=brexchange,
            token=token,
            tick_size=tick_size,
            contract_value=contract_value,
        )
        db_session.add(row)
    else:
        row.symbol_id = symbol_id
        row.token = token or row.token
        if tick_size is not None:
            row.tick_size = tick_size
        if contract_value is not None:
            row.contract_value = contract_value
    db_session.commit()
    return row.id


def get_symbol_id(exchange: str, symbol: str) -> int | None:
    """Return the parent symbol_id or None if not found."""
    row = Symbol.query.filter_by(exchange=exchange, symbol=symbol).first()
    return row.id if row else None


def get_token_for_broker(symbol: str, exchange: str, broker: str) -> str | None:
    """Broker-aware token lookup: symbol + exchange + broker → token."""
    parent = Symbol.query.filter_by(exchange=exchange, symbol=symbol).first()
    if parent is None:
        return None
    child = BrokerSymbol.query.filter_by(symbol_id=parent.id, broker=broker).first()
    return child.token if child else None


def get_brsymbol_for_broker(symbol: str, exchange: str, broker: str) -> str | None:
    """Return the broker symbol name for a canonical symbol."""
    parent = Symbol.query.filter_by(exchange=exchange, symbol=symbol).first()
    if parent is None:
        return None
    child = BrokerSymbol.query.filter_by(symbol_id=parent.id, broker=broker).first()
    return child.brsymbol if child else None


def get_oa_symbol_for_broker(brsymbol: str, brexchange: str, broker: str) -> str | None:
    """Reverse lookup: broker symbol → canonical OpenAlgo symbol."""
    child = BrokerSymbol.query.filter_by(
        brsymbol=brsymbol, brexchange=brexchange, broker=broker
    ).first()
    if child is None:
        return None
    parent = Symbol.query.filter_by(id=child.symbol_id).first()
    return parent.symbol if parent else None
