"""House-style recipe planning — Python 3.9 stdlib only (the server imports this
module directly, so no third-party dependency may leak in here; house_render.py
is the numpy/Pillow half that actually draws pixels).

A "recipe" (see docs/STUDIO-V2.md, "The recipe") describes a clip entirely in
SOURCE seconds (positions in the class recording). This module resolves a
recipe into the "plan" (OUTPUT seconds — what the viewer sees) that the web UI
and the CLI use for lanes, summaries and "what changed" without ever having to
re-implement the cut/caption/SFX timing rules themselves.

Function reference (all documented in STUDIO-V2.md § Python modules):
    validate(spec) -> list[str]
    plan(spec) -> dict
    seg_map(spec) -> [(a, b, o), ...]                 (snapped a/b, output offset o)
    src_to_out(spec, src) -> float | None
    out_to_src(spec, out) -> float
    snap_segments(spec) -> [{"a","b","snap","mute","snapped":[a,b]}, ...]
    auto_captions(spec, words) -> [{"text","a","b"}, ...]
    sfx_events(spec, plan) -> [{"key","name","t","gain","muted","source"}, ...]
    diff(old, new) -> list[str]
    rough_cut_spec(clip_id, source_file, words_path, ranges, title) -> spec
"""
from __future__ import annotations

import array
import json
import os
import re
import subprocess

from . import paths

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

DEFAULT_SPEAKER_TILE = [962, 272, 318, 178]
DEFAULT_TAIL = 0.6
DEFAULT_OUTPUT = {"width": 1080, "height": 1920, "fps": 24}
DEFAULT_VOICE_LUFS = -17
DEFAULT_TRUE_PEAK = -1.5

TITLE_LEAD = 0.8  # title reveal starts this many seconds before output 0 (TITLE_AT in the V02 renderer)

# auto_captions: break the current phrase before one of these words once it has
# picked up >= 3 words already (mirrors how the hand-written V02/V01 PHRASES
# happen to break: "tapi sama je...", "so sebenarnya...", "and then...").
CAPTION_BREAK_WORDS = {
    "tapi", "so", "kalau", "sebab", "and", "memang", "lepas", "baru",
    "experience", "problem",
}
CAPTION_PAUSE = 0.45
CAPTION_MAX_WORDS = 5
CAPTION_MAX_CHARS = 34
CAPTION_ASR_EARLY = 0.8  # ASR word starts run up to ~0.5s early; absorb with margin

SNAP_SR = 16000
SNAP_WINDOW = 0.35      # ffmpeg decode window on either side of the boundary
SNAP_MAX_MOVE = 0.30    # only move the boundary within this range
SNAP_RMS_THRESHOLD = 120.0  # int16 scale; "quiet" if the 20ms window RMS is below this

FRAME_STYLES = ("photo", "cutout", "book")
MOMENT_KINDS = ("fullscreen", "manuscript", "zoom", "screen")
SCREEN_CAM_POSITIONS = ("bottom-right", "bottom-left", "top-right", "top-left", "none")
# Output seconds: consecutive screen moments this close (or overlapping/touching)
# hand over directly - the renderer cross-fades the panel instead of dropping
# back to the speaker card between them (see house_render.py's screen_chains),
# so their inner whoosh-out/whoosh-in pair is auto-muted below.
SCREEN_ADJACENT_GAP = 0.5


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def validate(spec) -> list:
    """Structural + semantic checks. Returns a list of human error strings
    (empty = valid). Never raises on malformed input - always returns strings."""
    errors = []

    def err(msg):
        errors.append(msg)

    if not isinstance(spec, dict):
        return ["spec must be an object"]

    if not spec.get("clip"):
        err("clip: missing id")

    source = spec.get("source")
    if not isinstance(source, dict):
        err("source: missing")
    else:
        if not source.get("file"):
            err("source.file: missing")
        if not source.get("words"):
            err("source.words: missing")
        tile = source.get("speaker_tile", DEFAULT_SPEAKER_TILE)
        if not (isinstance(tile, (list, tuple)) and len(tile) == 4):
            err("source.speaker_tile: must be [x, y, w, h]")

    cut = spec.get("cut")
    if not isinstance(cut, dict):
        err("cut: missing")
    else:
        segments = cut.get("segments")
        if not isinstance(segments, list) or not segments:
            err("cut.segments: must be a non-empty list")
        else:
            prev_b = None
            for i, seg in enumerate(segments):
                if not isinstance(seg, dict):
                    err("cut.segments[%d]: must be an object" % i)
                    continue
                a, b = seg.get("a"), seg.get("b")
                if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                    err("cut.segments[%d]: a/b must be numbers" % i)
                    continue
                if b <= a:
                    err("cut.segments[%d]: b (%.3f) must be after a (%.3f)" % (i, b, a))
                if prev_b is not None and a < prev_b - 1e-6:
                    err("cut.segments[%d]: overlaps the previous segment" % i)
                prev_b = b
        tail = cut.get("tail", DEFAULT_TAIL)
        if not isinstance(tail, (int, float)) or tail < 0:
            err("cut.tail: must be a non-negative number")

    captions = spec.get("captions", {}) or {}
    mode = captions.get("mode", "auto")
    if mode not in ("auto", "manual"):
        err("captions.mode: must be 'auto' or 'manual'")
    if mode == "manual":
        for i, p in enumerate(captions.get("phrases", []) or []):
            if not isinstance(p, dict) or "text" not in p or "a" not in p or "b" not in p:
                err("captions.phrases[%d]: needs text/a/b" % i)

    title = spec.get("title")
    if title is not None:
        if not isinstance(title, dict) or "lines" not in title or "until" not in title:
            err("title: needs lines[] and until")
        elif not isinstance(title.get("lines"), list) or not title["lines"]:
            err("title.lines: must be a non-empty list")

    for i, hl in enumerate(spec.get("headlines", []) or []):
        if not isinstance(hl, dict) or not hl.get("id"):
            err("headlines[%d]: needs id" % i)
            continue
        if "until" not in hl:
            err("headlines[%s]: needs until" % hl.get("id", i))
        lines = hl.get("lines")
        if not isinstance(lines, list) or not lines:
            err("headlines[%s]: needs a non-empty lines[]" % hl.get("id", i))
        else:
            for j, line in enumerate(lines):
                if not isinstance(line, dict):
                    err("headlines[%s].lines[%d]: must be an object" % (hl.get("id", i), j))
                elif not line.get("dim") and "text" not in line:
                    err("headlines[%s].lines[%d]: needs text (or dim:true)" % (hl.get("id", i), j))
                elif "at" not in line:
                    err("headlines[%s].lines[%d]: needs at" % (hl.get("id", i), j))

    ids_seen = set()
    for i, mom in enumerate(spec.get("moments", []) or []):
        if not isinstance(mom, dict):
            err("moments[%d]: must be an object" % i)
            continue
        mid = mom.get("id") or ("moments[%d]" % i)
        if not mom.get("id"):
            err("moments[%d]: needs id" % i)
        elif mid in ids_seen:
            err("moments: duplicate id %r" % mid)
        ids_seen.add(mid)
        kind = mom.get("kind")
        if kind not in MOMENT_KINDS:
            err("%s: kind must be one of %s" % (mid, ", ".join(MOMENT_KINDS)))
            continue
        if kind == "fullscreen":
            if "until" not in mom:
                err("%s: fullscreen needs until" % mid)
            items = mom.get("items", []) or []
            for j, it in enumerate(items):
                if it.get("frame") is not None and it.get("frame") not in FRAME_STYLES:
                    err("%s.items[%d]: frame must be one of %s" % (mid, j, ", ".join(FRAME_STYLES)))
                if "image" not in it or "at" not in it:
                    err("%s.items[%d]: needs image and at" % (mid, j))
            counter = mom.get("counter")
            if counter is not None:
                for key in ("from", "to", "start", "land"):
                    if key not in counter:
                        err("%s.counter: needs %s" % (mid, key))
        elif kind == "manuscript":
            for key in ("at", "until", "text", "type_at", "type_end"):
                if key not in mom:
                    err("%s: manuscript needs %s" % (mid, key))
        elif kind == "zoom":
            for key in ("at", "until", "zoom"):
                if key not in mom:
                    err("%s: zoom needs %s" % (mid, key))
        elif kind == "screen":
            for key in ("at", "until"):
                if key not in mom:
                    err("%s: screen needs %s" % (mid, key))
            at, until = mom.get("at"), mom.get("until")
            if isinstance(at, (int, float)) and isinstance(until, (int, float)) and until <= at:
                err("%s: until (%.3f) must be after at (%.3f)" % (mid, until, at))
            for field in ("crop", "crop_to"):
                val = mom.get(field)
                if val is None:
                    continue
                ok = isinstance(val, (list, tuple)) and len(val) == 4 and all(isinstance(v, (int, float)) for v in val)
                if ok:
                    x, y, w, h = val
                    ok = x >= 0 and y >= 0 and w > 0 and h > 0
                if not ok:
                    err("%s.%s: must be [x, y, w, h] with non-negative x/y and positive w/h" % (mid, field))
            cam = mom.get("cam", "bottom-right")
            if cam not in SCREEN_CAM_POSITIONS:
                err("%s.cam: must be one of %s" % (mid, ", ".join(SCREEN_CAM_POSITIONS)))

    sound = spec.get("sound", {}) or {}
    if "voice_lufs" in sound and not isinstance(sound["voice_lufs"], (int, float)):
        err("sound.voice_lufs: must be a number")
    if "true_peak" in sound and not isinstance(sound["true_peak"], (int, float)):
        err("sound.true_peak: must be a number")

    output = spec.get("output", {}) or {}
    for key in ("width", "height", "fps"):
        if key in output and (not isinstance(output[key], (int, float)) or output[key] <= 0):
            err("output.%s: must be a positive number" % key)

    return errors


# ---------------------------------------------------------------------------
# snapping (silence-aware boundary nudge)
# ---------------------------------------------------------------------------

def _snap_cache_path():
    return os.path.join(paths.cache_dir(), "snap.json")


def _load_snap_cache():
    try:
        with open(_snap_cache_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_snap_cache(cache):
    path = _snap_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp-%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, path)
    except OSError:
        pass


def _snap_cache_key(file_path, mtime, t, side):
    return "%s|%.6f|%.3f|%s" % (file_path, mtime, t, side)


def _snap_one(file_path, t, side, cache):
    """Move boundary `t` into the quietest 20ms window within ±SNAP_MAX_MOVE s,
    only if that window's RMS is below SNAP_RMS_THRESHOLD. `side` ("start"/"end")
    is only used for cache-keying/debugging - the search itself is symmetric."""
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        mtime = 0.0
    key = _snap_cache_key(file_path, mtime, t, side)
    if key in cache:
        return cache[key]

    result = t
    try:
        lo = max(0.0, t - SNAP_WINDOW)
        dur = 2 * SNAP_WINDOW
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", "%.3f" % lo, "-t", "%.3f" % dur, "-i", str(file_path),
             "-vn", "-ac", "1", "-ar", str(SNAP_SR), "-f", "s16le", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=20,
        ).stdout
        samples = array.array("h")
        samples.frombytes(raw[: (len(raw) // 2) * 2])
        win = max(1, int(SNAP_SR * 0.01))  # 10ms frame
        n = len(samples) // win
        frames = []
        for i in range(n):
            chunk = samples[i * win:(i + 1) * win]
            if not chunk:
                frames.append(0.0)
                continue
            ms = sum(x * x for x in chunk) / len(chunk)
            frames.append(ms ** 0.5)
        best_rms, best_centre = None, None
        for i in range(len(frames) - 1):  # slide a 20ms (2-frame) window
            v = (frames[i] + frames[i + 1]) / 2.0
            centre_t = lo + (i * win + win) / float(SNAP_SR)
            if abs(centre_t - t) > SNAP_MAX_MOVE:
                continue
            if best_rms is None or v < best_rms:
                best_rms, best_centre = v, centre_t
        if best_rms is not None and best_rms < SNAP_RMS_THRESHOLD and best_centre is not None:
            result = best_centre
    except (OSError, subprocess.SubprocessError, ValueError):
        result = t

    cache[key] = result
    return result


def snap_segments(spec) -> list:
    """Resolve spec['cut']['segments'], moving `snap: true` boundaries into
    nearby silence. Returns new dicts (does not mutate spec); each has the
    original 'a'/'b' plus 'snapped': [a2, b2]."""
    cut = spec.get("cut", {}) or {}
    segments = cut.get("segments", []) or []
    source = spec.get("source", {}) or {}
    src_file = source.get("file")

    # `snap` applies to both edges; `snap_a` / `snap_b` override one edge (a split keeps its hand-tuned edge
    # and snaps only the new one).
    def _side(seg, key):
        return bool(seg.get(key, seg.get("snap")))

    any_snap = any(_side(seg, "snap_a") or _side(seg, "snap_b") for seg in segments)
    cache = _load_snap_cache() if (any_snap and src_file and os.path.exists(src_file)) else {}
    before = dict(cache)

    out = []
    for seg in segments:
        a = float(seg.get("a", 0.0))
        b = float(seg.get("b", a))
        snap = bool(seg.get("snap"))
        snap_a, snap_b = _side(seg, "snap_a"), _side(seg, "snap_b")
        sa, sb = a, b
        if (snap_a or snap_b) and src_file and os.path.exists(src_file):
            if snap_a:
                sa = _snap_one(src_file, a, "start", cache)
            if snap_b:
                sb = _snap_one(src_file, b, "end", cache)
            if sb <= sa:  # never let a snap invert or collapse the segment
                sa, sb = a, b
        out.append({
            "a": a, "b": b, "snap": snap, "mute": bool(seg.get("mute")),
            "snapped": [sa, sb],
        })

    if cache != before:
        _save_snap_cache(cache)
    return out


# ---------------------------------------------------------------------------
# time mapping
# ---------------------------------------------------------------------------

def seg_map(spec):
    """[(a, b, o), ...] - snapped source boundaries with cumulative output
    offset o, in cut order. This is the piecewise-linear map used by
    src_to_out/out_to_src and by the renderer's segment trim/concat."""
    out = []
    acc = 0.0
    for seg in snap_segments(spec):
        sa, sb = seg["snapped"]
        out.append((sa, sb, acc))
        acc += max(0.0, sb - sa)
    return out


def _map_time(segs, src, tail=0.0):
    """Return (out_time, clamped). clamped=True means `src` fell inside a
    removed part (or past the end of the tail) and was clamped to the
    nearest kept moment.

    A source time up to `tail` seconds past the last kept segment's end is
    NOT a removed part - it addresses the frozen-picture/silent-audio tail
    (cut.tail) that holds after the last word, so it maps 1:1 into that
    span without a warning. Past the tail, it clamps flat to the true end."""
    if not segs:
        return None, True
    for a, b, o in segs:
        if a - 1e-6 <= src <= b + 1e-6:
            return o + (src - a), False
    a0 = segs[0][0]
    if src < a0:
        return segs[0][2], True
    aN, bN, oN = segs[-1]
    end_o = oN + (bN - aN)
    if src > bN:
        if src <= bN + tail + 1e-6:
            return end_o + (src - bN), False
        return end_o + tail, True
    for a, b, o in segs:
        if src < a:
            return o, True
    return end_o, True


def _tail_of(spec):
    return float((spec.get("cut", {}) or {}).get("tail", DEFAULT_TAIL))


def src_to_out(spec, src):
    """Map a SOURCE second to an OUTPUT second. None if the recipe has no
    segments at all. A time inside a removed part clamps to the nearest kept
    moment (silently - callers that need to warn should use plan()'s
    warnings list, which is built from the same clamping). A time up to
    cut.tail past the last kept segment lands in the frozen tail, 1:1."""
    segs = seg_map(spec)
    if not segs:
        return None
    return _map_time(segs, src, _tail_of(spec))[0]


def out_to_src(spec, out):
    """Map an OUTPUT second back to a SOURCE second (piecewise-linear;
    outside [0, duration] clamps to the first/last kept boundary, with the
    frozen tail mapping 1:1 back onto the seconds just past the last b)."""
    segs = seg_map(spec)
    if not segs:
        return 0.0
    tail = _tail_of(spec)
    for a, b, o in segs:
        length = b - a
        if o - 1e-6 <= out <= o + length + 1e-6:
            return a + (out - o)
    a0, b0, o0 = segs[0]
    aN, bN, oN = segs[-1]
    kept_length = oN + (bN - aN)
    if out > kept_length:
        return min(bN + (out - kept_length), bN + tail)
    if out < o0:
        return a0
    return bN


# ---------------------------------------------------------------------------
# auto captions
# ---------------------------------------------------------------------------

def _word_list(words):
    if isinstance(words, dict):
        words = words.get("word_segments") or words.get("words") or []
    out = []
    for w in words or []:
        if isinstance(w, dict):
            out.append({"word": w.get("word", ""), "start": float(w.get("start", 0)), "end": float(w.get("end", 0))})
        elif isinstance(w, (list, tuple)) and len(w) >= 3:
            out.append({"word": w[0], "start": float(w[1]), "end": float(w[2])})
    out.sort(key=lambda w: w["start"])
    return out


def _assign_words_to_segments(words, kept_segments):
    """kept_segments: [(a, b)] snapped, non-muted, in order. Returns
    [(word, seg_index)] for words that land in a kept segment, in time order.
    A word's midpoint inside [a, b] keeps it; otherwise (ASR runs ~0.5s early)
    a word starting within CAPTION_ASR_EARLY before a segment's start is
    pulled into that segment, unless the previous segment already claims it."""
    assigned = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2.0
        target = None
        for si, (a, b) in enumerate(kept_segments):
            if a <= mid <= b:
                target = si
                break
        if target is None:
            for si, (a, b) in enumerate(kept_segments):
                if a - CAPTION_ASR_EARLY <= w["start"] < a:
                    prev_claims = si > 0 and kept_segments[si - 1][0] <= w["start"] <= kept_segments[si - 1][1]
                    if not prev_claims:
                        target = si
                        break
        if target is not None:
            assigned.append((w, target))
    return assigned


def auto_captions(spec, words) -> list:
    """Group kept words (spec's kept, non-muted segments) into short caption
    phrases. Returns [{"text", "a", "b"}] with a/b in SOURCE seconds (first
    word start, last word end) - plan() maps them to output seconds."""
    words = _word_list(words)
    segs = snap_segments(spec)
    kept = [(seg["snapped"][0], seg["snapped"][1]) for seg in segs if not seg.get("mute")]
    assigned = _assign_words_to_segments(words, kept)

    phrases = []
    cur = []
    for entry in assigned:
        w, si = entry
        if cur:
            prev_w, prev_si = cur[-1]
            gap = w["start"] - prev_w["end"]
            candidate_text = " ".join(x[0]["word"] for x in cur) + " " + w["word"]
            token = re.sub(r"[^\w]", "", w["word"]).lower()
            do_break = (
                gap >= CAPTION_PAUSE
                or si != prev_si
                or len(cur) >= CAPTION_MAX_WORDS
                or (len(cur) >= 3 and token in CAPTION_BREAK_WORDS)
                or len(candidate_text) > CAPTION_MAX_CHARS
            )
            if do_break:
                phrases.append(cur)
                cur = []
        cur.append(entry)
    if cur:
        phrases.append(cur)

    out = []
    for group in phrases:
        text = " ".join(w["word"] for w, _ in group)
        a = group[0][0]["start"]
        b = group[-1][0]["end"]
        out.append({"text": text, "a": a, "b": b})
    return out


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def _load_words(spec):
    path = (spec.get("source", {}) or {}).get("words")
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def ticker_ticks(start_t, land_t, steps_count):
    """Output times at which the counter's displayed value changes, EXCLUDING
    the landing change itself (that gets its own "impact" SFX). Mirrors the
    V02 renderer's ticker_times() ease-out roll, generalised to `steps_count`
    values instead of the hard-coded 15-entry YEARS list. Shared by
    sfx_events() (timing SFX) and house_render.py (drawing the digits)."""
    n = max(1, steps_count - 1)
    return [start_t + (land_t - start_t) * (1 - (1 - i / n) ** (1 / 3)) for i in range(1, n)]


def counter_steps(counter):
    """The full sequence of displayed values for a fullscreen moment's year
    counter, from `counter["steps"]` if given (the exact curated list, e.g.
    for the V02 conversion) or else evenly spaced integers between from/to."""
    steps = counter.get("steps")
    if steps:
        return list(steps)
    try:
        f, t = int(counter["from"]), int(counter["to"])
    except (KeyError, TypeError, ValueError):
        return [str(counter.get("from")), str(counter.get("to"))]
    n = 14
    return [str(round(f + (t - f) * i / n)) for i in range(n + 1)]


def fullscreen_slide_src(mom):
    """SOURCE time a fullscreen moment's speaker card starts sliding out:
    the explicit `slide`, or (if absent) 0.5s before the earliest item/counter
    anchor - mirrors the V02 renderer's SCENES default. Shared by plan(),
    sfx_events() and house_render.py so the three never disagree."""
    if mom.get("slide") is not None:
        return mom["slide"]
    items = mom.get("items", []) or []
    counter = mom.get("counter")
    anchors = [it.get("at") for it in items] + ([counter.get("start")] if counter else [])
    if anchors:
        return min(anchors) - 0.5
    return mom.get("until", 0)


def plan(spec) -> dict:
    warnings = []
    segs = seg_map(spec)
    snapped = snap_segments(spec)
    cut = spec.get("cut", {}) or {}
    tail = float(cut.get("tail", DEFAULT_TAIL))

    def map_t(src, label):
        t, clamped = _map_time(segs, src, tail)
        if clamped:
            warnings.append("%s is anchored inside a removed part; clamped to %.1f s" % (label, t))
        return t

    kept_dur = segs[-1][2] + max(0.0, segs[-1][1] - segs[-1][0]) if segs else 0.0
    duration = kept_dur + tail

    out_segments = []
    for seg, (sa, sb, o) in zip(snapped, segs):
        out_segments.append({
            "a": seg["a"], "b": seg["b"], "o": round(o, 4),
            "mute": seg["mute"], "snapped": [round(sa, 4), round(sb, 4)],
        })

    # captions
    captions_spec = spec.get("captions", {}) or {}
    mode = captions_spec.get("mode", "auto")
    if mode == "manual":
        phrases = captions_spec.get("phrases", []) or []
    else:
        phrases = auto_captions(spec, _load_words(spec))
    # t0/word-end for every phrase first, then apply the house style's caption
    # hold: a phrase stays on screen until the next one starts, or 0.7s past
    # its own last word (whichever is sooner) - exactly `c["e"] = min(nxt,
    # c["we"] + 0.7)` in the V02/V01 renderers.
    raw_captions = []
    for i, p in enumerate(phrases):
        t0 = map_t(p["a"], "caption %d" % i)
        we = map_t(p["b"], "caption %d" % i)
        raw_captions.append((t0, we, p.get("text", "")))
    out_captions = []
    for i, (t0, we, text) in enumerate(raw_captions):
        nxt = raw_captions[i + 1][0] if i + 1 < len(raw_captions) else duration
        t1 = min(nxt, we + 0.7)
        out_captions.append({"i": i, "text": text, "t0": round(t0, 3), "t1": round(t1, 3)})

    # title
    out_title = None
    title_spec = spec.get("title")
    if title_spec:
        t1 = map_t(title_spec["until"], "title")
        out_title = {
            "t0": 0.0, "t1": round(t1, 3),
            "lines": [{"text": l.get("text", ""), "hl": l.get("hl")} for l in title_spec.get("lines", [])],
        }

    # headlines
    out_headlines = []
    for hl in spec.get("headlines", []) or []:
        hid = hl.get("id", "h?")
        lines_out, dims, ats = [], [], []
        real_i = 0
        for line in hl.get("lines", []) or []:
            if line.get("dim"):
                dims.append(round(map_t(line.get("at", 0), "%s dim" % hid), 3))
                continue
            t = map_t(line.get("at", 0), "%s line %d" % (hid, real_i + 1))
            lines_out.append({"i": real_i, "text": line.get("text", ""), "t": round(t, 3), "hl": line.get("hl")})
            ats.append(t)
            real_i += 1
        until_t = map_t(hl.get("until", 0), "%s until" % hid)
        t0 = min(ats) if ats else until_t
        out_headlines.append({"id": hid, "t0": round(t0, 3), "t1": round(until_t, 3), "lines": lines_out, "dims": dims})

    # moments
    out_moments = []
    for mom in spec.get("moments", []) or []:
        mid = mom.get("id", "m?")
        kind = mom.get("kind")
        if kind == "fullscreen":
            items = mom.get("items", []) or []
            counter = mom.get("counter")
            item_ts = [map_t(it.get("at", 0), "%s item" % mid) for it in items]
            head_lines = mom.get("head", {}).get("lines", []) or []
            head_ats = [map_t(l.get("at", 0), "%s head" % mid) for l in head_lines if not l.get("dim")]
            slide_t = map_t(fullscreen_slide_src(mom), "%s slide" % mid)
            until_t = map_t(mom.get("until", 0), "%s until" % mid)
            t0 = min([slide_t] + head_ats + item_ts) if (head_ats or item_ts) else slide_t
            bits = []
            if counter:
                bits.append("Year counter %s→%s" % (counter.get("from"), counter.get("to")))
            if items:
                bits.append("%d image%s" % (len(items), "" if len(items) == 1 else "s"))
            summary = " · ".join(bits) if bits else "Fullscreen"
            out_moments.append({"id": mid, "kind": kind, "t0": round(t0, 3), "t1": round(until_t, 3), "summary": summary})
        elif kind == "manuscript":
            t0 = map_t(mom.get("at", 0), "%s at" % mid)
            t1 = map_t(mom.get("until", 0), "%s until" % mid)
            text = mom.get("text", "")
            summary = "Manuscript · %s" % text if text else "Manuscript"
            out_moments.append({"id": mid, "kind": kind, "t0": round(t0, 3), "t1": round(t1, 3), "summary": summary})
        elif kind == "zoom":
            t0 = map_t(mom.get("at", 0), "%s at" % mid)
            t1 = map_t(mom.get("until", 0), "%s until" % mid)
            summary = "Zoom ×%.2g" % mom.get("zoom", 1.0)
            out_moments.append({"id": mid, "kind": kind, "t0": round(t0, 3), "t1": round(t1, 3), "summary": summary})
        elif kind == "screen":
            t0 = map_t(mom.get("at", 0), "%s at" % mid)
            t1 = map_t(mom.get("until", 0), "%s until" % mid)
            bits = ["Screen share"]
            if mom.get("cam", "bottom-right") != "none":
                bits.append("corner cam")
            crop_to = mom.get("crop_to")
            if crop_to:
                crop = mom.get("crop") or [0, 0, crop_to[2], crop_to[3]]
                area0 = crop[2] * crop[3]
                area1 = crop_to[2] * crop_to[3]
                if area1 < area0 * 0.98:
                    bits.append("push-in")
                elif area1 > area0 * 1.02:
                    bits.append("pull-out")
                else:
                    bits.append("pan")
            summary = " · ".join(bits)
            out_moments.append({"id": mid, "kind": kind, "t0": round(t0, 3), "t1": round(t1, 3), "summary": summary})
        else:
            out_moments.append({"id": mid, "kind": kind, "t0": 0.0, "t1": 0.0, "summary": "Unknown moment"})

    result = {
        "duration": round(duration, 3),
        "segments": out_segments,
        "captions": out_captions,
        "title": out_title,
        "headlines": out_headlines,
        "moments": out_moments,
        "warnings": warnings,
    }
    result["sfx"] = sfx_events(spec, result)
    return result


# ---------------------------------------------------------------------------
# sfx
# ---------------------------------------------------------------------------

def sfx_events(spec, plan_) -> list:
    """Derive the SFX list exactly as the V02/V01 house-style renderers do:
    whoosh on a full-screen card sliding out/in, a pop per item, a soft click
    per highlighted headline word, key-press ticks + one bass impact for a
    year counter, and a whoosh + two typing bursts for a manuscript page.
    `plan_` only needs the resolved 'headlines' (for click timing); moment
    geometry is re-resolved from `spec` here so this function also works when
    called standalone with just a spec + its plan()."""
    sound = spec.get("sound", {}) or {}
    gain_adj = float(sound.get("sfx_gain_db", 0) or 0)
    muted = set(sound.get("muted", []) or [])
    segs = seg_map(spec)
    tail = _tail_of(spec)

    def map_t(src):
        return _map_time(segs, src, tail)[0]

    events = []

    def add(key, name, t, gain, source="auto", force_muted=False):
        events.append({
            "key": key, "name": name, "t": round(t, 3),
            "gain": round(gain + gain_adj, 2), "muted": (key in muted) or force_muted, "source": source,
        })

    if sound.get("auto", True):
        # Screen moments close enough to hand over directly (SCREEN_ADJACENT_GAP)
        # auto-mute their shared inner whoosh-out/whoosh-in pair, since the
        # renderer cross-fades the panel there instead of flashing the speaker
        # card - editors don't need to add those keys to sound.muted by hand.
        # Explicit sound.muted entries (for these keys or any other) still work,
        # via the `key in muted` check in add() above.
        screen_spans = sorted(
            (
                (map_t(m.get("at", 0)), map_t(m.get("until", 0)), m.get("id", "m?"))
                for m in (spec.get("moments", []) or []) if m.get("kind") == "screen"
            ),
            key=lambda x: x[0],
        )
        suppress_out, suppress_in = set(), set()
        for (_, t1a, ida), (t0b, _, idb) in zip(screen_spans, screen_spans[1:]):
            if t0b - t1a <= SCREEN_ADJACENT_GAP:
                suppress_out.add(ida)
                suppress_in.add(idb)

        for hl in plan_.get("headlines", []):
            n = 0
            for line in hl.get("lines", []):
                if line.get("hl"):
                    n += 1
                    add("%s:click:%d" % (hl["id"], n), "click-soft", line["t"] + 0.2, -17)

        for mom in spec.get("moments", []) or []:
            mid = mom.get("id", "m?")
            kind = mom.get("kind")
            if kind == "fullscreen":
                items = mom.get("items", []) or []
                counter = mom.get("counter")
                item_ts = [map_t(it.get("at", 0)) for it in items]
                slide_t = map_t(fullscreen_slide_src(mom))
                out_t = map_t(mom.get("until", 0))
                add("%s:whoosh-in" % mid, "whoosh-short", slide_t, -15)
                add("%s:whoosh-out" % mid, "whoosh-short", out_t - 0.15, -17)
                for i, it_t in enumerate(item_ts, start=1):
                    add("%s:pop:%d" % (mid, i), "pop", it_t, -13)
                n = 0
                for line in mom.get("head", {}).get("lines", []) or []:
                    if line.get("hl") and not line.get("dim"):
                        n += 1
                        add("%s:click:%d" % (mid, n), "click-soft", map_t(line.get("at", 0)) + 0.2, -17)
                if counter:
                    start_t = map_t(counter["start"])
                    land_t = map_t(counter["land"])
                    steps = counter_steps(counter)
                    for i, tt in enumerate(ticker_ticks(start_t, land_t, len(steps)), start=1):
                        add("%s:counter:tick:%d" % (mid, i), "key-press", tt, -24)
                    add("%s:counter:land" % mid, "impact-bass-1", land_t, -17)
            elif kind == "manuscript":
                at_t = map_t(mom.get("at", 0))
                header_at_t = at_t + 0.2  # implicit offset (matches PAGE["header_at"] in the V02 renderer)
                type_at_t = map_t(mom.get("type_at", mom.get("at", 0)))
                add("%s:whoosh" % mid, "whoosh-short", at_t, -19)
                add("%s:typing:header" % mid, "typing", header_at_t, -24)
                add("%s:typing" % mid, "typing", type_at_t, -15)
            elif kind == "screen":
                # Same whoosh in/out as a fullscreen card's slide, so `sound.muted`
                # keys look and behave the same across moment kinds.
                in_t = map_t(mom.get("at", 0))
                out_t = map_t(mom.get("until", 0))
                add("%s:whoosh-in" % mid, "whoosh-short", in_t, -15, force_muted=mid in suppress_in)
                add("%s:whoosh-out" % mid, "whoosh-short", out_t - 0.15, -17, force_muted=mid in suppress_out)
            # kind == "zoom": no SFX in the house style.

    for i, ex in enumerate(sound.get("extra", []) or [], start=1):
        key = "extra:%d" % i
        t = map_t(ex.get("at", 0))
        events.append({
            "key": key, "name": ex.get("name"), "t": round(t, 3),
            "gain": round(float(ex.get("gain", 0) or 0) + gain_adj, 2),
            "muted": key in muted, "source": "extra",
        })

    events.sort(key=lambda e: e["t"])
    return events


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

def _by_id(items):
    return {it.get("id"): it for it in (items or []) if isinstance(it, dict)}


def _interval_minus(xs, ys):
    """Parts of the union of intervals xs not covered by ys (both lists of (a, b))."""
    out = []
    for a, b in sorted(xs):
        pieces = [(a, b)]
        for c, d in ys:
            nxt = []
            for p, q in pieces:
                if d <= p or c >= q:
                    nxt.append((p, q))
                    continue
                if c > p:
                    nxt.append((p, c))
                if d < q:
                    nxt.append((d, q))
            pieces = nxt
        out.extend(pieces)
    return out


def _words_between(words, a, b, limit=8):
    got = []
    for w in words:
        s0, e0 = w.get("start"), w.get("end")
        if s0 is None or e0 is None:
            continue
        mid = (s0 + e0) / 2.0
        if a - 0.05 <= mid <= b + 0.05:
            got.append(w.get("word", ""))
    if not got:
        return ""
    return " ".join(got[:limit]) + (" …" if len(got) > limit else "")


def _mmss(t):
    m = int(t // 60)
    return "%d:%04.1f" % (m, t - 60 * m)


def diff(old, new) -> list:
    """Human bullets describing what changed between two specs, for the
    Render step's "what changed" list and version notes."""
    old = old or {}
    new = new or {}
    bullets = []

    # cut: describe the kept-time difference in words ("removed “ok so kira” (−0.8 s)"), not segment arithmetic
    old_segs = [(float(s.get("a", 0)), float(s.get("b", 0))) for s in (old.get("cut", {}) or {}).get("segments", []) or []]
    new_segs = [(float(s.get("a", 0)), float(s.get("b", 0))) for s in (new.get("cut", {}) or {}).get("segments", []) or []]
    if old_segs != new_segs:
        removed = _interval_minus(old_segs, new_segs)
        added = _interval_minus(new_segs, old_segs)
        data = _load_words(new) or _load_words(old)
        wl = (data.get("word_segments") if isinstance(data, dict) else data) or []
        for kind, spans in (("removed", removed), ("added back", added)):
            for a, b in spans:
                if b - a < 0.03:
                    continue
                said = _words_between(wl, a, b)
                sign = "−" if kind == "removed" else "+"
                what = ("“%s”" % said) if said else ("a pause at %s" % _mmss(a))
                bullets.append("Cut: %s %s (%s%.1f s)" % (kind, what, sign, b - a))
        moved = sum(1 for x, y in zip(old_segs, new_segs) if x != y) if len(old_segs) == len(new_segs) else 0
        if not removed and not added and moved:
            bullets.append("Cut: adjusted %d cut point%s" % (moved, "" if moved == 1 else "s"))

    old_tail = (old.get("cut", {}) or {}).get("tail", DEFAULT_TAIL)
    new_tail = (new.get("cut", {}) or {}).get("tail", DEFAULT_TAIL)
    if old_tail != new_tail:
        bullets.append("Cut: tail %.2fs → %.2fs" % (old_tail, new_tail))

    # captions
    old_cap, new_cap = old.get("captions", {}) or {}, new.get("captions", {}) or {}
    if old_cap.get("mode", "auto") != new_cap.get("mode", "auto"):
        bullets.append("Captions: mode %s → %s" % (old_cap.get("mode", "auto"), new_cap.get("mode", "auto")))
    if bool(old_cap.get("hidden")) != bool(new_cap.get("hidden")):
        bullets.append("Captions: %s" % ("hidden" if new_cap.get("hidden") else "shown"))
    if new_cap.get("mode") == "manual" or old_cap.get("mode") == "manual":
        old_texts = [p.get("text") for p in old_cap.get("phrases", []) or []]
        new_texts = [p.get("text") for p in new_cap.get("phrases", []) or []]
        for t in old_texts:
            if t not in new_texts:
                bullets.append("Captions: removed '%s'" % t)
        for t in new_texts:
            if t not in old_texts:
                bullets.append("Captions: added '%s'" % t)

    # title
    old_title, new_title = old.get("title"), new.get("title")
    if bool(old_title) != bool(new_title):
        bullets.append("Text: title %s" % ("added" if new_title else "removed"))
    elif old_title and new_title:
        old_lines = [l.get("text") for l in old_title.get("lines", [])]
        new_lines = [l.get("text") for l in new_title.get("lines", [])]
        if old_lines != new_lines:
            bullets.append("Text: '%s' → '%s'" % (" / ".join(old_lines), " / ".join(new_lines)))
        if old_title.get("until") != new_title.get("until"):
            bullets.append("Text: title until %s → %s" % (old_title.get("until"), new_title.get("until")))

    # headlines
    old_hl, new_hl = _by_id(old.get("headlines")), _by_id(new.get("headlines"))
    for hid in old_hl:
        if hid not in new_hl:
            bullets.append("Text: removed headline %s" % hid)
    for hid in new_hl:
        if hid not in old_hl:
            bullets.append("Text: added headline %s" % hid)
    for hid in old_hl:
        if hid in new_hl:
            ot = [l.get("text") for l in old_hl[hid].get("lines", []) if not l.get("dim")]
            nt = [l.get("text") for l in new_hl[hid].get("lines", []) if not l.get("dim")]
            if ot != nt:
                bullets.append("Text: '%s' → '%s'" % (" / ".join(ot), " / ".join(nt)))

    # moments
    old_mo, new_mo = _by_id(old.get("moments")), _by_id(new.get("moments"))
    for mid in old_mo:
        if mid not in new_mo:
            bullets.append("Moments: removed %s (%s)" % (mid, old_mo[mid].get("kind")))
    for mid in new_mo:
        if mid not in old_mo:
            bullets.append("Moments: added %s" % new_mo[mid].get("kind"))
    for mid in old_mo:
        if mid in new_mo and old_mo[mid].get("kind") != new_mo[mid].get("kind"):
            bullets.append("Moments: %s changed kind %s → %s" % (mid, old_mo[mid].get("kind"), new_mo[mid].get("kind")))

    # sound
    old_snd, new_snd = old.get("sound", {}) or {}, new.get("sound", {}) or {}
    if bool(old_snd.get("auto", True)) != bool(new_snd.get("auto", True)):
        bullets.append("Sound: auto SFX %s" % ("on" if new_snd.get("auto", True) else "off"))
    old_muted, new_muted = set(old_snd.get("muted", []) or []), set(new_snd.get("muted", []) or [])
    for k in old_muted - new_muted:
        bullets.append("Sound: unmuted %s" % k)
    for k in new_muted - old_muted:
        bullets.append("Sound: muted %s" % k)
    if old_snd.get("sfx_gain_db", 0) != new_snd.get("sfx_gain_db", 0):
        bullets.append("Sound: SFX gain %sdB → %sdB" % (old_snd.get("sfx_gain_db", 0), new_snd.get("sfx_gain_db", 0)))
    if old_snd.get("voice_lufs", DEFAULT_VOICE_LUFS) != new_snd.get("voice_lufs", DEFAULT_VOICE_LUFS):
        bullets.append("Sound: voice loudness %s → %s LUFS" % (old_snd.get("voice_lufs"), new_snd.get("voice_lufs")))

    return bullets


# ---------------------------------------------------------------------------
# rough cut
# ---------------------------------------------------------------------------

def _wrap_title_lines(title, max_lines=4, max_chars=18):
    """Wrap a title into short lines without ever dropping words: widen the line length until it fits in
    `max_lines` (the headline renderer shrinks the font to fit the widest line)."""
    import re
    # " — " separates a title from its subtitle: break the line there instead of printing the dash.
    parts = [p.split() for p in re.split(r"\s+[\u2014\u2013-]\s+", (title or "").strip()) if p.strip()]
    if not parts:
        return [{"text": title or "", "hl": None}]
    width = max_chars
    while True:
        lines = []
        for words in parts:
            cur = ""
            for w in words:
                cand = ("%s %s" % (cur, w)).strip()
                if len(cand) <= width or not cur:
                    cur = cand
                else:
                    lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
        if len(lines) <= max_lines or width > 60:
            break
        width += 2
    return [{"text": l, "hl": None} for l in lines]


def rough_cut_spec(clip_id, source_file, words_path, ranges, title) -> dict:
    """Build a minimal recipe straight from an approved proposal: the kept
    ranges become snap:true segments, captions are auto, and the title is
    the proposal title wrapped into <=3 short lines with no highlight, shown
    until just after the first caption phrase (or a flat 4s fallback)."""
    segments = [{"a": float(a), "b": float(b), "snap": True, "mute": False} for a, b in (ranges or [])]
    spec = {
        "schema": 1,
        "clip": clip_id,
        "source": {"file": source_file, "words": words_path, "speaker_tile": list(DEFAULT_SPEAKER_TILE)},
        "cut": {"segments": segments, "tail": DEFAULT_TAIL},
        "captions": {"mode": "auto", "phrases": [], "hidden": False},
        "title": {"lines": _wrap_title_lines(title), "until": None},
        "headlines": [],
        "moments": [],
        "sound": {"auto": True, "sfx_gain_db": 0, "muted": [], "extra": [],
                   "voice_lufs": DEFAULT_VOICE_LUFS, "true_peak": DEFAULT_TRUE_PEAK},
        "look": {"preset": "house-v1"},
        "output": dict(DEFAULT_OUTPUT),
    }

    until_src = (ranges[0][0] + 4.0) if ranges else 4.0
    try:
        words = _load_words(spec)
        phrases = auto_captions(spec, words) if words else []
        if phrases:
            until_src = phrases[0]["b"] + 1.5
    except Exception:
        pass
    spec["title"]["until"] = until_src
    return spec
