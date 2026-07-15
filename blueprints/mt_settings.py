# blueprints/mt_settings.py
"""Multi-tenant per-user settings: broker credential management.

Only active when MULTI_TENANT=true. Each user stores their own broker
API key/secret (encrypted) in UserBrokerCredentials, keyed by (username, broker).
The instance-wide .env broker config is not used in multi-tenant mode.
"""

import os
import time
from urllib.parse import quote, unquote, urlsplit

import httpx
from flask import Blueprint, jsonify, redirect, request, session, url_for
from flask_wtf.csrf import generate_csrf

from database.broker_creds_db import (
    delete_broker_credentials,
    get_broker_credentials,
    list_user_brokers,
    save_broker_credentials,
)
from utils.logging import get_logger
from utils.session import require_user_session


# Cache the server's public egress IP — it is stable, so avoid an external call
# on every page render. Refreshed hourly.
_ip_cache = {"ip": None, "ts": 0.0}
_IP_TTL = 3600.0


def _get_server_public_ip() -> str | None:
    """Return the server's public outbound IP (what a broker sees on a direct
    connection), or None if it can't be determined. Cached for 1 hour.

    A direct httpx call is used deliberately (not the context-aware pooled
    client) so the answer is the SERVER's IP, never a user's proxy IP.
    """
    now = time.time()
    if _ip_cache["ip"] and now - _ip_cache["ts"] < _IP_TTL:
        return _ip_cache["ip"]
    for url in ("https://api.ipify.org", "https://checkip.amazonaws.com", "https://ifconfig.me/ip"):
        try:
            resp = httpx.get(url, timeout=5.0)
            if resp.status_code == 200:
                ip = resp.text.strip()
                if ip:
                    _ip_cache["ip"] = ip
                    _ip_cache["ts"] = now
                    return ip
        except Exception:
            continue
    return None


def _build_proxy_url(scheme: str, host: str, port: str, user: str, password: str) -> str:
    """Assemble a proxy URL from separate parts. Returns '' if no host given.

    Credentials are percent-encoded so passwords with @ : / etc. are safe.
    """
    host = (host or "").strip()
    if not host:
        return ""
    scheme = (scheme or "http").strip().lower()
    if scheme not in ("http", "https"):
        scheme = "http"
    auth = ""
    user = (user or "").strip()
    password = password or ""
    if user:
        auth = quote(user, safe="")
        if password:
            auth += ":" + quote(password, safe="")
        auth += "@"
    port = (port or "").strip()
    netloc = f"{host}:{port}" if port else host
    return f"{scheme}://{auth}{netloc}"


def _parse_proxy_url(url: str | None) -> dict:
    """Split a stored proxy URL back into parts for display/editing.

    Returns {scheme, host, port, user, password}. Password is returned decoded
    so it can prefill the edit form; the display path masks it separately.
    """
    parts = {"scheme": "http", "host": "", "port": "", "user": "", "password": ""}
    if not url:
        return parts
    sp = urlsplit(url)
    parts["scheme"] = sp.scheme or "http"
    parts["host"] = sp.hostname or ""
    parts["port"] = str(sp.port) if sp.port else ""
    parts["user"] = unquote(sp.username) if sp.username else ""
    parts["password"] = unquote(sp.password) if sp.password else ""
    return parts

logger = get_logger(__name__)

mt_settings_bp = Blueprint("mt_settings_bp", __name__, url_prefix="/mt")

# Canonical list of supported brokers (id -> display name). Mirrors the
# frontend allBrokers list in frontend/src/pages/BrokerSelect.tsx.
SUPPORTED_BROKERS = [
    ("fivepaisa", "5 Paisa"),
    ("fivepaisaxts", "5 Paisa (XTS)"),
    ("aliceblue", "Alice Blue"),
    ("angel", "Angel One"),
    ("arrow", "Arrow"),
    ("compositedge", "CompositEdge"),
    ("dhan", "Dhan"),
    ("deltaexchange", "Delta Exchange"),
    ("indmoney", "IndMoney"),
    ("dhan_sandbox", "Dhan (Sandbox)"),
    ("definedge", "Definedge"),
    ("firstock", "Firstock"),
    ("flattrade", "Flattrade"),
    ("motilal", "Motilal Oswal"),
    ("fyers", "Fyers"),
    ("groww", "Groww"),
    ("ibulls", "Ibulls"),
    ("iifl", "IIFL"),
    ("iiflcapital", "IIFL Capital"),
    ("jainamxts", "JainamXts"),
    ("kotak", "Kotak Securities"),
    ("mstock", "mStock by Mirae Asset"),
    ("nubra", "Nubra"),
    ("paytm", "Paytm Money"),
    ("pocketful", "Pocketful"),
    ("rmoney", "RMoney"),
    ("samco", "Samco"),
    ("shoonya", "Shoonya"),
    ("tradejini", "Tradejini"),
    ("tradesmart", "TradeSmart"),
    ("upstox", "Upstox"),
    ("wisdom", "Wisdom Capital"),
    ("zebu", "Zebu"),
    ("zerodha", "Zerodha"),
]
BROKER_DISPLAY = dict(SUPPORTED_BROKERS)


def _mt_enabled() -> bool:
    return os.getenv("MULTI_TENANT", "false").lower() == "true"


@mt_settings_bp.route("/broker-credentials", methods=["GET"])
@require_user_session
def broker_credentials_page():
    """Legacy path — the credential manager is now the React page at
    /broker-credentials (inside the app shell). Redirect there."""
    if not _mt_enabled():
        return "Not available", 404
    return redirect("/broker-credentials")


@mt_settings_bp.route("/broker-credentials", methods=["POST"])
@require_user_session
def save_broker_credentials_route():
    """Save/update the signed-in user's credentials for a broker."""
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404

    username = session.get("user")
    broker = (request.form.get("broker") or "").strip().lower()
    api_key = (request.form.get("api_key") or "").strip()
    api_secret = (request.form.get("api_secret") or "").strip()

    proxy_host = (request.form.get("proxy_host") or "").strip()
    proxy_port = (request.form.get("proxy_port") or "").strip()
    proxy_url = _build_proxy_url(
        request.form.get("proxy_scheme", "http"),
        proxy_host,
        proxy_port,
        request.form.get("proxy_user", ""),
        request.form.get("proxy_pass", ""),
    )

    page = url_for("mt_settings_bp.broker_credentials_page")

    if broker not in BROKER_DISPLAY:
        return redirect(f"{page}?error=Invalid+broker")

    # One broker per user. Allow updating the already-configured broker, but
    # reject adding a second, different one (defense-in-depth behind the locked
    # UI dropdown). The user must remove the current broker first to switch.
    existing = list_user_brokers(username)
    if existing and broker not in existing:
        return redirect(
            f"{page}?error=Only+one+broker+per+account.+Remove+the+current+broker+to+switch."
        )

    if not api_key or not api_secret:
        return redirect(f"{page}?error=API+key+and+secret+are+required")
    if proxy_host and proxy_port and not proxy_port.isdigit():
        return redirect(f"{page}?error=Proxy+port+must+be+a+number")

    if not save_broker_credentials(username, broker, api_key, api_secret, proxy_url=proxy_url):
        return redirect(f"{page}?error=Failed+to+save+credentials")
    logger.info("User %s saved broker credentials for %s", username, broker)
    return redirect(f"{page}?saved={broker}")


@mt_settings_bp.route("/broker-credentials/<broker>/delete", methods=["POST"])
@require_user_session
def delete_broker_credentials_route(broker):
    """Remove the signed-in user's credentials for a broker."""
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404

    username = session.get("user")
    broker = broker.strip().lower()
    delete_broker_credentials(username, broker)
    logger.info("User %s removed broker credentials for %s", username, broker)
    page = url_for("mt_settings_bp.broker_credentials_page")
    return redirect(f"{page}?removed={broker}")


@mt_settings_bp.route("/broker-config", methods=["GET"])
@require_user_session
def broker_config_mt():
    """Return the signed-in user's configured brokers for the /broker dropdown.

    Each entry carries the broker id, its API key, and the dynamically built
    redirect URL ({HOST_SERVER}/{broker}/callback).
    """
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404

    username = session.get("user")
    app_url = os.getenv("HOST_SERVER", "http://127.0.0.1:5000").rstrip("/")

    brokers = []
    for bid in list_user_brokers(username):
        creds = get_broker_credentials(username, bid)
        if not creds:
            continue
        brokers.append(
            {
                "broker_name": bid,
                "broker_api_key": creds["api_key"],
                "redirect_url": f"{app_url}/{bid}/callback",
            }
        )

    return jsonify(status="success", multi_tenant=True, brokers=brokers)


# ============================================================================
# JSON API for the React broker-credentials page (/broker-credentials)
# ============================================================================


@mt_settings_bp.route("/api/broker-credentials", methods=["GET"])
@require_user_session
def api_broker_credentials_get():
    """Return the signed-in user's currently configured broker + proxy parts
    (never the secrets) for the React manager page."""
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404
    username = session.get("user")
    brokers = list_user_brokers(username)
    current = brokers[0] if brokers else None
    proxy = _parse_proxy_url(None)
    if current:
        creds = get_broker_credentials(username, current) or {}
        proxy = _parse_proxy_url(creds.get("proxy_url"))
    # Do not leak the proxy password to the client; only say whether one is set.
    has_pass = bool(proxy.pop("password", ""))
    return jsonify(status="success", current_broker=current, proxy=proxy, proxy_has_password=has_pass)


@mt_settings_bp.route("/api/broker-credentials", methods=["POST"])
@require_user_session
def api_broker_credentials_save():
    """Save/update the user's single broker credential (JSON body)."""
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404
    username = session.get("user")
    data = request.get_json(silent=True) or {}
    broker = (data.get("broker") or "").strip().lower()
    api_key = (data.get("api_key") or "").strip()
    api_secret = (data.get("api_secret") or "").strip()
    proxy_host = (data.get("proxy_host") or "").strip()
    proxy_port = (data.get("proxy_port") or "").strip()
    proxy_url = _build_proxy_url(
        data.get("proxy_scheme", "http"),
        proxy_host,
        proxy_port,
        data.get("proxy_user", ""),
        data.get("proxy_pass", ""),
    )

    if broker not in BROKER_DISPLAY:
        return jsonify(status="error", message="Invalid broker"), 400
    if not api_key or not api_secret:
        return jsonify(status="error", message="API key and secret are required"), 400
    if proxy_host and proxy_port and not proxy_port.isdigit():
        return jsonify(status="error", message="Proxy port must be a number"), 400

    # One broker per user: allow updating the existing one, reject a second.
    existing = list_user_brokers(username)
    if existing and broker not in existing:
        return jsonify(
            status="error",
            message="Only one broker per account. Remove the current broker to switch.",
        ), 400

    if not save_broker_credentials(username, broker, api_key, api_secret, proxy_url=proxy_url):
        return jsonify(status="error", message="Failed to save credentials"), 500
    logger.info("User %s saved broker credentials for %s (react)", username, broker)
    return jsonify(status="success", message=f"Saved credentials for {BROKER_DISPLAY[broker]}")


@mt_settings_bp.route("/api/broker-credentials/<broker>", methods=["DELETE"])
@require_user_session
def api_broker_credentials_delete(broker):
    """Remove the user's credentials for a broker (JSON)."""
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404
    username = session.get("user")
    delete_broker_credentials(username, broker.strip().lower())
    logger.info("User %s removed broker credentials for %s (react)", username, broker)
    return jsonify(status="success", message="Removed")
