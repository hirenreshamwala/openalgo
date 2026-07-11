import json
import os

import httpx

from broker.indmoney.api.baseurl import BASE_URL, get_url
from utils.broker_context import get_broker_credential
from utils.httpx_client import get_httpx_client


def authenticate_broker(code):
    try:
        BROKER_API_KEY = get_broker_credential("BROKER_API_KEY")
        BROKER_API_SECRET = get_broker_credential("BROKER_API_SECRET")
        REDIRECT_URL = get_broker_credential("REDIRECT_URL")

        # For IndMoney, the access token is directly provided in BROKER_API_SECRET
        # No OAuth flow needed - just return the access token
        if BROKER_API_SECRET:
            return BROKER_API_SECRET, None
        else:
            return None, "No access token found in BROKER_API_SECRET environment variable"

    except Exception as e:
        return None, f"An exception occurred: {str(e)}"
