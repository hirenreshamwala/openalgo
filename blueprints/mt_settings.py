# blueprints/mt_settings.py
"""Multi-tenant per-user settings: broker credential management.

Only active when MULTI_TENANT=true. Each user stores their own broker
API key/secret (encrypted) in UserBrokerCredentials, keyed by (username, broker).
The instance-wide .env broker config is not used in multi-tenant mode.
"""

import os

from flask import Blueprint, jsonify, redirect, request, session, url_for

from database.broker_creds_db import (
    delete_broker_credentials,
    get_broker_credentials,
    list_user_brokers,
    save_broker_credentials,
)
from utils.logging import get_logger
from utils.session import require_user_session

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
    """Per-user broker credential management page (multi-tenant only)."""
    if not _mt_enabled():
        return "Not available", 404

    username = session.get("user")
    configured = set(list_user_brokers(username))

    # Options for the add/edit dropdown — all 34 supported brokers.
    options = "".join(
        f"<option value='{bid}'>{name}</option>" for bid, name in SUPPORTED_BROKERS
    )

    # Table of already-configured brokers.
    if configured:
        saved_rows = ""
        for bid in sorted(configured):
            name = BROKER_DISPLAY.get(bid, bid)
            saved_rows += (
                f"<tr><td>{name}</td><td><code>{bid}</code></td>"
                f"<td><form method='post' action='/mt/broker-credentials/{bid}/delete' style='display:inline' "
                f"onsubmit='return confirm(\"Remove {name} credentials?\")'>"
                "<button class='btn-del' type='submit'>Remove</button></form></td></tr>"
            )
        saved_table = (
            "<table><thead><tr><th>Broker</th><th>ID</th><th>Action</th></tr></thead>"
            f"<tbody>{saved_rows}</tbody></table>"
        )
    else:
        saved_table = "<p class='muted'>No brokers configured yet. Add one below.</p>"

    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Broker Credentials — OpenAlgo</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>*{{box-sizing:border-box}}body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:32px;max-width:760px}}
h1{{color:#f8fafc;font-size:1.4rem;margin-bottom:4px}}h2{{color:#cbd5e1;font-size:1rem;margin-top:32px}}
.muted{{color:#64748b;font-size:14px}}nav a{{color:#38bdf8;text-decoration:none;margin-right:16px;font-size:14px}}nav{{margin-bottom:20px}}
table{{border-collapse:collapse;width:100%;background:#1e293b;border-radius:8px;overflow:hidden;margin-top:8px}}
th{{background:#334155;padding:9px 14px;text-align:left;font-size:12px;color:#94a3b8;text-transform:uppercase}}
td{{padding:9px 14px;font-size:14px;border-top:1px solid #0f172a}}code{{color:#7dd3fc}}
form.add{{background:#1e293b;padding:20px;border-radius:8px;margin-top:8px}}
label{{display:block;font-size:13px;color:#94a3b8;margin:12px 0 4px}}
input,select{{width:100%;padding:9px 12px;border-radius:6px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;font-size:14px}}
button{{border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600;margin-top:16px}}
.btn-save{{background:#2563eb;color:#fff}}.btn-del{{background:#7f1d1d;color:#fecaca;padding:5px 12px;margin:0;font-size:13px}}
</style></head><body>
<nav><a href='/broker'>&#8592; Broker Login</a><a href='/mt/broker-credentials'>&#8635; Refresh</a></nav>
<h1>Broker Credentials</h1>
<p class='muted'>Signed in as <strong>{username}</strong>. Add the API key &amp; secret for each broker you want to trade with. Stored encrypted, per user.</p>

<h2>Configured brokers</h2>
{saved_table}

<h2>Add / update a broker</h2>
<form class='add' method='post' action='/mt/broker-credentials'>
  <label for='broker'>Broker</label>
  <select id='broker' name='broker' required>{options}</select>
  <label for='api_key'>API Key</label>
  <input id='api_key' name='api_key' type='text' autocomplete='off' required placeholder='Your broker API key'>
  <label for='api_secret'>API Secret</label>
  <input id='api_secret' name='api_secret' type='password' autocomplete='off' required placeholder='Your broker API secret'>
  <button class='btn-save' type='submit'>Save credentials</button>
</form>
<p class='muted' style='margin-top:16px'>After saving, go to <a href='/broker' style='color:#38bdf8'>Broker Login</a> to connect.</p>
</body></html>"""
    return html


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

    if broker not in BROKER_DISPLAY:
        return "Invalid broker", 400
    if not api_key or not api_secret:
        return "API key and secret are required", 400

    if not save_broker_credentials(username, broker, api_key, api_secret):
        return "Failed to save credentials", 500
    logger.info("User %s saved broker credentials for %s", username, broker)
    return redirect(url_for("mt_settings_bp.broker_credentials_page"))


@mt_settings_bp.route("/broker-credentials/<broker>/delete", methods=["POST"])
@require_user_session
def delete_broker_credentials_route(broker):
    """Remove the signed-in user's credentials for a broker."""
    if not _mt_enabled():
        return jsonify(status="error", message="Not available"), 404

    username = session.get("user")
    delete_broker_credentials(username, broker.strip().lower())
    logger.info("User %s removed broker credentials for %s", username, broker)
    return redirect(url_for("mt_settings_bp.broker_credentials_page"))


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
