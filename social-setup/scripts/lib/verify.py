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
