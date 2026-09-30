"""Local wizard HTTP server: one page, a small JSON API, and the two OAuth
callback routes. Single-threaded http.server — this is a one-student,
one-browser-tab tool, not a public service.
"""
import datetime
import json
import mimetypes
import os
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import oauth, platforms, store, verify

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets")

VERIFY_FUNCS = {
    "meta": verify.verify_meta,
    "tiktok": verify.verify_tiktok,
    "youtube": verify.verify_youtube,
}

# Credential expiry the wizard can state up front (None = unknown/no expiry).
EXPIRY_DAYS = {
    "meta": {"threads_token": 60},
    "youtube": {"refresh_token": 7},  # only while the Cloud project is in Testing mode
}


def find_port(preferred, must_match_preferred=False):
    """Return a free TCP port on 127.0.0.1, preferring `preferred`.

    TikTok's redirect URI is fixed in the console (http://localhost:8765/callback),
    so for that flow the port cannot float — must_match_preferred=True makes this
    raise instead of silently picking a different port.
    """
    def is_free(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    if is_free(preferred):
        return preferred
    if must_match_preferred:
        raise RuntimeError(
            f"Port {preferred} sedang digunakan. TikTok perlukan redirect URI tetap "
            f"(http://localhost:{preferred}/callback per guide). Tutup program yang guna "
            f"port {preferred} dan cuba lagi."
        )
    for port in range(preferred + 1, preferred + 50):
        if is_free(port):
            return port
    raise RuntimeError("Tak jumpa port kosong.")


class WizardState:
    def __init__(self, platform, port, no_browser):
        self.platform = platform
        self.port = port
        self.no_browser = no_browser
        self.lock = threading.Lock()
        self.oauth_state = None
        self.pending_keys = {}  # client_key/client_secret or client_id/client_secret, held in memory only
        self.oauth_tokens = {}  # access_token/refresh_token, held in memory only
        self.finished = threading.Event()
        self.cancelled = threading.Event()
        self.timed_out = threading.Event()
        self.final_summary = None


def _redirect_uri(state):
    cfg = platforms.get(state.platform)
    oauth_cfg = cfg.get("oauth")
    host = "localhost" if state.platform == "tiktok" else "127.0.0.1"
    return f"http://{host}:{state.port}{oauth_cfg['callback_path']}"


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep stdout clean for the final JSON summary line

        # -- helpers -----------------------------------------------------
        def _send_json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html, code=200):
            body = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_redirect(self, location):
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        def _read_json_body(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except ValueError:
                return {}

        def _serve_static(self, rel_path):
            safe = os.path.normpath(rel_path).lstrip(os.sep)
            full = os.path.join(ASSETS_DIR, safe)
            if not full.startswith(ASSETS_DIR) or not os.path.isfile(full):
                self.send_error(404)
                return
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            with open(full, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # -- request guard -------------------------------------------------
        def _allowed_hosts(self):
            return {f"127.0.0.1:{state.port}", f"localhost:{state.port}"}

        def _guard(self, write=False):
            """Reject requests not addressed to this wizard (DNS rebinding) and
            state-changing requests sent by other websites (CSRF)."""
            if self.headers.get("Host", "") not in self._allowed_hosts():
                self.send_error(403)
                return False
            if write:
                origin = self.headers.get("Origin")
                if origin is not None and origin.replace("http://", "", 1) not in self._allowed_hosts():
                    self.send_error(403)
                    return False
                if self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
                    self.send_error(403)
                    return False
            return True

        # -- routing -------------------------------------------------------
        def do_GET(self):
            if not self._guard(write=self.path.startswith("/api/")):
                return
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = dict(urllib.parse.parse_qsl(parsed.query))

            if path == "/":
                self._render_index()
            elif path.startswith("/assets/"):
                self._serve_static(path[len("/assets/"):])
            elif path == "/tiktok/authorize" and state.platform == "tiktok":
                self._start_oauth(query)
            elif path == "/youtube/authorize" and state.platform == "youtube":
                self._start_oauth(query)
            elif path == "/callback" and state.platform == "tiktok":
                self._handle_callback(query)
            elif path == "/oauth/callback" and state.platform == "youtube":
                self._handle_callback(query)
            elif path == "/api/cancel":
                state.cancelled.set()
                self._send_json({"ok": True})
            else:
                self.send_error(404)

        def do_POST(self):
            if not self._guard(write=True):
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self.send_error(415)
                return
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            payload = self._read_json_body()

            if path == "/api/keys":
                with state.lock:
                    state.pending_keys.update(payload.get("fields", {}))
                self._send_json({"ok": True})
            elif path == "/api/verify":
                fields = self._current_fields(payload.get("fields", {}))
                checks = VERIFY_FUNCS[state.platform](fields)
                self._send_json({"checks": checks, "all_ok": bool(checks) and all(c["ok"] for c in checks)})
            elif path == "/api/save":
                self._handle_save(payload.get("fields", {}))
            else:
                self.send_error(404)

        # -- actions ---------------------------------------------------
        def _current_fields(self, submitted):
            fields = dict(submitted)
            with state.lock:
                for k, v in state.pending_keys.items():
                    fields.setdefault(k, v)
                for k, v in state.oauth_tokens.items():
                    fields.setdefault(k, v)
            return fields

        def _render_index(self):
            cfg = platforms.get(state.platform)
            redirect_uri = _redirect_uri(state) if cfg.get("oauth") else None
            steps = []
            for step in cfg["steps"]:
                body = step["body"]
                if redirect_uri and "{redirect_uri}" in body:
                    body = body.format(redirect_uri=redirect_uri)
                steps.append({**step, "body": body})

            with state.lock:
                oauth_done_flag = bool(state.oauth_tokens)

            wizard_config = {
                "platform": state.platform,
                "title": cfg["title"],
                "subtitle": cfg["subtitle"],
                "fields": cfg["fields"],
                "steps": steps,
                "oauth": cfg.get("oauth"),
                "redirect_uri": redirect_uri,
                "oauth_done": oauth_done_flag,
            }

            template_path = os.path.join(ASSETS_DIR, "wizard.html")
            with open(template_path, "r", encoding="utf-8") as fh:
                html = fh.read()
            config_json = json.dumps(wizard_config).replace("</script", "<\\/script")
            html = html.replace("__WIZARD_CONFIG__", config_json)
            self._send_html(html)

        def _start_oauth(self, query):
            cfg = platforms.get(state.platform)
            oauth_cfg = cfg["oauth"]
            redirect_uri = _redirect_uri(state)
            new_state_value = oauth.new_state()
            with state.lock:
                state.oauth_state = new_state_value
                key_field = "client_key" if state.platform == "tiktok" else "client_id"
                client_id_value = state.pending_keys.get(key_field, "")

            if not client_id_value:
                self._send_redirect("/?error=missing_keys")
                return

            if state.platform == "tiktok":
                url = oauth.tiktok_authorize_url(client_id_value, redirect_uri, oauth_cfg["scopes"], new_state_value)
            else:
                url = oauth.google_authorize_url(client_id_value, redirect_uri, oauth_cfg["scopes"], new_state_value)
            self._send_redirect(url)

        def _handle_callback(self, query):
            code = query.get("code")
            returned_state = query.get("state")
            with state.lock:
                expected_state = state.oauth_state
                client_key = state.pending_keys.get("client_key") or state.pending_keys.get("client_id")
                client_secret = state.pending_keys.get("client_secret")

            if not code or not returned_state or returned_state != expected_state:
                self._send_redirect(f"/?{state.platform}=error")
                return

            redirect_uri = _redirect_uri(state)
            if state.platform == "tiktok":
                ok, body, err = verify.tiktok_exchange_code(client_key, client_secret, code, redirect_uri)
            else:
                ok, body, err = verify.youtube_exchange_code(client_key, client_secret, code, redirect_uri)

            if ok and isinstance(body, dict) and body.get("access_token"):
                with state.lock:
                    if state.platform == "tiktok":
                        state.oauth_tokens["access_token"] = body.get("access_token", "")
                        if body.get("refresh_token"):
                            state.oauth_tokens["refresh_token"] = body["refresh_token"]
                    else:
                        if body.get("refresh_token"):
                            state.oauth_tokens["refresh_token"] = body["refresh_token"]
                self._send_redirect(f"/?{state.platform}=done")
            else:
                self._send_redirect(f"/?{state.platform}=error")

        def _handle_save(self, submitted_fields):
            fields = self._current_fields(submitted_fields)
            checks = VERIFY_FUNCS[state.platform](fields)
            all_ok = bool(checks) and all(c["ok"] for c in checks)
            if not all_ok:
                self._send_json({"saved": False, "checks": checks, "all_ok": False})
                return

            existing = store.read_credentials()
            to_save = dict(fields)
            expiry = None
            expiry_map = EXPIRY_DAYS.get(state.platform, {})
            for field_key, days in expiry_map.items():
                if to_save.get(field_key):
                    expiry = store.expiry_date_from_now(days)
                    to_save[f"{field_key}_expires_at"] = expiry
            to_save["verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            merged = store.merge_platform_credentials(existing, state.platform, to_save)
            store.write_credentials(merged)

            renew_hint = None
            if state.platform == "youtube":
                renew_hint = "Jalankan wizard semula sebelum tamat untuk dapatkan token baharu."
            elif state.platform == "meta":
                renew_hint = "Generate token Threads baharu di langkah 6 sebelum tamat."

            summary = store.build_summary(state.platform, checks, expiry=expiry, renew_hint=renew_hint)
            with state.lock:
                state.final_summary = summary
            state.finished.set()
            self._send_json({"saved": True, "checks": checks, "all_ok": True, "summary": summary})

    return Handler


def run_server(state):
    handler_cls = make_handler(state)
    httpd = HTTPServer(("127.0.0.1" if state.platform != "tiktok" else "localhost", state.port), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread
