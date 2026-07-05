import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_token_lookup.db")
os.environ.setdefault("API_KEY_PEPPER", "a" * 32)
os.environ.setdefault("FERNET_SALT", "b" * 32)
os.environ["MULTI_TENANT"] = "true"

from database.symbols_db import init_db, upsert_symbol, upsert_broker_symbol
from database.token_db_enhanced import get_token_mt, get_br_symbol_mt, get_oa_symbol_mt


def setup_module():
    init_db()
    sid = upsert_symbol("NSE", "INFY", "Infosys", "EQ", None, None, 1)
    upsert_broker_symbol(sid, "zerodha", "INFY", "NSE", "408065", 0.05, None)
    upsert_broker_symbol(sid, "dhan", "INFY", "NSE", "1594", 0.05, None)


def test_get_token_mt_zerodha():
    assert get_token_mt("INFY", "NSE", "zerodha") == "408065"


def test_get_token_mt_dhan():
    assert get_token_mt("INFY", "NSE", "dhan") == "1594"


def test_get_br_symbol_mt():
    assert get_br_symbol_mt("INFY", "NSE", "zerodha") == "INFY"


def test_get_oa_symbol_mt():
    assert get_oa_symbol_mt("INFY", "NSE", "zerodha") == "INFY"


def teardown_module():
    if os.path.exists("test_token_lookup.db"):
        os.remove("test_token_lookup.db")
