"""
Shared httpx client module with connection pooling support for all broker APIs
with automatic protocol negotiation (HTTP/2 when available, HTTP/1.1 fallback)
"""

import threading
from typing import Optional

import httpx

from utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)

# Connection-pooled httpx clients, keyed by outbound proxy URL. The key None is
# the default (no proxy) client used by single-tenant deployments and by any
# broker call made outside a per-user request context.
#
# Multi-tenant: each user may configure their own HTTP/HTTPS egress proxy so
# their broker traffic exits from their own registered static IP (SEBI static-IP
# mandate). httpx binds the proxy at CLIENT construction (not per request), so we
# keep one pooled client per distinct proxy URL rather than creating a client per
# call — creating a client per call would leak file descriptors under the
# long-running single-worker eventlet/gunicorn process.
_httpx_clients: dict[Optional[str], httpx.Client] = {}
_clients_lock = threading.Lock()


def _resolve_proxy() -> Optional[str]:
    """Return the outbound proxy URL for the current request, or None.

    Reads HTTP_PROXY from the per-request broker credential context (set by the
    auth before_request hook in multi-tenant mode). Falls back to None so
    single-tenant behavior is unchanged.
    """
    try:
        from utils.broker_context import get_context_value

        # Strictly context-only (no os.getenv fallback) so a host-level HTTP_PROXY
        # never silently reroutes single-tenant broker traffic.
        return get_context_value("HTTP_PROXY")
    except Exception:
        return None


def get_httpx_client() -> httpx.Client:
    """
    Returns a connection-pooled HTTP client with automatic protocol negotiation
    (HTTP/2 when available, HTTP/1.1 fallback).

    In multi-tenant mode the client is selected by the current user's configured
    outbound proxy (from the request context), so each user's broker calls egress
    from their own static IP. With no proxy configured, the shared default client
    is returned — identical to the previous single-client behavior.

    Returns:
        httpx.Client: A configured, pooled HTTP client for the active proxy.
    """
    proxy = _resolve_proxy()

    client = _httpx_clients.get(proxy)
    if client is not None and not client.is_closed:
        return client

    with _clients_lock:
        # Re-check inside the lock (another thread may have created it).
        client = _httpx_clients.get(proxy)
        if client is None or client.is_closed:
            client = _create_http_client(proxy=proxy)
            _httpx_clients[proxy] = client
            logger.info(
                "Created pooled HTTP client (proxy=%s, HTTP/2 preferred, HTTP/1.1 fallback)",
                proxy or "none",
            )
        return client


def request(method: str, url: str, **kwargs) -> httpx.Response:
    """
    Make an HTTP request using the shared client with automatic protocol negotiation.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: URL to request
        **kwargs: Additional arguments to pass to the request

    Returns:
        httpx.Response: The HTTP response

    Raises:
        httpx.HTTPError: If the request fails
    """
    import time

    from flask import g

    client = get_httpx_client()

    # Track actual broker API call time for latency monitoring
    broker_api_start = time.time()
    response = client.request(method, url, **kwargs)
    broker_api_end = time.time()

    # Store broker API time in Flask's g object for latency tracking
    if hasattr(g, "latency_tracker"):
        broker_api_time_ms = (broker_api_end - broker_api_start) * 1000
        g.broker_api_time = broker_api_time_ms
        logger.debug(f"Broker API call took {broker_api_time_ms:.2f}ms")

    # Log the actual HTTP version used (info level for visibility)
    if response.http_version:
        logger.info(f"Request used {response.http_version} - URL: {url[:50]}...")

    return response


# Shortcut methods for common HTTP methods
def get(url: str, **kwargs) -> httpx.Response:
    """
    Send a GET request.

    Args:
        url (str): The URL to send the GET request to.
        **kwargs: Additional arguments passed to the underlying request method.

    Returns:
        httpx.Response: The HTTP response from the server.
    """
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> httpx.Response:
    """
    Send a POST request.

    Args:
        url (str): The URL to send the POST request to.
        **kwargs: Additional arguments passed to the underlying request method.

    Returns:
        httpx.Response: The HTTP response from the server.
    """
    return request("POST", url, **kwargs)


def put(url: str, **kwargs) -> httpx.Response:
    """
    Send a PUT request.

    Args:
        url (str): The URL to send the PUT request to.
        **kwargs: Additional arguments passed to the underlying request method.

    Returns:
        httpx.Response: The HTTP response from the server.
    """
    return request("PUT", url, **kwargs)


def delete(url: str, **kwargs) -> httpx.Response:
    """
    Send a DELETE request.

    Args:
        url (str): The URL to send the DELETE request to.
        **kwargs: Additional arguments passed to the underlying request method.

    Returns:
        httpx.Response: The HTTP response from the server.
    """
    return request("DELETE", url, **kwargs)


def _create_http_client(proxy: Optional[str] = None) -> httpx.Client:
    """
    Create a new HTTP client with automatic protocol negotiation and latency tracking.
    Enables both HTTP/2 and HTTP/1.1, letting httpx choose the best protocol.

    Args:
        proxy: Optional HTTP/HTTPS proxy URL to route all traffic through, so the
            request egresses from a specific static IP. None means direct.

    Returns:
        httpx.Client: A configured HTTP client with protocol auto-negotiation and timing hooks
    """
    import os
    import time

    from flask import g

    # Event hooks for tracking broker API timing
    def log_request(request):
        """Hook called before request is sent"""
        request.extensions["start_time"] = time.time()
        logger.debug(f"Starting request to {request.url}")

    def log_response(response):
        """Hook called after response is received"""
        try:
            start_time = response.request.extensions.get("start_time")
            if start_time:
                duration_ms = (time.time() - start_time) * 1000

                # Store broker API time in Flask's g object for latency tracking
                try:
                    from flask import has_request_context

                    if has_request_context() and hasattr(g, "latency_tracker"):
                        g.broker_api_time = duration_ms
                        logger.debug(f"Broker API call took {duration_ms:.2f}ms")
                except (RuntimeError, AttributeError):
                    # Not in Flask request context or g not available
                    pass

                logger.debug(f"Request completed in {duration_ms:.2f}ms")
        except Exception as e:
            logger.exception(f"Error in response hook: {e}")

    try:
        # Detect if running in standalone mode (Docker/production) vs integrated mode (local dev)
        # In standalone mode, disable HTTP/2 to avoid protocol negotiation issues
        app_mode = os.environ.get("APP_MODE", "integrated").strip().strip("'\"")
        is_standalone = app_mode == "standalone"

        # Disable HTTP/2 in standalone/Docker environments to avoid protocol negotiation issues
        http2_enabled = not is_standalone

        client = httpx.Client(
            http2=http2_enabled,  # Disable HTTP/2 in standalone mode, enable in integrated mode
            http1=True,  # Always enable HTTP/1.1 for compatibility
            proxy=proxy,  # None = direct; else route egress through the user's proxy
            timeout=120.0,  # Increased timeout for large historical data requests
            limits=httpx.Limits(
                max_keepalive_connections=40,  # Increased from 20 for multi-strategy environments
                max_connections=100,  # Increased from 50 for 10+ concurrent strategies
                keepalive_expiry=30.0,  # Reduced from 120s to recycle stale connections faster
            ),
            # Add verify parameter to handle SSL/TLS issues in standalone mode
            verify=True,  # Can be set to False for debugging SSL issues (not recommended for production)
            # Add event hooks for latency tracking
            event_hooks={"request": [log_request], "response": [log_response]},
        )

        if proxy:
            logger.info("HTTP client configured with outbound proxy")
        if is_standalone:
            logger.info("Running in standalone mode - HTTP/2 disabled for compatibility")
        else:
            logger.info("Running in integrated mode - HTTP/2 enabled for optimal performance")

        return client

    except Exception as e:
        logger.exception(f"Failed to create HTTP client: {e}")
        raise


def cleanup_httpx_client() -> None:
    """
    Closes all pooled httpx clients (one per proxy) and releases their resources.

    Should be called when the application is shutting down to prevent
    resource leaks.

    Returns:
        None
    """
    with _clients_lock:
        for key, client in list(_httpx_clients.items()):
            try:
                client.close()
            except Exception:
                logger.exception("Error closing HTTP client (proxy=%s)", key or "none")
        count = len(_httpx_clients)
        _httpx_clients.clear()
        if count:
            logger.info("Closed %d pooled HTTP client(s)", count)
