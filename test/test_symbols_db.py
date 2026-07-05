import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_symbols.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)

from database.symbols_db import init_db, upsert_symbol, upsert_broker_symbol, get_symbol_id

def setup_module():
    init_db()

def test_upsert_creates_parent():
    sid = upsert_symbol("NSE", "SBIN", "State Bank of India", "EQ", None, None, 1)
    assert sid is not None and sid > 0

def test_upsert_deduplicates_parent():
    sid1 = upsert_symbol("NSE", "SBIN", "State Bank of India", "EQ", None, None, 1)
    sid2 = upsert_symbol("NSE", "SBIN", "State Bank of India", "EQ", None, None, 1)
    assert sid1 == sid2  # same row reused

def test_two_brokers_share_parent():
    sid = upsert_symbol("NSE", "RELIANCE", "Reliance Industries", "EQ", None, None, 1)
    bid1 = upsert_broker_symbol(sid, "zerodha", "RELIANCE", "NSE", "738561", 0.05, None)
    bid2 = upsert_broker_symbol(sid, "dhan", "RELIANCE", "NSE", "1333", 0.05, None)
    assert bid1 != bid2  # different child rows
    assert get_symbol_id("NSE", "RELIANCE") == sid

def teardown_module():
    if os.path.exists("test_symbols.db"):
        os.remove("test_symbols.db")
