"""Build the two OAuth authorize URLs the wizard redirects the browser to.

Token exchange itself lives in verify.py (tiktok_exchange_code /
youtube_exchange_code) next to the other network calls.
"""
import secrets
import urllib.parse

TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def new_state():
    return secrets.token_urlsafe(16)


def tiktok_authorize_url(client_key, redirect_uri, scope, state):
    params = {
        "client_key": client_key,
        "scope": scope,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{TIKTOK_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def google_authorize_url(client_id, redirect_uri, scope, state):
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
