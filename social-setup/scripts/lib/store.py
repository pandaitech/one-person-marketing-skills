"""Pure-ish credential store helpers: path resolution, merge, redaction, expiry math.

No network calls live here. The only I/O is reading/writing the credentials JSON
file, isolated in read_credentials()/write_credentials() so the rest of this
module (and the tests) can work with plain dicts.
"""
import json
import os
import stat
import tempfile
from datetime import datetime, timedelta, timezone

APP_DIR_PARTS = (".pandaitech", "social")
CREDENTIALS_FILENAME = "credentials.json"

PLATFORMS = ("meta",)


def credentials_dir():
    """Directory that holds credentials.json. Respects $HOME (and %USERPROFILE%
    via os.path.expanduser) so tests can point it at a temp dir."""
    return os.path.join(os.path.expanduser("~"), *APP_DIR_PARTS)


def credentials_path():
    return os.path.join(credentials_dir(), CREDENTIALS_FILENAME)


def read_credentials():
    """Return the saved credentials dict, or {} if the file doesn't exist yet."""
    path = credentials_path()
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except ValueError:
            return {}
    return data if isinstance(data, dict) else {}


def write_credentials(data):
    """Write the full credentials dict atomically, creating the directory if
    needed and restricting permissions to the owner (600 on macOS/Linux)."""
    directory = credentials_dir()
    os.makedirs(directory, mode=0o700, exist_ok=True)
    path = credentials_path()
    fd, tmp_path = tempfile.mkstemp(prefix=".credentials-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600; no-op-ish on Windows
    except OSError:
        pass
    return path


def merge_platform_credentials(existing, platform, new_fields):
    """Return a NEW full credentials dict with new_fields merged into
    existing[platform], leaving every other platform (and any field of this
    platform not present in new_fields) untouched."""
    merged = json.loads(json.dumps(existing)) if existing else {}
    platform_data = dict(merged.get(platform, {}))
    platform_data.update(new_fields)
    merged[platform] = platform_data
    return merged


def expiry_date_from_now(days):
    """ISO date (YYYY-MM-DD, UTC) `days` days from now."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


def days_until(iso_date_str):
    """Whole days from now (UTC) until iso_date_str (YYYY-MM-DD). Negative if past."""
    target = datetime.strptime(iso_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    delta = target - datetime.now(timezone.utc)
    return delta.days


def is_expired(iso_date_str):
    return days_until(iso_date_str) < 0


def build_summary(platform, checks, expiry=None, renew_hint=None):
    """Build the one-line, secret-free summary dict printed to stdout.

    checks: list of {"name": str, "ok": bool, "hint": str|None}
    expiry: optional ISO date string (YYYY-MM-DD) for the shortest-lived credential
    """
    all_ok = bool(checks) and all(c["ok"] for c in checks)
    summary = {
        "platform": platform,
        "status": "ok" if all_ok else "error",
        "verified": [
            {"name": c["name"], "ok": bool(c["ok"])} for c in checks
        ],
    }
    failed_hints = [c.get("hint") for c in checks if not c["ok"] and c.get("hint")]
    if failed_hints:
        summary["hints"] = failed_hints
    if expiry:
        summary["expires"] = expiry
        summary["expires_in_days"] = days_until(expiry)
    if renew_hint:
        summary["renew"] = renew_hint
    return summary


def none_saved_summary():
    return {"status": "none_saved", "platforms": []}
