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
    """Per-user broker credential management page (multi-tenant only)."""
    if not _mt_enabled():
        return "Not available", 404

    username = session.get("user")
    configured = set(list_user_brokers(username))

    # CSRF token — the app runs Flask-WTF CSRFProtect globally, so every POST
    # form must carry this hidden field or the submit is rejected with 400.
    csrf_token = generate_csrf()

    # Feedback banner from the post/redirect/get flow.
    flash_html = ""
    if request.args.get("saved"):
        b = BROKER_DISPLAY.get(request.args["saved"], request.args["saved"])
        flash_html = f"<div class='flash ok'>Saved credentials for {b}.</div>"
    elif request.args.get("removed"):
        b = BROKER_DISPLAY.get(request.args["removed"], request.args["removed"])
        flash_html = f"<div class='flash ok'>Removed {b}.</div>"
    elif request.args.get("error"):
        flash_html = f"<div class='flash err'>{request.args['error']}</div>"

    # One broker per user: if a broker is already configured, the add/update
    # form is locked to that broker (only its keys/proxy can be updated). To
    # switch brokers the user must remove the current one first. When nothing
    # is configured yet, all 34 brokers are offered.
    current_broker = next(iter(configured), None)
    if current_broker:
        options = f"<option value='{current_broker}'>{BROKER_DISPLAY.get(current_broker, current_broker)}</option>"
        add_heading = "Update your broker"
        switch_note = (
            f"<p class='muted'>You have <strong>{BROKER_DISPLAY.get(current_broker, current_broker)}</strong> "
            "configured. Update its API key / secret / proxy below. To use a different broker, remove it "
            "first &mdash; only one broker per account.</p>"
        )
    else:
        options = "".join(
            f"<option value='{bid}'>{name}</option>" for bid, name in SUPPORTED_BROKERS
        )
        add_heading = "Add your broker"
        switch_note = ""

    # Table of already-configured brokers.
    if configured:
        saved_rows = ""
        for bid in sorted(configured):
            name = BROKER_DISPLAY.get(bid, bid)
            creds = get_broker_credentials(username, bid) or {}
            proxy = creds.get("proxy_url")
            if proxy:
                pp = _parse_proxy_url(proxy)
                loc = f"{pp['host']}:{pp['port']}" if pp["port"] else pp["host"]
                auth_note = " <span class='muted'>(auth)</span>" if pp["user"] else ""
                proxy_cell = f"<code>{pp['scheme']}://{loc}</code>{auth_note}"
            else:
                proxy_cell = "<span class='muted'>direct</span>"
            saved_rows += (
                f"<tr><td>{name}</td><td><code>{bid}</code></td><td>{proxy_cell}</td>"
                f"<td><form method='post' action='/mt/broker-credentials/{bid}/delete' style='display:inline' "
                f"onsubmit='return confirm(\"Remove {name} credentials?\")'>"
                f"<input type='hidden' name='csrf_token' value='{csrf_token}'>"
                "<button class='btn-del' type='submit'>Remove</button></form></td></tr>"
            )
        saved_table = (
            "<table><thead><tr><th>Broker</th><th>ID</th><th>Egress proxy</th><th>Action</th></tr></thead>"
            f"<tbody>{saved_rows}</tbody></table>"
        )
    else:
        saved_table = "<p class='muted'>No brokers configured yet. Add one below.</p>"

    # Server's public egress IP — what the broker sees on a direct (no-proxy)
    # connection. Users whitelisting the shared server IP add this.
    server_ip = _get_server_public_ip()
    if server_ip:
        ip_banner = (
            "<div class='ipbox'><div>"
            "<span class='muted'>This server's public IP (for direct connections)</span><br>"
            f"<span class='ip'>{server_ip}</span></div>"
            f"<button type='button' class='btn-copy' onclick=\"navigator.clipboard.writeText('{server_ip}')\">Copy</button>"
            "</div>"
            "<p class='muted'>Add this IP to your broker's API/static-IP whitelist if you are "
            "<strong>not</strong> using an egress proxy below. If you use a proxy, whitelist the "
            "proxy's IP instead.</p>"
        )
    else:
        ip_banner = (
            "<div class='ipbox'><span class='muted'>Could not determine the server's public IP "
            "(no outbound internet?). Check your server's static IP manually.</span></div>"
        )

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
.ipbox{{display:flex;align-items:center;justify-content:space-between;gap:16px;background:#0b2545;border:1px solid #1d4ed8;border-radius:8px;padding:14px 18px;margin-top:16px}}
.ipbox .ip{{font-family:ui-monospace,monospace;font-size:1.3rem;font-weight:700;color:#7dd3fc;letter-spacing:.02em}}
.btn-copy{{background:#1d4ed8;color:#fff;padding:6px 14px;margin:0;font-size:13px}}
.flash{{padding:11px 16px;border-radius:8px;margin-top:16px;font-size:14px;font-weight:500}}
.flash.ok{{background:#052e1b;border:1px solid #16a34a;color:#86efac}}
.flash.err{{background:#3f1212;border:1px solid #dc2626;color:#fca5a5}}
</style></head><body>
<nav><a href='/broker'>&#8592; Broker Login</a><a href='/mt/broker-credentials'>&#8635; Refresh</a></nav>
<h1>Broker Credentials</h1>
<p class='muted'>Signed in as <strong>{username}</strong>. Add the API key &amp; secret for your broker. One broker per account, stored encrypted.</p>
{flash_html}
{ip_banner}
<h2>Configured brokers</h2>
{saved_table}

<h2>{add_heading}</h2>
{switch_note}
<form class='add' method='post' action='/mt/broker-credentials'>
  <input type='hidden' name='csrf_token' value='{csrf_token}'>
  <label for='broker'>Broker</label>
  <select id='broker' name='broker' required>{options}</select>
  <label for='api_key'>API Key</label>
  <input id='api_key' name='api_key' type='text' autocomplete='off' required placeholder='Your broker API key'>
  <label for='api_secret'>API Secret</label>
  <input id='api_secret' name='api_secret' type='password' autocomplete='off' required placeholder='Your broker API secret'>
  <fieldset style='border:1px solid #334155;border-radius:8px;padding:12px 16px;margin-top:16px'>
    <legend class='muted' style='padding:0 6px'>Egress Proxy (optional)</legend>
    <p class='muted' style='margin-top:0'>If your broker whitelists a specific static IP, enter a proxy that egresses from that IP. Leave Host blank for a direct connection.</p>
    <div style='display:flex;gap:12px;flex-wrap:wrap'>
      <div style='flex:0 0 110px'>
        <label for='proxy_scheme'>Scheme</label>
        <select id='proxy_scheme' name='proxy_scheme'>
          <option value='http'>http</option>
          <option value='https'>https</option>
        </select>
      </div>
      <div style='flex:1 1 240px'>
        <label for='proxy_host'>Host / IP</label>
        <input id='proxy_host' name='proxy_host' type='text' autocomplete='off' placeholder='e.g. 203.0.113.10 or proxy.example.com'>
      </div>
      <div style='flex:0 0 110px'>
        <label for='proxy_port'>Port</label>
        <input id='proxy_port' name='proxy_port' type='text' autocomplete='off' placeholder='8080'>
      </div>
    </div>
    <div style='display:flex;gap:12px;flex-wrap:wrap'>
      <div style='flex:1 1 240px'>
        <label for='proxy_user'>Username <span class='muted'>(optional)</span></label>
        <input id='proxy_user' name='proxy_user' type='text' autocomplete='off' placeholder='proxy username'>
      </div>
      <div style='flex:1 1 240px'>
        <label for='proxy_pass'>Password <span class='muted'>(optional)</span></label>
        <input id='proxy_pass' name='proxy_pass' type='password' autocomplete='off' placeholder='proxy password'>
      </div>
    </div>
  </fieldset>
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
