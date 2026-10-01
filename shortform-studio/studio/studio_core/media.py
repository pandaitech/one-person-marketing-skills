"""ffprobe/ffmpeg helpers: probing, posters/thumbs, filmstrips, waveforms.

Everything expensive is cached under DATA_DIR/cache/<kind>/<id>/<n>/ and
invalidated when the source file's (mtime, size) changes. A per-target
threading.Lock guards generation so concurrent requests for the same cached
item don't spawn ffmpeg twice.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading

from . import paths, store

WAVE_COLOR = "0xC9D43A"  # waveform accent colour in the review UI

_locks_guard = threading.Lock()
_locks = {}


def _lock_for(key):
    with _locks_guard:
        lk = _locks.get(key)
        if lk is None:
            lk = threading.Lock()
            _locks[key] = lk
        return lk


class MediaError(Exception):
    pass


def _run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise MediaError((proc.stderr or b"").decode("utf-8", "replace")[-2000:])
    return proc.stdout


def probe(path):
    """Return {duration, width, height, size} for a media file."""
    size = None
    try:
        size = os.path.getsize(path)
    except OSError:
        pass
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    try:
        out = _run(cmd)
        data = json.loads(out.decode("utf-8", "replace"))
    except Exception:
        return {"duration": None, "width": None, "height": None, "size": size}
    duration = None
    fmt = data.get("format", {})
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None
    width = height = None
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            width = s.get("width")
            height = s.get("height")
            if duration is None and s.get("duration"):
                try:
                    duration = float(s["duration"])
                except (TypeError, ValueError):
                    pass
            break
    return {"duration": duration, "width": width, "height": height, "size": size}


def _source_stamp(source_path):
    try:
        st = os.stat(source_path)
    except OSError:
        return None
    return "%d:%d" % (int(st.st_mtime), st.st_size)


def _cache_dir(kind, ident, n):
    return os.path.join(paths.cache_dir(), kind, str(ident), str(n))


def get_cached(kind, ident, n, source_path, filename, generator):
    """Return the path to a cached artifact, (re)generating it if the source
    file changed or it doesn't exist yet. `generator(source_path, target)`
    must create `target`."""
    d = _cache_dir(kind, ident, n)
    target = os.path.join(d, filename)
    stamp_path = target + ".stamp"
    lock = _lock_for(target)
    with lock:
        cur = _source_stamp(source_path)
        old = None
        if os.path.exists(stamp_path):
            try:
                with open(stamp_path, "r") as f:
                    old = f.read().strip()
            except OSError:
                old = None
        if os.path.exists(target) and cur is not None and old == cur:
            return target
        store.ensure_dir(d)
        generator(source_path, target)
        if cur is not None:
            with open(stamp_path, "w") as f:
                f.write(cur)
        return target


def poster_generator(t=None, width=360):
    def gen(source_path, target):
        seek = t
        if seek is None:
            info = probe(source_path)
            dur = info.get("duration") or 0
            seek = max(dur * 0.15, 0)
        cmd = [
            "ffmpeg", "-y", "-ss", "%.3f" % seek, "-i", source_path,
            "-frames:v", "1", "-vf", "scale=%d:-2" % width,
            "-q:v", "3", target,
        ]
        _run(cmd)
    return gen


def poster(kind, ident, n, source_path, t=None, width=360):
    fname = "poster.jpg" if t is None else ("t-%d.jpg" % int(round(t * 1000)))
    return get_cached(kind, ident, n, source_path, fname, poster_generator(t=t, width=width))


def _filmstrip_geometry(source_path):
    info = probe(source_path)
    w, h = info.get("width"), info.get("height")
    if not w or not h:
        return 72, 128
    tile_h = 128
    tile_w = int(round(tile_h * (w / float(h))))
    return tile_w, tile_h


def filmstrip_generator(tiles=60):
    def gen(source_path, target):
        info = probe(source_path)
        dur = info.get("duration") or 1.0
        tile_w, tile_h = _filmstrip_geometry(source_path)
        fps = tiles / float(dur) if dur > 0 else 1.0
        vf = "fps=%f,scale=%d:%d,tile=%dx1" % (fps, tile_w, tile_h, tiles)
        cmd = ["ffmpeg", "-y", "-i", source_path, "-frames:v", "1", "-vf", vf,
               "-q:v", "4", target]
        _run(cmd)
    return gen


def filmstrip(kind, ident, n, source_path, tiles=60):
    return get_cached(kind, ident, n, source_path, "filmstrip.jpg", filmstrip_generator(tiles))


def waveform_generator(width, height):
    def gen(source_path, target):
        filt = ("[0:a]aformat=channel_layouts=mono,showwavespic=s=%dx%d:colors=%s[wave];"
                "[wave]format=rgba,colorkey=0x000000:0.02:0.1[out]") % (width, height, WAVE_COLOR)
        cmd = ["ffmpeg", "-y", "-i", source_path, "-filter_complex", filt,
               "-map", "[out]", "-frames:v", "1", target]
        _run(cmd)
    return gen


def waveform(kind, ident, n, source_path, width=1600, height=96):
    return get_cached(kind, ident, n, source_path, "waveform.png",
                       waveform_generator(width, height))
