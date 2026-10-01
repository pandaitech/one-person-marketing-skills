"""v2 render job manager: renders a clip's current recipe through
studio_core.house_render (run via `uv run`), polls its progress file into
clip.render, and registers the resulting version on success. Also a small
content-addressed cache of draft stills for the edit view.

One running render per clip, tracked in-process by a module-level set + lock
(mirrored into the persisted clip.render field so the UI can poll it too).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import uuid

from . import media, paths, store


class RenderError(Exception):
    pass


_lock = threading.Lock()
_running = set()  # clip_ids with a render currently in flight


# ---------------------------------------------------------------------------
# command builders (monkeypatched by tests to point at a fake renderer)
# ---------------------------------------------------------------------------

def _resolve_uv():
    """PATH first; then the usual install locations (a server started from a
    GUI/launchd has a thin PATH)."""
    found = shutil.which("uv")
    if found:
        return found
    for d in ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin"):
        cand = os.path.join(os.path.expanduser(d), "uv")
        if os.access(cand, os.X_OK):
            return cand
    return None


def render_command(spec_path, out_path, progress_path):
    uv_exe = _resolve_uv()
    if not uv_exe:
        raise RenderError("uv not found on PATH (checked ~/.local/bin, /opt/homebrew/bin, /usr/local/bin)")
    return [uv_exe, "run", "--with", "pillow", "--with", "numpy", "python", "-m",
            "studio_core.house_render", "render", spec_path, out_path, "--progress", progress_path]


def still_command(spec_path, t_out, out_jpg, width):
    uv_exe = _resolve_uv()
    if not uv_exe:
        raise RenderError("uv not found on PATH (checked ~/.local/bin, /opt/homebrew/bin, /usr/local/bin)")
    return [uv_exe, "run", "--with", "pillow", "--with", "numpy", "python", "-m",
            "studio_core.house_render", "still", spec_path, str(t_out), out_jpg, "--width", str(int(width))]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _default_workdir(clip_id):
    return os.path.join(paths.renders_root(), clip_id)


def _next_render_version(clip):
    versions = clip.get("versions", [])
    return max((v.get("n", 0) for v in versions), default=0) + 1


def _render_out_path(workdir, clip_id, n):
    renders_dir = os.path.join(workdir, "renders")
    store.ensure_dir(renders_dir)
    cand = os.path.join(renders_dir, "%s-v%d.mp4" % (clip_id, n))
    if not os.path.exists(cand):
        return cand
    # never overwrite an existing render file -- bump with a suffix
    i = 2
    while True:
        alt = os.path.join(renders_dir, "%s-v%d-%d.mp4" % (clip_id, n, i))
        if not os.path.exists(alt):
            return alt
        i += 1


def _spec_tmp_dir():
    d = os.path.join(paths.cache_dir(), "render-tmp")
    store.ensure_dir(d)
    return d


def _write_temp_spec(clip_id, tag, spec):
    path = os.path.join(_spec_tmp_dir(), "%s-%s-%s.json" % (clip_id, tag, uuid.uuid4().hex[:8]))
    store.write_json_atomic(path, spec)
    return path


def _progress_path(clip_id, n):
    d = os.path.join(paths.cache_dir(), "render-progress")
    store.ensure_dir(d)
    return os.path.join(d, "%s-v%s.json" % (clip_id, n))


def _log_path(clip_id):
    store.ensure_dir(paths.logs_dir())
    ts = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    return os.path.join(paths.logs_dir(), "render-%s-%s.log" % (clip_id, ts))


def _log_tail(log_path, n=20):
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:]).strip()
    except OSError:
        return ""


def _poll_progress(clip_id, progress_path):
    data = store.read_json(progress_path, None)
    if not data:
        return None
    frame, total = data.get("frame"), data.get("total")
    pct = None
    if frame is not None and total:
        try:
            pct = round(100.0 * float(frame) / float(total), 1)
        except (TypeError, ZeroDivisionError):
            pct = None
    store.set_clip_render(clip_id, {"progress": pct})
    return pct


def _prepare(clip_id):
    clip = store.get_clip(clip_id)
    if clip is None:
        raise RenderError("unknown clip %s" % clip_id)
    spec = store.get_recipe(clip_id)
    if spec is None:
        raise RenderError("no recipe for clip %s" % clip_id)
    n = _next_render_version(clip)
    workdir = clip.get("workdir") or _default_workdir(clip_id)
    out_path = _render_out_path(workdir, clip_id, n)
    spec_path = _write_temp_spec(clip_id, "v%d" % n, spec)
    progress_path = _progress_path(clip_id, n)
    cmd = render_command(spec_path, out_path, progress_path)
    return clip, spec, n, out_path, progress_path, cmd


def _finish_success(clip_id, n, out_path, note, addresses):
    recipe = store.get_recipe(clip_id)
    prev_snapshot = store.latest_snapshot(clip_id)
    if prev_snapshot is None:
        changes = ["First render"]
    else:
        try:
            from studio_core import house_plan
            changes = house_plan.diff(prev_snapshot, recipe) or ["Minor changes"]
        except Exception:
            changes = ["Minor changes"]
    bullets = "\n".join("- %s" % c for c in changes)
    notes = ("%s\n\n%s" % (note, bullets)) if note else bullets
    info = media.probe(out_path)
    clip, version = store.add_clip_version(
        clip_id, out_path, notes=notes, addresses=addresses or [], kind="render", probe=info)
    store.snapshot_recipe(clip_id, recipe, version["n"])
    store.set_clip_render(clip_id, {"state": "done", "progress": 100, "message": "",
                                     "version": version["n"], "ended": store.now_iso()})
    store.append_event("editor", "render_done", "Rendered %s" % version["label"], clip=clip_id)
    return version


def _finish_error(clip_id, log_path):
    tail = _log_tail(log_path, 20)
    store.set_clip_render(clip_id, {"state": "error", "message": tail or "render failed",
                                     "ended": store.now_iso()})
    store.append_event("system", "render_error", tail or "render failed", clip=clip_id)


def _watch(clip_id, proc, n, out_path, progress_path, log_path, note, addresses):
    try:
        while proc.poll() is None:
            _poll_progress(clip_id, progress_path)
            time.sleep(0.5)
        _poll_progress(clip_id, progress_path)
        ok = proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0
        if ok:
            _finish_success(clip_id, n, out_path, note, addresses)
        else:
            _finish_error(clip_id, log_path)
    finally:
        with _lock:
            _running.discard(clip_id)


# ---------------------------------------------------------------------------
# public: render
# ---------------------------------------------------------------------------

def start_render(clip_id, note=None, addresses=None):
    """Start (or refuse if one is already running) a background render for
    clip_id. Returns the clip.render state right after launch."""
    with _lock:
        if clip_id in _running:
            raise RenderError("a render is already running for clip %s" % clip_id)
        _running.add(clip_id)
    try:
        clip, spec, n, out_path, progress_path, cmd = _prepare(clip_id)
    except Exception:
        with _lock:
            _running.discard(clip_id)
        raise
    log_path = _log_path(clip_id)
    store.set_clip_render(clip_id, {"state": "running", "progress": 0, "message": "",
                                     "version": n, "started": store.now_iso(), "ended": None})
    try:
        with open(log_path, "ab", buffering=0) as log_f:
            proc = subprocess.Popen(cmd, cwd=paths.studio_dir(), stdout=log_f, stderr=log_f,
                                     stdin=subprocess.DEVNULL)
    except Exception:
        with _lock:
            _running.discard(clip_id)
        store.set_clip_render(clip_id, {"state": "error", "message": "failed to start render process",
                                         "ended": store.now_iso()})
        raise
    t = threading.Thread(target=_watch, args=(clip_id, proc, n, out_path, progress_path, log_path, note, addresses),
                          daemon=True)
    t.start()
    return store.clip_render_state(store.get_clip(clip_id))


def run_render_sync(clip_id, note=None, addresses=None, print_progress=True):
    """Foreground render for the CLI: blocks until done, optionally printing
    progress, then registers the version (or raises RenderError)."""
    with _lock:
        if clip_id in _running:
            raise RenderError("a render is already running for clip %s" % clip_id)
        _running.add(clip_id)
    try:
        clip, spec, n, out_path, progress_path, cmd = _prepare(clip_id)
        log_path = _log_path(clip_id)
        store.set_clip_render(clip_id, {"state": "running", "progress": 0, "message": "",
                                         "version": n, "started": store.now_iso(), "ended": None})
        with open(log_path, "ab", buffering=0) as log_f:
            proc = subprocess.Popen(cmd, cwd=paths.studio_dir(), stdout=log_f, stderr=log_f,
                                     stdin=subprocess.DEVNULL)
        last_pct = None
        while proc.poll() is None:
            pct = _poll_progress(clip_id, progress_path)
            if print_progress and pct is not None and pct != last_pct:
                print("rendering %s v%d: %.1f%%" % (clip_id, n, pct))
                last_pct = pct
            time.sleep(0.2)
        _poll_progress(clip_id, progress_path)
        ok = proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0
        if not ok:
            _finish_error(clip_id, log_path)
            raise RenderError("render failed for %s (see %s)" % (clip_id, log_path))
        version = _finish_success(clip_id, n, out_path, note, addresses)
        if print_progress:
            print("rendered %s -> %s" % (version["label"], out_path))
        return version
    finally:
        with _lock:
            _running.discard(clip_id)


# ---------------------------------------------------------------------------
# public: draft stills (content-addressed cache)
# ---------------------------------------------------------------------------

_still_locks_guard = threading.Lock()
_still_locks = {}


def _still_lock_for(key):
    with _still_locks_guard:
        lk = _still_locks.get(key)
        if lk is None:
            lk = threading.Lock()
            _still_locks[key] = lk
        return lk


def _prune_stills(cache_dir, keep=200):
    try:
        files = [os.path.join(cache_dir, f) for f in os.listdir(cache_dir) if f.endswith(".jpg")]
    except FileNotFoundError:
        return
    if len(files) <= keep:
        return
    files.sort(key=lambda p: os.path.getmtime(p))
    for f in files[:len(files) - keep]:
        try:
            os.remove(f)
        except OSError:
            pass


def still_jpg(clip_id, t, width=540):
    """A draft still of the clip's *current* recipe at output time t, cached
    by (recipe hash, t rounded to 0.05s, width). Regenerated only on a cache
    miss; per-key lock so concurrent requests don't spawn the renderer twice."""
    clip = store.get_clip(clip_id)
    if clip is None:
        raise RenderError("unknown clip %s" % clip_id)
    spec = store.get_recipe(clip_id)
    if spec is None:
        raise RenderError("no recipe for clip %s" % clip_id)
    key_t = round(round(float(t) / 0.05) * 0.05, 2)
    spec_hash = hashlib.sha1(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    cache_dir = os.path.join(paths.cache_dir(), "stills", clip_id)
    store.ensure_dir(cache_dir)
    fname = "%s-%s-%d.jpg" % (spec_hash, ("%.2f" % key_t), int(width))
    target = os.path.join(cache_dir, fname)
    lock = _still_lock_for(target)
    with lock:
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            return target
        spec_path = _write_temp_spec(clip_id, "still", spec)
        cmd = still_command(spec_path, key_t, target, width)
        try:
            proc = subprocess.run(cmd, cwd=paths.studio_dir(), stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=20)
        except subprocess.TimeoutExpired:
            raise RenderError("still render timed out for clip %s" % clip_id)
        if proc.returncode != 0 or not os.path.isfile(target) or os.path.getsize(target) == 0:
            msg = (proc.stderr or b"").decode("utf-8", "replace")[-2000:] or "still render failed"
            raise RenderError(msg)
        _prune_stills(cache_dir, keep=200)
        return target
