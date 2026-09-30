"""Read-only credential verification calls, one cheap request per check.

Standard library only (urllib). Every function returns a list of
{"name": str, "ok": bool, "hint": str|None} dicts, in Malay, matching the
"green/red per item with a plain-Malay fix hint" requirement. Nothing here
ever prints a secret; hints only reference field names, not values.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 10
USER_AGENT = "pandaitech-social-setup/1.0"

GRAPH = "https://graph.facebook.com/v20.0"
THREADS_GRAPH = "https://graph.threads.net/v1.0"
TIKTOK_API = "https://open.tiktokapis.com/v2"
YT_API = "https://www.googleapis.com/youtube/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return True, json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = None
        return False, body, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, None, f"Tak dapat sambung ({exc.reason})"
    except Exception as exc:  # noqa: BLE001 - surface as a plain hint, never crash the wizard
        return False, None, str(exc)


def _post_form(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return True, json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        try:
            body_json = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body_json = None
        return False, body_json, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, None, f"Tak dapat sambung ({exc.reason})"


def _graph_error_hint(body, fallback):
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return f"{fallback}: {err['message']}"
    return fallback


# ---------------------------------------------------------------- Meta -----

def verify_meta(fields):
    checks = []
    token = (fields.get("fb_ig_token") or "").strip()
    page_id = (fields.get("page_id") or "").strip()
    ig_id = (fields.get("ig_business_id") or "").strip()
    threads_token = (fields.get("threads_token") or "").strip()

    if not token:
        checks.append({"name": "Token Facebook + Instagram", "ok": False,
                        "hint": "Token FB+IG belum diisi."})
    else:
        ok, body, err = _get(f"{GRAPH}/me?access_token={urllib.parse.quote(token)}")
        checks.append({
            "name": "Token Facebook + Instagram sah",
            "ok": ok,
            "hint": None if ok else _graph_error_hint(body, "Token tak sah atau dah luput. Generate token baharu di System users (langkah 9 dalam guide)."),
        })
        if ok and page_id:
            ok2, body2, _ = _get(f"{GRAPH}/{urllib.parse.quote(page_id)}?fields=name&access_token={urllib.parse.quote(token)}")
            checks.append({
                "name": "Page ID boleh diakses",
                "ok": ok2,
                "hint": None if ok2 else _graph_error_hint(body2, "Page ID salah, atau token tak ada akses ke Page ini. Semak Assign assets (langkah 8)."),
            })
        elif not page_id:
            checks.append({"name": "Page ID diisi", "ok": False, "hint": "Page ID belum diisi. Dapatkan dari Graph API Explorer (langkah 10)."})

        if ok and ig_id:
            ok3, body3, _ = _get(f"{GRAPH}/{urllib.parse.quote(ig_id)}?fields=username&access_token={urllib.parse.quote(token)}")
            checks.append({
                "name": "Instagram Business ID boleh diakses",
                "ok": ok3,
                "hint": None if ok3 else _graph_error_hint(body3, "Instagram ID salah, atau IG belum disambung ke Page. Semak langkah 6 dan 10."),
            })
        elif not ig_id:
            checks.append({"name": "Instagram Business ID diisi", "ok": False, "hint": "Instagram Business ID belum diisi. Dapatkan dari Graph API Explorer (langkah 10)."})

    if not threads_token:
        checks.append({"name": "Token Threads", "ok": False, "hint": "Token Threads belum diisi."})
    else:
        ok4, body4, err4 = _get(f"{THREADS_GRAPH}/me?fields=id,username&access_token={urllib.parse.quote(threads_token)}")
        checks.append({
            "name": "Token Threads sah",
            "ok": ok4,
            "hint": None if ok4 else _graph_error_hint(body4, "Token Threads tak sah atau dah luput (60 hari). Generate semula di langkah 13."),
        })

    return checks


# -------------------------------------------------------------- TikTok -----

def tiktok_exchange_code(client_key, client_secret, code, redirect_uri):
    return _post_form(f"{TIKTOK_API}/oauth/token/", {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })


def tiktok_refresh_token(client_key, client_secret, refresh_token):
    return _post_form(f"{TIKTOK_API}/oauth/token/", {
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })


def verify_tiktok(fields):
    checks = []
    client_key = (fields.get("client_key") or "").strip()
    client_secret = (fields.get("client_secret") or "").strip()
    access_token = (fields.get("access_token") or "").strip()
    refresh_token = (fields.get("refresh_token") or "").strip()

    if not client_key or not client_secret:
        checks.append({"name": "Client Key & Client Secret", "ok": False,
                        "hint": "Client Key atau Client Secret belum diisi."})
        return checks
    checks.append({"name": "Client Key & Client Secret diisi", "ok": True, "hint": None})

    if not access_token and refresh_token:
        ok, body, err = tiktok_refresh_token(client_key, client_secret, refresh_token)
        if ok and isinstance(body, dict) and body.get("access_token"):
            access_token = body["access_token"]

    if not access_token:
        checks.append({"name": "Log masuk TikTok", "ok": False,
                        "hint": "Belum log masuk TikTok. Klik butang 'Log masuk TikTok' dalam wizard."})
        return checks

    ok, body, err = _get(
        f"{TIKTOK_API}/user/info/?fields=open_id,display_name",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    # TikTok's user info endpoint can return HTTP 200 with an error code in the
    # body (e.g. access_token_invalid), so the HTTP status alone isn't enough.
    body_error_code = None
    if ok and isinstance(body, dict):
        body_error_code = (body.get("error") or {}).get("code")
    ok_info = ok and (body_error_code in (None, "ok"))
    hint = None if ok_info else "Token TikTok tak sah atau dah luput. Klik 'Log masuk TikTok' semula."
    checks.append({"name": "Token TikTok sah (user info)", "ok": bool(ok_info), "hint": hint})
    return checks


# ------------------------------------------------------------- YouTube -----

def youtube_exchange_code(client_id, client_secret, code, redirect_uri):
    return _post_form(GOOGLE_TOKEN_URL, {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })


def youtube_refresh_access_token(client_id, client_secret, refresh_token):
    return _post_form(GOOGLE_TOKEN_URL, {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })


def verify_youtube(fields):
    checks = []
    client_id = (fields.get("client_id") or "").strip()
    client_secret = (fields.get("client_secret") or "").strip()
    refresh_token = (fields.get("refresh_token") or "").strip()

    if not client_id or not client_secret:
        checks.append({"name": "Client ID & Client Secret", "ok": False,
                        "hint": "Client ID atau Client Secret belum diisi."})
        return checks
    checks.append({"name": "Client ID & Client Secret diisi", "ok": True, "hint": None})

    if not refresh_token:
        checks.append({"name": "Log masuk Google", "ok": False,
                        "hint": "Belum log masuk Google. Klik butang 'Log masuk Google' dalam wizard."})
        return checks

    ok, body, err = youtube_refresh_access_token(client_id, client_secret, refresh_token)
    if not ok or not isinstance(body, dict) or not body.get("access_token"):
        checks.append({
            "name": "Refresh token sah",
            "ok": False,
            "hint": "Refresh token tak sah atau dah luput. Kalau projek masih dalam mod Testing, token luput dalam 7 hari — jalankan wizard semula.",
        })
        return checks
    checks.append({"name": "Refresh token sah", "ok": True, "hint": None})

    access_token = body["access_token"]
    ok2, body2, err2 = _get(
        f"{YT_API}/channels?part=snippet&mine=true",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    has_channel = ok2 and isinstance(body2, dict) and body2.get("items")
    checks.append({
        "name": "Channel YouTube dijumpai",
        "ok": bool(has_channel),
        "hint": None if has_channel else "Tak jumpa channel untuk akaun ni. Pastikan anda log masuk dengan akaun pemilik channel.",
    })
    return checks
