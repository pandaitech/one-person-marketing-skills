"""ThreadingHTTPServer: JSON REST API, static web/ files, and Range-capable
media/thumb/filmstrip/waveform endpoints. Binds 127.0.0.1 only.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import dispatch, jobs, media, paths, store

log = logging.getLogger("studio")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
    ".txt": "text/plain; charset=utf-8",
    ".ico": "image/x-icon",
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# summaries
# ---------------------------------------------------------------------------

def _latest_version(clip):
    versions = clip.get("versions", [])
    if not versions:
        return None
    return max(versions, key=lambda v: v.get("n", 0))


def _canonical(obj):
    """A stable JSON string for structural equality comparisons (recipe vs snapshot)."""
    if obj is None:
        return None
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def clip_summary(clip):
    latest = _latest_version(clip)
    comments = clip.get("comments", [])
    open_counts = {
        "draft": sum(1 for c in comments if c.get("status") == "draft" and c.get("author") == "director"),
        "sent": sum(1 for c in comments if c.get("status") == "sent"),
        "addressed": sum(1 for c in comments if c.get("status") == "addressed"),
    }
    seen = clip.get("director_seen_version")
    new_version = bool(latest is not None and (seen is None or latest["n"] > seen))
    has_recipe = store.recipe_exists(clip["id"])
    dirty = False
    if has_recipe:
        spec = store.get_recipe(clip["id"])
        snap = store.latest_snapshot(clip["id"])
        dirty = (_canonical(spec) != _canonical(snap)) if snap is not None else True
    render_state = store.clip_render_state(clip)
    return {
        "id": clip["id"], "title": clip.get("title"), "batch": clip.get("batch"),
        "status": clip.get("status"), "agent": clip.get("agent"),
        "approved_version": clip.get("approved_version"),
        "latest_version": latest["n"] if latest else None,
        "version_count": len(clip.get("versions", [])),
        "duration": latest.get("duration") if latest else None,
        "poster_url": ("/thumb/%s/%d.jpg" % (clip["id"], latest["n"])) if latest else None,
        "updated": clip.get("updated"),
        "open": open_counts,
        "new_version": new_version,
        "last_event": store.last_event_for(clip=clip["id"]),
        "has_recipe": has_recipe,
        "dirty": dirty,
        "render": {"state": render_state.get("state"), "progress": render_state.get("progress")},
    }


def clip_detail(clip):
    out = dict(clip)
    versions = []
    for v in clip.get("versions", []):
        vv = dict(v)
        vv["media_url"] = "/media/%s/%d" % (clip["id"], v["n"])
        vv["poster_url"] = "/thumb/%s/%d.jpg" % (clip["id"], v["n"])
        vv["filmstrip_url"] = "/filmstrip/%s/%d.jpg" % (clip["id"], v["n"])
        vv["waveform_url"] = "/waveform/%s/%d.png" % (clip["id"], v["n"])
        versions.append(vv)
    out["versions"] = versions
    return out


def recording_summary(rec):
    proposals = rec.get("proposals", [])
    counts = {"proposed": 0, "approved": 0, "rejected": 0, "needs_changes": 0}
    for p in proposals:
        st = p.get("status")
        if st in counts:
            counts[st] += 1
    comments = rec.get("comments", [])
    open_counts = {
        "draft": sum(1 for c in comments if c.get("status") == "draft" and c.get("author") == "director"),
        "sent": sum(1 for c in comments if c.get("status") == "sent"),
    }
    return {
        "id": rec["id"], "title": rec.get("title"), "batch": rec.get("batch"),
        "date": rec.get("date"), "duration": rec.get("duration"), "status": rec.get("status"),
        "agent": rec.get("agent"), "poster_url": "/thumb/rec/%s.jpg" % rec["id"],
        "proposals": counts, "open": open_counts, "updated": rec.get("updated"),
    }


def recording_detail(rec):
    out = dict(rec)
    out["media_url"] = "/media/rec/%s" % rec["id"]
    out["poster_url"] = "/thumb/rec/%s.jpg" % rec["id"]
    out["waveform_url"] = "/waveform/rec/%s.png" % rec["id"]
    return out


def state_payload():
    clips = store.list_clips()
    recordings = store.list_recordings()
    review = 0
    queued = 0
    working = 0
    approved = 0
    published = 0
    drafts = 0
    rendering = 0
    for c in clips:
        st = c.get("status")
        has_drafts = store.clip_has_director_drafts(c)
        if st == "review" or has_drafts:
            review += 1
        if has_drafts:
            drafts += 1
        if st == "queued":
            queued += 1
        if st == "working":
            working += 1
        if st == "approved":
            approved += 1
        if st == "published":
            published += 1
        if store.clip_render_state(c).get("state") == "running":
            rendering += 1
    proposals = sum(1 for r in recordings for p in r.get("proposals", []) if p.get("status") == "proposed")
    return {
        "now": store.now_iso(),
        "settings": store.get_settings(),
        "batches": store.list_batches(),
        "taste": store.get_taste(),
        "clips": [clip_summary(c) for c in clips],
        "recordings": [recording_summary(r) for r in recordings],
        "counts": {
            "review": review, "queued": queued, "working": working,
            "approved": approved, "published": published, "drafts": drafts,
            "proposals": proposals, "rendering": rendering,
        },
    }


# ---------------------------------------------------------------------------
# transcript compaction (cached in memory by mtime)
# ---------------------------------------------------------------------------

_transcript_cache = {}
_transcript_cache_lock = threading.Lock()


def group_words(words, gap=0.7, max_words=28, max_secs=14.0):
    """Group [[word, start, end], ...] into [[start, end, text], ...] rows, breaking on pauses and length."""
    rows, cur = [], []
    for w in words:
        if cur:
            pause = w[1] - (cur[-1][2] or cur[-1][1])
            too_long = len(cur) >= max_words or (w[1] - cur[0][1]) >= max_secs
            if pause >= gap or too_long:
                rows.append([cur[0][1], cur[-1][2] or cur[-1][1], " ".join(x[0] for x in cur)])
                cur = []
        cur.append(w)
    if cur:
        rows.append([cur[0][1], cur[-1][2] or cur[-1][1], " ".join(x[0] for x in cur)])
    return rows


def compact_transcript(path):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        raise ApiError(404, "transcript file not found")
    with _transcript_cache_lock:
        cached = _transcript_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
    data = store.read_json(path, None)
    if data is None:
        raise ApiError(404, "transcript file not readable")
    segments = [[s.get("start"), s.get("end"), (s.get("text") or "").strip()] for s in data.get("segments", [])]
    words = [[w.get("word"), w.get("start"), w.get("end")] for w in data.get("word_segments", [])
             if w.get("start") is not None]
    # Some timelines (whisper.cpp with max-len 1) store one word per "segment". A transcript of single words is
    # unreadable, so regroup words into phrase rows when segments are that short.
    if words and (not segments or sum(len((s[2] or "").split()) for s in segments) / max(1, len(segments)) < 3):
        segments = group_words(words)
    out = {"segments": segments, "words": words}
    with _transcript_cache_lock:
        _transcript_cache[path] = (mtime, out)
    return out


def transcript_words(rec):
    path = rec.get("transcript")
    if not path:
        return []
    data = store.read_json(path, None)
    if not data:
        return []
    return data.get("word_segments", [])


# ---------------------------------------------------------------------------
# request body / query helpers
# ---------------------------------------------------------------------------

def _q(query, name, default=None):
    v = query.get(name)
    if not v:
        return default
    return v[0]


def _qf(query, name, default=None):
    v = _q(query, name)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _qi(query, name, default=None):
    v = _q(query, name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _require(body, *names):
    # 0 is a valid value (version 0 = the original cut); only None/""/absent count as missing
    missing = [n for n in names if body.get(n) is None or body.get(n) == ""]
    if missing:
        raise ApiError(400, "missing field(s): %s" % ", ".join(missing))


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def api_get_state(m, q, body):
    return 200, state_payload()


def api_get_clip(m, q, body):
    clip = store.get_clip(m.group(1))
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, clip_detail(clip)


def api_post_clip(m, q, body):
    _require(body, "title")
    clip = store.create_clip(
        title=body["title"], id=body.get("id"), batch=body.get("batch"),
        brief=body.get("brief", ""), source=body.get("source", ""),
        workdir=body.get("workdir"),
    )
    return 200, clip


def api_patch_clip(m, q, body):
    clip = store.update_clip_fields(m.group(1), body)
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, clip


def api_post_comment(m, q, body):
    clip_id = m.group(1)
    if not store.clip_exists(clip_id):
        raise ApiError(404, "unknown clip")
    _require(body, "text")
    version = body.get("version")
    if version is None:
        c = store.get_clip(clip_id)
        latest = _latest_version(c)
        version = latest["n"] if latest else 0
    clip, comment = store.add_clip_comment(
        clip_id, version, body["text"], t=body.get("t"), t_end=body.get("t_end"),
        author=body.get("author", "director"), parent=body.get("parent"))
    return 200, comment


def api_patch_comment(m, q, body):
    clip, comment = store.update_clip_comment(m.group(1), m.group(2), body)
    if clip is None or comment is None:
        raise ApiError(404, "unknown clip or comment")
    return 200, comment


def api_delete_comment(m, q, body):
    force = _q(q, "force") == "1"
    clip, result = store.delete_clip_comment(m.group(1), m.group(2), force=force)
    if clip is None:
        raise ApiError(404, "unknown clip")
    if not result.get("ok"):
        raise ApiError(400, result.get("error", "cannot delete"))
    return 200, {"ok": True}


def api_send(m, q, body):
    clip_id = m.group(1)
    clip, n = store.send_clip_notes(clip_id)
    if clip is None:
        raise ApiError(404, "unknown clip")
    dispatched = False
    settings = store.get_settings()
    if settings.get("auto_dispatch") and n > 0:
        try:
            dispatch.dispatch_clip(clip_id)
            dispatched = True
        except dispatch.DispatchError as e:
            store.append_event("system", "dispatch_error", str(e), clip=clip_id)
    out = dict(clip)
    out["dispatched"] = dispatched
    return 200, out


def api_approve(m, q, body):
    _require(body, "version")
    clip = store.approve_clip(m.group(1), body["version"])
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, clip


def api_unapprove(m, q, body):
    clip = store.unapprove_clip(m.group(1))
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, clip


def api_seen(m, q, body):
    _require(body, "version")
    clip = store.mark_clip_seen(m.group(1), body["version"])
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, {"ok": True}


def api_post_version(m, q, body):
    clip_id = m.group(1)
    if not store.clip_exists(clip_id):
        raise ApiError(404, "unknown clip")
    _require(body, "file")
    file_path = body["file"]
    if not os.path.isfile(file_path):
        raise ApiError(400, "file does not exist: %s" % file_path)
    info = media.probe(file_path)
    clip, version = store.add_clip_version(
        clip_id, file_path, notes=body.get("notes", ""), addresses=body.get("addresses"),
        label=body.get("label"), kind=body.get("kind", "render"), probe=info)
    return 200, version


def api_claim(m, q, body):
    clip = store.claim_clip(m.group(1), message=(body or {}).get("message"))
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, clip


def api_dispatch(m, q, body):
    try:
        run_id, log_path = dispatch.dispatch_clip(m.group(1))
    except dispatch.DispatchError as e:
        raise ApiError(400, str(e))
    return 200, {"ok": True, "run_id": run_id, "log": log_path}


def api_log(m, q, body):
    clip = store.get_clip(m.group(1))
    if clip is None:
        raise ApiError(404, "unknown clip")
    lines = _qi(q, "lines", 200)
    log_path = clip.get("agent", {}).get("log")
    text = ""
    if log_path and os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        text = "".join(all_lines[-lines:])
    running = clip.get("agent", {}).get("state") == "working"
    return 200, {"text": text, "running": running}


def api_brief(m, q, body):
    clip = store.get_clip(m.group(1))
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, {"text": dispatch.clip_brief(clip)}


# --- v2: recipes / plan / render job ----------------------------------

def _plan_safe(spec):
    """house_plan.plan(spec), but a bad spec or a plan-time error must never
    500 the edit view -- return (None, message) instead."""
    try:
        from studio_core import house_plan
    except ImportError as e:
        return None, "house_plan not available: %s" % e
    try:
        errors = house_plan.validate(spec)
    except Exception as e:
        return None, "plan_error: %s" % e
    if errors:
        return None, "invalid spec: %s" % "; ".join(errors)
    try:
        return house_plan.plan(spec), None
    except Exception as e:
        return None, "plan_error: %s" % e


def _changes_since_snapshot(clip, spec, snap):
    if snap is None:
        return [] if clip.get("versions") else ["First render"]
    try:
        from studio_core import house_plan
        return house_plan.diff(snap, spec)
    except Exception:
        return []


def _edit_payload(clip, spec):
    plan, plan_error = _plan_safe(spec)
    latest = _latest_version(clip)
    rendered_version = latest["n"] if latest else None
    snap = store.latest_snapshot(clip["id"])
    dirty = (_canonical(spec) != _canonical(snap)) if snap is not None else True
    changes = _changes_since_snapshot(clip, spec, snap)
    job = store.clip_render_state(clip)
    return {
        "spec": spec, "plan": plan, "plan_error": plan_error,
        "rendered_version": rendered_version, "dirty": dirty,
        "changes": changes, "job": job,
    }


def api_get_edit(m, q, body):
    clip_id = m.group(1)
    clip = store.get_clip(clip_id)
    if clip is None:
        raise ApiError(404, "unknown clip")
    spec = store.get_recipe(clip_id)
    if spec is None:
        raise ApiError(404, "no recipe")
    return 200, _edit_payload(clip, spec)


def api_put_edit(m, q, body):
    clip_id = m.group(1)
    clip = store.get_clip(clip_id)
    if clip is None:
        raise ApiError(404, "unknown clip")
    spec = body.get("spec") if isinstance(body, dict) else None
    if spec is None:
        raise ApiError(400, "missing field(s): spec")
    try:
        from studio_core import house_plan
        errors = house_plan.validate(spec)
    except ImportError:
        errors = []
    if errors:
        return 400, {"error": "invalid spec", "errors": errors}
    store.save_recipe(clip_id, spec)
    clip = store.get_clip(clip_id)
    return 200, _edit_payload(clip, spec)


def api_rough_cut(m, q, body):
    clip_id = m.group(1)
    clip = store.get_clip(clip_id)
    if clip is None:
        raise ApiError(404, "unknown clip")
    spec, created = store.create_rough_cut_recipe(clip_id, overwrite=True)
    if spec is None:
        raise ApiError(400, "no approved proposal found for clip %s" % clip_id)
    clip = store.get_clip(clip_id)
    return 200, _edit_payload(clip, spec)


def api_words(m, q, body):
    clip_id = m.group(1)
    clip = store.get_clip(clip_id)
    if clip is None:
        raise ApiError(404, "unknown clip")
    pad = _qf(q, "pad", 30.0)
    spec = store.get_recipe(clip_id)
    words_path, ranges = None, []
    if spec is not None:
        words_path = (spec.get("source") or {}).get("words")
        ranges = [[seg.get("a"), seg.get("b")] for seg in (spec.get("cut") or {}).get("segments", [])
                  if seg.get("a") is not None and seg.get("b") is not None]
    if not words_path:
        rec, proposal = store.find_proposal_for_clip(clip_id)
        if rec is not None:
            words_path = rec.get("transcript")
            if not ranges:
                ranges = proposal.get("ranges") or []
    if not words_path:
        return 200, {"words": []}
    data = store.read_json(words_path, None)
    if not data:
        return 200, {"words": []}
    all_words = [[w.get("word"), w.get("start"), w.get("end")] for w in data.get("word_segments", [])
                 if w.get("start") is not None]
    if not ranges:
        return 200, {"words": all_words}
    lo = min(a for a, b in ranges) - pad
    hi = max(b for a, b in ranges) + pad
    picked = [w for w in all_words
              if w[1] is not None and w[1] >= lo and (w[2] if w[2] is not None else w[1]) <= hi]
    return 200, {"words": picked}


def api_post_render(m, q, body):
    clip_id = m.group(1)
    if not store.clip_exists(clip_id):
        raise ApiError(404, "unknown clip")
    body = body or {}
    note = body.get("note")
    addresses = body.get("addresses")
    try:
        job = jobs.start_render(clip_id, note=note, addresses=addresses)
    except jobs.RenderError as e:
        raise ApiError(400, str(e))
    return 200, {"job": job}


def api_get_render(m, q, body):
    clip = store.get_clip(m.group(1))
    if clip is None:
        raise ApiError(404, "unknown clip")
    return 200, {"job": store.clip_render_state(clip)}


def api_get_taste(m, q, body):
    return 200, store.get_taste()


def api_post_taste(m, q, body):
    _require(body, "text")
    rule = store.add_rule(body["text"], author=body.get("author", "director"), source=body.get("source"))
    return 200, rule


def api_patch_taste(m, q, body):
    rule = store.update_rule(m.group(1), body)
    if rule is None:
        raise ApiError(404, "unknown rule")
    return 200, rule


def api_delete_taste(m, q, body):
    ok = store.delete_rule(m.group(1))
    if not ok:
        raise ApiError(404, "unknown rule")
    return 200, {"ok": True}


def api_events(m, q, body):
    limit = _qi(q, "limit", 100)
    clip = _q(q, "clip")
    return 200, {"events": store.list_events(limit=limit, clip=clip)}


def api_patch_settings(m, q, body):
    settings = store.update_settings(body)
    return 200, settings


# --- recordings -------------------------------------------------------

def api_get_recordings(m, q, body):
    return 200, {"recordings": [recording_summary(r) for r in store.list_recordings()]}


def api_post_recording(m, q, body):
    _require(body, "title", "file")
    info = media.probe(body["file"]) if os.path.isfile(body["file"]) else {}
    rec = store.create_recording(
        title=body["title"], file=body["file"], id=body.get("id"),
        transcript=body.get("transcript"), batch=body.get("batch"), date=body.get("date"),
        notes=body.get("notes", ""), probe=info)
    return 200, rec


def api_get_recording(m, q, body):
    rec = store.get_recording(m.group(1))
    if rec is None:
        raise ApiError(404, "unknown recording")
    return 200, recording_detail(rec)


def api_patch_recording(m, q, body):
    rec = store.update_recording_fields(m.group(1), body)
    if rec is None:
        raise ApiError(404, "unknown recording")
    return 200, rec


def api_recording_transcript(m, q, body):
    rec = store.get_recording(m.group(1))
    if rec is None:
        raise ApiError(404, "unknown recording")
    if not rec.get("transcript"):
        return 200, {"segments": [], "words": []}
    return 200, compact_transcript(rec["transcript"])


def api_post_proposal(m, q, body):
    rec_id = m.group(1)
    if not store.get_recording(rec_id):
        raise ApiError(404, "unknown recording")
    _require(body, "title", "ranges")
    rec, proposal = store.add_proposal(
        rec_id, body["title"], body["ranges"], hook=body.get("hook", ""),
        summary=body.get("summary", ""), score=body.get("score"),
        transcript=body.get("transcript", ""), author=body.get("author", "editor"),
        addresses=body.get("addresses"))
    return 200, proposal


def api_patch_proposal(m, q, body):
    rec, proposal = store.update_proposal(m.group(1), m.group(2), body, addresses=body.get("addresses"))
    if rec is None or proposal is None:
        raise ApiError(404, "unknown recording or proposal")
    return 200, proposal


def api_approve_proposal(m, q, body):
    rec_id, pid = m.group(1), m.group(2)
    rec_before = store.get_recording(rec_id)
    if rec_before is None:
        raise ApiError(404, "unknown recording")
    already = any(p.get("id") == pid and p.get("status") == "approved" and p.get("clip_id")
                  for p in rec_before.get("proposals", []))
    words = transcript_words(rec_before)
    rec, proposal, clip = store.approve_proposal(rec_id, pid, transcript_words=words)
    if rec is None or proposal is None:
        raise ApiError(404, "unknown recording or proposal")
    settings = store.get_settings()
    if clip and not already:
        created = False
        try:
            _spec, created = store.create_rough_cut_recipe(clip["id"])
        except Exception as e:
            store.append_event("system", "recipe_error", str(e), clip=clip["id"])
        if created and settings.get("auto_rough_cut", True):
            try:
                jobs.start_render(clip["id"], note="Rough cut")
                clip = store.get_clip(clip["id"])
            except jobs.RenderError as e:
                store.append_event("system", "render_error", str(e), clip=clip["id"])
    if settings.get("auto_dispatch") and clip and not already and proposal.get("clip_id") == clip.get("id") \
            and (clip.get("agent") or {}).get("state") != "working":
        try:
            dispatch.dispatch_clip(clip["id"])
            clip = store.get_clip(clip["id"])
        except dispatch.DispatchError as e:
            store.append_event("system", "dispatch_error", str(e), clip=clip["id"])
    return 200, {"proposal": proposal, "clip": clip}


def api_reject_proposal(m, q, body):
    rec, proposal = store.reject_proposal(m.group(1), m.group(2))
    if rec is None or proposal is None:
        raise ApiError(404, "unknown recording or proposal")
    return 200, proposal


def api_post_recording_comment(m, q, body):
    rec_id = m.group(1)
    if not store.get_recording(rec_id):
        raise ApiError(404, "unknown recording")
    _require(body, "text")
    rec, comment = store.add_recording_comment(
        rec_id, body["text"], t=body.get("t"), t_end=body.get("t_end"),
        proposal=body.get("proposal"), author=body.get("author", "director"),
        parent=body.get("parent"))
    return 200, comment


def api_patch_recording_comment(m, q, body):
    rec, comment = store.update_recording_comment(m.group(1), m.group(2), body)
    if rec is None or comment is None:
        raise ApiError(404, "unknown recording or comment")
    return 200, comment


def api_delete_recording_comment(m, q, body):
    force = _q(q, "force") == "1"
    rec, result = store.delete_recording_comment(m.group(1), m.group(2), force=force)
    if rec is None:
        raise ApiError(404, "unknown recording")
    if not result.get("ok"):
        raise ApiError(400, result.get("error", "cannot delete"))
    return 200, {"ok": True}


def api_send_recording(m, q, body):
    rec_id = m.group(1)
    rec, n = store.send_recording_notes(rec_id)
    if rec is None:
        raise ApiError(404, "unknown recording")
    dispatched = False
    settings = store.get_settings()
    if settings.get("auto_dispatch") and n > 0:
        try:
            dispatch.dispatch_recording(rec_id)
            dispatched = True
        except dispatch.DispatchError as e:
            store.append_event("system", "dispatch_error", str(e), rec=rec_id)
    out = dict(rec)
    out["dispatched"] = dispatched
    return 200, out


def api_claim_recording(m, q, body):
    rec = store.claim_recording(m.group(1), message=(body or {}).get("message"))
    if rec is None:
        raise ApiError(404, "unknown recording")
    return 200, rec


def api_dispatch_recording(m, q, body):
    try:
        run_id, log_path = dispatch.dispatch_recording(m.group(1))
    except dispatch.DispatchError as e:
        raise ApiError(400, str(e))
    return 200, {"ok": True, "run_id": run_id, "log": log_path}


def api_log_recording(m, q, body):
    rec = store.get_recording(m.group(1))
    if rec is None:
        raise ApiError(404, "unknown recording")
    lines = _qi(q, "lines", 200)
    log_path = rec.get("agent", {}).get("log")
    text = ""
    if log_path and os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        text = "".join(all_lines[-lines:])
    running = rec.get("agent", {}).get("state") == "working"
    return 200, {"text": text, "running": running}


def api_brief_recording(m, q, body):
    rec = store.get_recording(m.group(1))
    if rec is None:
        raise ApiError(404, "unknown recording")
    return 200, {"text": dispatch.recording_brief(rec)}


ROUTES = [
    ("GET", r"^/api/state$", api_get_state),
    ("GET", r"^/api/events$", api_events),
    ("GET", r"^/api/taste$", api_get_taste),
    ("POST", r"^/api/taste$", api_post_taste),
    ("PATCH", r"^/api/taste/([^/]+)$", api_patch_taste),
    ("DELETE", r"^/api/taste/([^/]+)$", api_delete_taste),
    ("PATCH", r"^/api/settings$", api_patch_settings),

    ("GET", r"^/api/recordings$", api_get_recordings),
    ("POST", r"^/api/recordings$", api_post_recording),
    ("GET", r"^/api/recordings/([^/]+)$", api_get_recording),
    ("PATCH", r"^/api/recordings/([^/]+)$", api_patch_recording),
    ("GET", r"^/api/recordings/([^/]+)/transcript$", api_recording_transcript),
    ("POST", r"^/api/recordings/([^/]+)/proposals$", api_post_proposal),
    ("PATCH", r"^/api/recordings/([^/]+)/proposals/([^/]+)$", api_patch_proposal),
    ("POST", r"^/api/recordings/([^/]+)/proposals/([^/]+)/approve$", api_approve_proposal),
    ("POST", r"^/api/recordings/([^/]+)/proposals/([^/]+)/reject$", api_reject_proposal),
    ("POST", r"^/api/recordings/([^/]+)/comments$", api_post_recording_comment),
    ("PATCH", r"^/api/recordings/([^/]+)/comments/([^/]+)$", api_patch_recording_comment),
    ("DELETE", r"^/api/recordings/([^/]+)/comments/([^/]+)$", api_delete_recording_comment),
    ("POST", r"^/api/recordings/([^/]+)/send$", api_send_recording),
    ("POST", r"^/api/recordings/([^/]+)/claim$", api_claim_recording),
    ("POST", r"^/api/recordings/([^/]+)/dispatch$", api_dispatch_recording),
    ("GET", r"^/api/recordings/([^/]+)/log$", api_log_recording),
    ("GET", r"^/api/recordings/([^/]+)/brief$", api_brief_recording),

    ("GET", r"^/api/clips/([^/]+)$", api_get_clip),
    ("POST", r"^/api/clips$", api_post_clip),
    ("PATCH", r"^/api/clips/([^/]+)$", api_patch_clip),
    ("POST", r"^/api/clips/([^/]+)/comments$", api_post_comment),
    ("PATCH", r"^/api/clips/([^/]+)/comments/([^/]+)$", api_patch_comment),
    ("DELETE", r"^/api/clips/([^/]+)/comments/([^/]+)$", api_delete_comment),
    ("POST", r"^/api/clips/([^/]+)/send$", api_send),
    ("POST", r"^/api/clips/([^/]+)/approve$", api_approve),
    ("POST", r"^/api/clips/([^/]+)/unapprove$", api_unapprove),
    ("POST", r"^/api/clips/([^/]+)/seen$", api_seen),
    ("POST", r"^/api/clips/([^/]+)/versions$", api_post_version),
    ("POST", r"^/api/clips/([^/]+)/claim$", api_claim),
    ("POST", r"^/api/clips/([^/]+)/dispatch$", api_dispatch),
    ("GET", r"^/api/clips/([^/]+)/log$", api_log),
    ("GET", r"^/api/clips/([^/]+)/brief$", api_brief),

    ("GET", r"^/api/clips/([^/]+)/edit$", api_get_edit),
    ("PUT", r"^/api/clips/([^/]+)/edit$", api_put_edit),
    ("POST", r"^/api/clips/([^/]+)/edit/rough-cut$", api_rough_cut),
    ("GET", r"^/api/clips/([^/]+)/words$", api_words),
    ("POST", r"^/api/clips/([^/]+)/render$", api_post_render),
    ("GET", r"^/api/clips/([^/]+)/render$", api_get_render),
]
COMPILED_ROUTES = [(method, re.compile(pattern), fn) for method, pattern, fn in ROUTES]


# ---------------------------------------------------------------------------
# media routes
# ---------------------------------------------------------------------------

MEDIA_ROUTES = [
    ("media_rec", re.compile(r"^/media/rec/([^/]+)$")),
    ("media_clip", re.compile(r"^/media/([^/]+)/(\d+)$")),
    ("thumb_rec", re.compile(r"^/thumb/rec/([^/]+)\.jpg$")),
    ("thumb_clip", re.compile(r"^/thumb/([^/]+)/(\d+)\.jpg$")),
    ("filmstrip_clip", re.compile(r"^/filmstrip/([^/]+)/(\d+)\.jpg$")),
    ("waveform_rec", re.compile(r"^/waveform/rec/([^/]+)\.png$")),
    ("waveform_clip", re.compile(r"^/waveform/([^/]+)/(\d+)\.png$")),
]

# v2: not plain JSON, so routed outside COMPILED_ROUTES/_dispatch_api.
STILL_RE = re.compile(r"^/api/clips/([^/]+)/still\.jpg$")
ASSET_UPLOAD_RE = re.compile(r"^/api/clips/([^/]+)/assets$")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _sanitize_asset_name(name):
    name = os.path.basename((name or "").strip())
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return name or "asset"


def _media_roots():
    roots = store.get_settings().get("media_roots") or paths.default_media_roots()
    return [os.path.realpath(os.path.expanduser(r)) for r in roots]


def _media_allowed(file_path):
    if not file_path:
        return False
    rp = os.path.realpath(file_path)
    for root in _media_roots():
        if rp == root or rp.startswith(root + os.sep):
            return True
    return False


def _version_file(clip_id, n):
    clip = store.get_clip(clip_id)
    if clip is None:
        return None
    for v in clip.get("versions", []):
        if v.get("n") == n:
            return v.get("file")
    return None


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ShortformStudio/1.0"

    def log_message(self, fmt, *args):
        path = self.path.split("?", 1)[0]
        if path.startswith("/media/") or path.startswith("/thumb/") or \
           path.startswith("/filmstrip/") or path.startswith("/waveform/"):
            return
        log.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "invalid JSON body")

    def _dispatch_api(self, method, path, query):
        body = {}
        if method in ("POST", "PATCH", "PUT"):
            body = self._read_body()
        for m, pattern, fn in COMPILED_ROUTES:
            if m != method:
                continue
            match = pattern.match(path)
            if match:
                status, data = fn(match, query, body)
                self._send_json(status, data)
                return
        self._send_json(404, {"error": "not found"})

    def _serve_range(self, file_path, content_type):
        if not file_path or not os.path.isfile(file_path):
            self._send_json(404, {"error": "media not found"})
            return
        if not _media_allowed(file_path):
            self._send_json(403, {"error": "file is outside configured media roots"})
            return
        try:
            size = os.path.getsize(file_path)
        except OSError:
            self._send_json(404, {"error": "media not found"})
            return
        start, end = 0, size - 1
        status = 200
        range_header = self.headers.get("Range")
        if range_header:
            match = re.match(r"bytes=(\d*)-(\d*)", range_header)
            if match:
                s, e = match.groups()
                if s == "" and e != "":
                    length = int(e)
                    start = max(size - length, 0)
                    end = size - 1
                else:
                    start = int(s) if s else 0
                    end = int(e) if e else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    try:
                        self.send_response(416)
                        self.send_header("Content-Range", "bytes */%d" % size)
                        self.end_headers()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    return
                status = 206
        length = end - start + 1
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            if status == 206:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            return
        if self.command == "HEAD":
            return
        try:
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                chunk = 256 * 1024
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    self.wfile.write(data)
                    remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_generated(self, file_path, content_type, max_age=60):
        if not os.path.isfile(file_path):
            self._send_json(404, {"error": "not generated"})
            return
        with open(file_path, "rb") as f:
            data = f.read()
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "max-age=%d" % max_age)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_still(self, path, query):
        clip_id = STILL_RE.match(path).group(1)
        if not store.clip_exists(clip_id):
            self._send_json(404, {"error": "unknown clip"})
            return
        t = _qf(query, "t", 0.0)
        width = _qi(query, "w", 540)
        try:
            target = jobs.still_jpg(clip_id, t, width=width)
        except jobs.RenderError as e:
            self._send_json(400, {"error": str(e)})
            return
        except Exception as e:  # pragma: no cover - defensive
            self._send_json(500, {"error": str(e)})
            return
        self._serve_generated(target, "image/jpeg", max_age=3600)

    def _handle_asset_upload(self, path, query):
        clip_id = ASSET_UPLOAD_RE.match(path).group(1)
        clip = store.get_clip(clip_id)
        if clip is None:
            self._send_json(404, {"error": "unknown clip"})
            return
        name = _sanitize_asset_name(_q(query, "name"))
        ext = os.path.splitext(name)[1].lower()
        if ext not in IMAGE_EXTS:
            self._send_json(400, {"error": "unsupported image extension: %s" % (ext or "(none)")})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._send_json(400, {"error": "empty body"})
            return
        if length > 25 * 1024 * 1024:
            self._send_json(400, {"error": "file too large (25 MB max)"})
            return
        raw = self.rfile.read(length)
        workdir = clip.get("workdir") or os.path.join(
            paths.renders_root(), clip_id)
        img_dir = os.path.join(workdir, "assets", "img")
        store.ensure_dir(img_dir)
        target = os.path.join(img_dir, name)
        if os.path.exists(target):
            base, ext2 = os.path.splitext(name)
            i = 2
            while os.path.exists(os.path.join(img_dir, "%s-%d%s" % (base, i, ext2))):
                i += 1
            target = os.path.join(img_dir, "%s-%d%s" % (base, i, ext2))
        with open(target, "wb") as f:
            f.write(raw)
        self._send_json(200, {"path": target})

    def _dispatch_media(self, path, query):
        for name, pattern in MEDIA_ROUTES:
            match = pattern.match(path)
            if not match:
                continue
            if name == "media_rec":
                rec = store.get_recording(match.group(1))
                if rec is None:
                    self._send_json(404, {"error": "unknown recording"})
                    return
                self._serve_range(rec.get("file"), "video/mp4")
                return
            if name == "media_clip":
                clip_id, n = match.group(1), int(match.group(2))
                self._serve_range(_version_file(clip_id, n), "video/mp4")
                return
            if name == "thumb_rec":
                rec = store.get_recording(match.group(1))
                if rec is None or not rec.get("file"):
                    self._send_json(404, {"error": "unknown recording"})
                    return
                t = _qf(query, "t")
                path_out = media.poster("rec", rec["id"], 0, rec["file"], t=t, width=480)
                self._serve_generated(path_out, "image/jpeg")
                return
            if name == "thumb_clip":
                clip_id, n = match.group(1), int(match.group(2))
                file_path = _version_file(clip_id, n)
                if not file_path:
                    self._send_json(404, {"error": "unknown clip/version"})
                    return
                t = _qf(query, "t")
                path_out = media.poster("clip", clip_id, n, file_path, t=t, width=360)
                self._serve_generated(path_out, "image/jpeg")
                return
            if name == "filmstrip_clip":
                clip_id, n = match.group(1), int(match.group(2))
                file_path = _version_file(clip_id, n)
                if not file_path:
                    self._send_json(404, {"error": "unknown clip/version"})
                    return
                path_out = media.filmstrip("clip", clip_id, n, file_path)
                self._serve_generated(path_out, "image/jpeg")
                return
            if name == "waveform_rec":
                rec = store.get_recording(match.group(1))
                if rec is None or not rec.get("file"):
                    self._send_json(404, {"error": "unknown recording"})
                    return
                path_out = media.waveform("rec", rec["id"], 0, rec["file"], width=3000, height=80)
                self._serve_generated(path_out, "image/png")
                return
            if name == "waveform_clip":
                clip_id, n = match.group(1), int(match.group(2))
                file_path = _version_file(clip_id, n)
                if not file_path:
                    self._send_json(404, {"error": "unknown clip/version"})
                    return
                path_out = media.waveform("clip", clip_id, n, file_path, width=1600, height=96)
                self._serve_generated(path_out, "image/png")
                return
        self._send_json(404, {"error": "not found"})

    def _dispatch_static(self, path):
        web_root = os.path.realpath(paths.web_dir())
        if path == "/":
            rel = "index.html"
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
        else:
            rel = path.lstrip("/")
        if not rel:
            rel = "index.html"
        target = os.path.normpath(os.path.join(web_root, rel))
        if target != web_root and not target.startswith(web_root + os.sep):
            self._send_json(404, {"error": "not found"})
            return
        if not os.path.isfile(target):
            if rel == "index.html":
                body = (b"<!doctype html><html><head><title>Shortform Studio</title></head>"
                        b"<body><h1>Shortform Studio</h1>"
                        b"<p>web/index.html has not been built yet.</p></body></html>")
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self._send_json(404, {"error": "not found"})
            return
        ext = os.path.splitext(target)[1].lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(target, "rb") as f:
            data = f.read()
        try:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _route(self, method):
        try:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            if STILL_RE.match(path) and method in ("GET", "HEAD"):
                self._serve_still(path, query)
            elif ASSET_UPLOAD_RE.match(path) and method == "POST":
                self._handle_asset_upload(path, query)
            elif path.startswith("/api/"):
                try:
                    self._dispatch_api(method, path, query)
                except ApiError as e:
                    self._send_json(e.status, {"error": e.message})
            elif path.startswith(("/media/", "/thumb/", "/filmstrip/", "/waveform/")):
                if method not in ("GET", "HEAD"):
                    self._send_json(404, {"error": "not found"})
                else:
                    self._dispatch_media(path, query)
            else:
                if method not in ("GET", "HEAD"):
                    self._send_json(404, {"error": "not found"})
                else:
                    self._dispatch_static(path)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # pragma: no cover - defensive
            log.exception("unhandled error")
            try:
                self._send_json(500, {"error": str(e)})
            except Exception:
                pass

    def do_GET(self):
        self._route("GET")

    def do_HEAD(self):
        self._route("HEAD")

    def do_POST(self):
        self._route("POST")

    def do_PATCH(self):
        self._route("PATCH")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")


def make_server(port=5055, host="127.0.0.1"):
    dispatch.reconcile_on_start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def run(port=5055, open_browser=False):
    httpd = make_server(port=port)
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open("http://127.0.0.1:%d/" % port)).start()
    log.info("Shortform Studio serving on http://127.0.0.1:%d (data: %s)", port, paths.data_dir())
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
