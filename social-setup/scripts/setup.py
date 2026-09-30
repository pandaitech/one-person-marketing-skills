#!/usr/bin/env python3
"""Local wizard that connects a student's own Meta / TikTok / YouTube developer
app. Standard library only -- no pip installs, runs on macOS and Windows.

Usage:
    python3 scripts/setup.py meta
    python3 scripts/setup.py tiktok
    python3 scripts/setup.py youtube
    python3 scripts/setup.py check
    py scripts/setup.py meta            (Windows)

Secrets are typed into the local wizard page in the student's browser and are
never printed to stdout or sent anywhere but the platform's own API. Only a
single redacted JSON summary line is printed at the end.
"""
import argparse
import json
import os
import sys
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import server, store, verify  # noqa: E402

DEFAULT_PORT = 8765
DEFAULT_TIMEOUT_MIN = 30

VERIFY_FUNCS = {
    "meta": verify.verify_meta,
    "tiktok": verify.verify_tiktok,
    "youtube": verify.verify_youtube,
}


def run_wizard(platform, port, no_browser, timeout_min):
    preferred = port or DEFAULT_PORT
    try:
        actual_port = server.find_port(preferred, must_match_preferred=(platform == "tiktok"))
    except RuntimeError as exc:
        print(json.dumps({"platform": platform, "status": "error", "error": str(exc)}))
        return 1

    state = server.WizardState(platform, actual_port, no_browser)
    httpd, thread = server.run_server(state)
    url = f"http://{'localhost' if platform == 'tiktok' else '127.0.0.1'}:{actual_port}/"

    if not no_browser:
        webbrowser.open(url)

    deadline = time.time() + timeout_min * 60
    try:
        while time.time() < deadline:
            if state.finished.wait(timeout=1):
                break
            if state.cancelled.is_set():
                break
        else:
            state.timed_out.set()
    except KeyboardInterrupt:
        state.cancelled.set()
    finally:
        httpd.shutdown()
        thread.join(timeout=5)

    if state.finished.is_set() and state.final_summary:
        print(json.dumps(state.final_summary))
        return 0
    if state.cancelled.is_set():
        print(json.dumps({"platform": platform, "status": "cancelled"}))
        return 1
    print(json.dumps({"platform": platform, "status": "timeout",
                       "hint": f"Tiada tindakan dalam {timeout_min} minit. Jalankan semula bila sedia."}))
    return 1


def run_check():
    saved = store.read_credentials()
    present = [p for p in store.PLATFORMS if saved.get(p)]
    if not present:
        print(json.dumps(store.none_saved_summary()))
        return 0
    for platform in present:
        checks = VERIFY_FUNCS[platform](saved[platform])
        expiry = None
        for key, value in saved[platform].items():
            if key.endswith("_expires_at") and value:
                expiry = value
        summary = store.build_summary(platform, checks, expiry=expiry)
        print(json.dumps(summary))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="setup.py",
        description="Wizard tempatan untuk sambung akaun Meta, TikTok atau YouTube.",
    )
    parser.add_argument("platform", choices=["meta", "tiktok", "youtube", "check"],
                         help="Platform untuk disambung, atau 'check' untuk sahkan semua yang tersimpan.")
    parser.add_argument("--no-browser", action="store_true",
                         help="Jangan buka browser secara automatik (untuk ujian).")
    parser.add_argument("--port", type=int, default=None,
                         help=f"Port tempatan (default {DEFAULT_PORT}).")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_MIN,
                         help=f"Had masa minit sebelum wizard tamat automatik (default {DEFAULT_TIMEOUT_MIN}).")
    args = parser.parse_args(argv)

    if args.platform == "check":
        return run_check()
    return run_wizard(args.platform, args.port, args.no_browser, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
