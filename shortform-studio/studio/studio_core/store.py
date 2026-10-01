"""JSON-file store for Shortform Studio.

One JSON file per clip / recording under DATA_DIR, atomic writes (tempfile +
os.replace), fcntl.flock guarding read-modify-write, and an append-only
events.jsonl activity feed. No database, no server dependency - the CLI works
directly against this module.
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
import re
import tempfile
import time
import uuid

from . import paths


# ---------------------------------------------------------------------------
# low level: atomic json read/write + locking
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "." + \
        ("%03d" % (int((time.time() % 1) * 1000))) + "Z"


def ensure_dir(path: str) -> None:
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def read_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except ValueError:
        return default


def write_json_atomic(path: str, data) -> None:
    ensure_dir(os.path.dirname(path))
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def locked(lock_path: str):
    """Exclusive lock guarding read-modify-write of a JSON record."""
    ensure_dir(os.path.dirname(lock_path))
    fh = open(lock_path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "clip"


def short_id() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

def append_event(actor, type_, text, clip=None, rec=None):
    ensure_dir(paths.data_dir())
    entry = {
        "ts": now_iso(),
        "actor": actor,
        "type": type_,
        "text": text,
    }
    if clip is not None:
        entry["clip"] = clip
    if rec is not None:
        entry["rec"] = rec
    path = paths.events_file()
    ensure_dir(os.path.dirname(path))
    lock_path = path + ".lock"
    with locked(lock_path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _tail_lines(path, max_lines):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    return lines[-max_lines:]


def list_events(limit=100, clip=None, rec=None):
    lines = _tail_lines(paths.events_file(), max(limit * 20, 2000))
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if clip is not None and e.get("clip") != clip:
            continue
        if rec is not None and e.get("rec") != rec:
            continue
        events.append(e)
    events.reverse()
    return events[:limit]


def last_event_for(clip=None, rec=None):
    events = list_events(limit=1, clip=clip, rec=rec)
    return events[0] if events else None


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "director_name": "Director",
    "editor_name": "AI editor",
    "auto_dispatch": False,
    # Headless dispatch command for "process the queue" runs. `{prompt}` is the
    # brief text, `{workdir}` the clip's render folder, `{studio_dir}` this
    # studio/ folder, `{data_dir}` the STUDIO_DATA_DIR root. Swap this array in
    # Settings to use another CLI agent, e.g. for Codex:
    #   ["codex", "exec", "--full-auto", "--cd", "{workdir}", "{prompt}"]
    "dispatch_command": [
        "claude", "-p", "{prompt}",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Bash Read Edit Write Glob Grep",
        "--add-dir", "{workdir}",
        "--add-dir", "{studio_dir}",
        "--add-dir", "{data_dir}",
    ],
    "media_roots": None,  # resolved lazily to paths.default_media_roots()
    # Optional approved bespoke-renderer project (render.py + assets/) a first cut
    # can start from instead of the bundled recipe renderer. Empty by default.
    "house_template": None,
    # v2: approving a proposal builds the rough-cut recipe and renders v1 automatically.
    "auto_rough_cut": True,
    # Neutral default theme for the house-style recipe renderer. Override any of
    # these hex colours (and/or "font", a Google Fonts family name) from Settings;
    # SKILL.md fills them from a brand's marketing-brain.md when one is supplied.
    "theme": {
        "background": "#F4F3EF",
        "text": "#1C1C1C",
        "accent": "#3B6EA5",
        "accent2": "#2B4C6F",
        "font": "Inter",
    },
}


def get_settings():
    data = read_json(paths.settings_file(), None)
    if data is None:
        data = dict(DEFAULT_SETTINGS)
        data["media_roots"] = [p for p in paths.default_media_roots()]
        write_json_atomic(paths.settings_file(), data)
        return data
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    if not merged.get("media_roots"):
        merged["media_roots"] = [p for p in paths.default_media_roots()]
    return merged


def update_settings(patch: dict):
    lock_path = paths.settings_file() + ".lock"
    with locked(lock_path):
        cur = get_settings()
        cur.update({k: v for k, v in patch.items() if v is not None or k in cur})
        write_json_atomic(paths.settings_file(), cur)
        return cur


# ---------------------------------------------------------------------------
# batches
# ---------------------------------------------------------------------------

def list_batches():
    return read_json(paths.batches_file(), [])


def ensure_batch(name):
    if not name:
        return
    lock_path = paths.batches_file() + ".lock"
    with locked(lock_path):
        batches = read_json(paths.batches_file(), [])
        for b in batches:
            if b.get("id") == name or b.get("name") == name:
                return
        batches.append({"id": name, "name": name, "note": "", "created": now_iso()})
        write_json_atomic(paths.batches_file(), batches)


# ---------------------------------------------------------------------------
# taste
# ---------------------------------------------------------------------------

def get_taste():
    data = read_json(paths.taste_file(), None)
    if data is not None:
        return data
    # First run: seed from the bundled generic taste book (references/taste-seed.json)
    # so a new batch starts with sensible defaults instead of an empty rule list.
    seed = read_json(paths.taste_seed_file(), {"rules": []})
    ts = now_iso()
    rules = [dict(r, created=r.get("created") or ts) for r in seed.get("rules", [])]
    data = {"rules": rules}
    write_json_atomic(paths.taste_file(), data)
    return data


def list_rules(status=None):
    rules = get_taste().get("rules", [])
    if status:
        rules = [r for r in rules if r.get("status") == status]
    return rules


def _next_rule_id(rules):
    n = 0
    for r in rules:
        m = re.match(r"^r(\d+)$", r.get("id", ""))
        if m:
            n = max(n, int(m.group(1)))
    return "r%d" % (n + 1)


def add_rule(text, author="director", status=None, source=None):
    lock_path = paths.taste_file() + ".lock"
    with locked(lock_path):
        taste = get_taste()
        rules = taste.get("rules", [])
        rid = _next_rule_id(rules)
        if status is None:
            status = "active" if author == "director" else "proposed"
        rule = {
            "id": rid,
            "text": text,
            "status": status,
            "author": author,
            "source": source,
            "created": now_iso(),
        }
        rules.append(rule)
        taste["rules"] = rules
        write_json_atomic(paths.taste_file(), taste)
        append_event(author, "taste_proposed" if status == "proposed" else "taste_added", text)
        return rule


def update_rule(rid, patch):
    lock_path = paths.taste_file() + ".lock"
    with locked(lock_path):
        taste = get_taste()
        rules = taste.get("rules", [])
        for r in rules:
            if r.get("id") == rid:
                r.update({k: v for k, v in patch.items() if v is not None})
                taste["rules"] = rules
                write_json_atomic(paths.taste_file(), taste)
                append_event("director", "taste_updated", r.get("text", ""))
                return r
        return None


def delete_rule(rid):
    lock_path = paths.taste_file() + ".lock"
    with locked(lock_path):
        taste = get_taste()
        rules = taste.get("rules", [])
        new_rules = [r for r in rules if r.get("id") != rid]
        if len(new_rules) == len(rules):
            return False
        taste["rules"] = new_rules
        write_json_atomic(paths.taste_file(), taste)
        return True


# ---------------------------------------------------------------------------
# clips
# ---------------------------------------------------------------------------

def _unique_id(base, existing_ids_fn):
    existing = existing_ids_fn()
    if base not in existing:
        return base
    i = 2
    while ("%s-%d" % (base, i)) in existing:
        i += 1
    return "%s-%d" % (base, i)


def list_clip_ids():
    ensure_dir(paths.clips_dir())
    ids = []
    try:
        for name in os.listdir(paths.clips_dir()):
            if name.endswith(".json"):
                ids.append(name[:-5])
    except FileNotFoundError:
        pass
    return ids


def unique_clip_id(title, explicit=None):
    if explicit:
        return _unique_id(slugify(explicit), lambda: set(list_clip_ids()))
    return _unique_id(slugify(title), lambda: set(list_clip_ids()))


def get_clip(clip_id):
    return read_json(paths.clip_file(clip_id), None)


def clip_exists(clip_id):
    return os.path.exists(paths.clip_file(clip_id))


def list_clips():
    return [get_clip(cid) for cid in list_clip_ids() if get_clip(cid) is not None]


def _empty_agent():
    return {"state": "idle", "pid": None, "run_id": None, "started": None,
            "ended": None, "log": None, "message": ""}


def create_clip(title, id=None, batch=None, brief="", source="", workdir=None,
                 status="drafting", versions=None, priority=0, tags=None):
    clip_id = unique_clip_id(title, explicit=id)
    if batch:
        ensure_batch(batch)
    clip = {
        "id": clip_id,
        "title": title,
        "batch": batch or "",
        "brief": brief or "",
        "source": source or "",
        "workdir": workdir or "",
        "status": status,
        "approved_version": None,
        "priority": priority or 0,
        "tags": tags or [],
        "created": now_iso(),
        "updated": now_iso(),
        "director_seen_version": None,
        "versions": versions or [],
        "comments": [],
        "agent": _empty_agent(),
    }
    with locked(paths.clip_lock_file(clip_id)):
        write_json_atomic(paths.clip_file(clip_id), clip)
    append_event("director", "clip_created", "Created clip \"%s\"" % title, clip=clip_id)
    return clip


def update_clip_fields(clip_id, patch):
    def fn(clip):
        for k in ("title", "brief", "source", "workdir", "batch", "priority", "tags", "status"):
            if k in patch and patch[k] is not None:
                clip[k] = patch[k]
        if patch.get("batch"):
            ensure_batch(patch["batch"])
        return clip
    return mutate_clip(clip_id, fn)


def mutate_clip(clip_id, fn):
    """Read-modify-write a clip under its lock. fn(clip) mutates in place
    and may return a replacement dict. Bumps `updated`. Returns the saved
    clip, or None if the clip does not exist."""
    lock_path = paths.clip_lock_file(clip_id)
    with locked(lock_path):
        clip = get_clip(clip_id)
        if clip is None:
            return None
        result = fn(clip)
        if result is not None:
            clip = result
        clip["updated"] = now_iso()
        write_json_atomic(paths.clip_file(clip_id), clip)
        return clip


def _next_comment_id(comments):
    n = 0
    for c in comments:
        m = re.match(r"^c(\d+)$", c.get("id", ""))
        if m:
            n = max(n, int(m.group(1)))
    return "c%d" % (n + 1)


def clip_has_director_drafts(clip):
    return any(c.get("author") == "director" and c.get("status") == "draft"
               for c in clip.get("comments", []))


def add_clip_comment(clip_id, version, text, t=None, t_end=None, author="director",
                      parent=None, status=None):
    result = {}

    def fn(clip):
        comments = clip.get("comments", [])
        cid = _next_comment_id(comments)
        st = status
        if st is None:
            st = "resolved" if (author == "editor" and parent) else "draft"
        comment = {
            "id": cid, "version": version, "t": t, "t_end": t_end,
            "text": text, "author": author, "parent": parent, "status": st,
            "addressed_in": None, "created": now_iso(), "updated": now_iso(),
        }
        comments.append(comment)
        clip["comments"] = comments
        result["comment"] = comment
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None, None
    kind = "reply" if (author == "editor" and parent) else "comment_added"
    append_event(author, kind, text, clip=clip_id)
    return clip, result["comment"]


def update_clip_comment(clip_id, cid, patch):
    result = {}

    def fn(clip):
        for c in clip.get("comments", []):
            if c.get("id") == cid:
                for k in ("text", "status", "t", "t_end"):
                    if k in patch and patch[k] is not None:
                        c[k] = patch[k]
                c["updated"] = now_iso()
                result["comment"] = c
                break
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None or "comment" not in result:
        return None, None
    if patch.get("status"):
        append_event("director", "comment_%s" % patch["status"], result["comment"].get("text", ""), clip=clip_id)
    return clip, result["comment"]


def delete_clip_comment(clip_id, cid, force=False):
    result = {"ok": False}

    def fn(clip):
        comments = clip.get("comments", [])
        for c in comments:
            if c.get("id") == cid:
                if c.get("status") != "draft" and not force:
                    result["error"] = "only draft comments can be deleted"
                    return clip
                clip["comments"] = [x for x in comments if x.get("id") != cid]
                result["ok"] = True
                break
        else:
            result["error"] = "not found"
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None, {"error": "not found"}
    return clip, result


def send_clip_notes(clip_id):
    sent_count = {"n": 0}

    def fn(clip):
        for c in clip.get("comments", []):
            if c.get("author") == "director" and c.get("status") == "draft":
                c["status"] = "sent"
                c["updated"] = now_iso()
                sent_count["n"] += 1
        clip["status"] = "queued"
        clip["agent"]["state"] = "queued"
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None, 0
    append_event("director", "notes_sent", "Sent %d note(s)" % sent_count["n"], clip=clip_id)
    return clip, sent_count["n"]


def claim_clip(clip_id, message=None):
    def fn(clip):
        clip["status"] = "working"
        clip["agent"]["state"] = "working"
        clip["agent"]["started"] = now_iso()
        clip["agent"]["ended"] = None
        clip["agent"]["message"] = message or ""
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None
    append_event("editor", "claimed", message or "Claimed", clip=clip_id)
    return clip


def _next_version_n(versions, kind):
    if not versions:
        return 0 if kind == "original" else 1
    return max(v.get("n", 0) for v in versions) + 1


def add_clip_version(clip_id, file, notes="", addresses=None, label=None, kind="render", probe=None):
    addresses = addresses or []
    result = {}

    def fn(clip):
        versions = clip.get("versions", [])
        n = _next_version_n(versions, kind)
        version = {
            "n": n, "label": label or ("original" if kind == "original" else "v%d" % n),
            "kind": kind, "file": file, "created": now_iso(), "notes": notes or "",
            "addresses": addresses,
            "duration": (probe or {}).get("duration"),
            "width": (probe or {}).get("width"),
            "height": (probe or {}).get("height"),
            "size": (probe or {}).get("size"),
        }
        versions.append(version)
        clip["versions"] = versions
        for c in clip.get("comments", []):
            if c.get("id") in addresses:
                c["status"] = "addressed"
                c["addressed_in"] = n
                c["updated"] = now_iso()
        clip["status"] = "review"
        clip["agent"]["state"] = "idle"
        clip["agent"]["ended"] = now_iso()
        result["version"] = version
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None, None
    append_event("editor", "version_added", "Added %s" % result["version"]["label"], clip=clip_id)
    return clip, result["version"]


def approve_clip(clip_id, version):
    def fn(clip):
        clip["status"] = "approved"
        clip["approved_version"] = version
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None
    append_event("director", "approved", "Approved v%s" % version, clip=clip_id)
    return clip


def unapprove_clip(clip_id):
    def fn(clip):
        clip["status"] = "review"
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None
    append_event("director", "unapproved", "Unapproved", clip=clip_id)
    return clip


def set_clip_status(clip_id, status):
    def fn(clip):
        clip["status"] = status
        return clip

    clip = mutate_clip(clip_id, fn)
    if clip is None:
        return None
    append_event("director", "status_changed", "Status -> %s" % status, clip=clip_id)
    return clip


def mark_clip_seen(clip_id, version):
    def fn(clip):
        clip["director_seen_version"] = version
        return clip
    return mutate_clip(clip_id, fn)


def set_clip_agent(clip_id, patch):
    def fn(clip):
        clip["agent"].update(patch)
        return clip
    return mutate_clip(clip_id, fn)


# ---------------------------------------------------------------------------
# v2: clip.render (the render job's last-known state, mirrored from jobs.py)
# ---------------------------------------------------------------------------

DEFAULT_RENDER_STATE = {
    "state": "idle",  # idle | running | done | error
    "progress": None,
    "message": "",
    "version": None,
    "started": None,
    "ended": None,
}


def clip_render_state(clip):
    state = dict(DEFAULT_RENDER_STATE)
    state.update(clip.get("render") or {})
    return state


def set_clip_render(clip_id, patch):
    def fn(clip):
        cur = dict(DEFAULT_RENDER_STATE)
        cur.update(clip.get("render") or {})
        cur.update(patch)
        clip["render"] = cur
        return clip
    return mutate_clip(clip_id, fn)


# ---------------------------------------------------------------------------
# v2: recipes ("the edit spec") + snapshots -- DATA_DIR/edits/<clip_id>.json
# ---------------------------------------------------------------------------

def get_recipe(clip_id):
    return read_json(paths.edit_file(clip_id), None)


def recipe_exists(clip_id):
    return os.path.isfile(paths.edit_file(clip_id))


def save_recipe(clip_id, spec):
    lock_path = paths.edit_lock_file(clip_id)
    with locked(lock_path):
        write_json_atomic(paths.edit_file(clip_id), spec)
    return spec


def _snapshot_versions(clip_id):
    d = paths.edit_snapshot_dir(clip_id)
    out = []
    try:
        for name in os.listdir(d):
            m = re.match(r"^v(\d+)\.json$", name)
            if m:
                out.append(int(m.group(1)))
    except FileNotFoundError:
        pass
    return sorted(out)


def snapshot_recipe(clip_id, spec, version):
    ensure_dir(paths.edit_snapshot_dir(clip_id))
    write_json_atomic(paths.edit_snapshot_file(clip_id, version), spec)
    return spec


def latest_snapshot(clip_id, max_version=None):
    """The most recently rendered recipe (the highest snapshot number, optionally
    bounded to <= max_version). None if nothing has ever been rendered."""
    versions = _snapshot_versions(clip_id)
    if max_version is not None:
        versions = [v for v in versions if v <= max_version]
    if not versions:
        return None
    return read_json(paths.edit_snapshot_file(clip_id, max(versions)), None)


def find_proposal_for_clip(clip_id):
    """The (recording, proposal) pair whose approved proposal produced this clip,
    or (None, None) if none references it."""
    for rec in list_recordings():
        for p in rec.get("proposals", []):
            if p.get("clip_id") == clip_id:
                return rec, p
    return None, None


def build_rough_cut_spec(clip_id):
    """Build (without saving) the rough-cut recipe for clip_id from the proposal
    that was approved into it. None if no proposal references this clip."""
    rec, proposal = find_proposal_for_clip(clip_id)
    if rec is None or proposal is None:
        return None
    from studio_core import house_plan  # lazy: stdlib module written by a parallel worker
    ranges = proposal.get("ranges") or []
    title = proposal.get("title") or ""
    return house_plan.rough_cut_spec(clip_id, rec.get("file"), rec.get("transcript"), ranges, title)


def create_rough_cut_recipe(clip_id, overwrite=False):
    """Create (and save) the rough-cut recipe for clip_id.

    Idempotent unless overwrite=True: with overwrite=False and a recipe that
    already exists, returns it unchanged (created=False) so approving a
    proposal twice never clobbers a director's edits or renders twice.
    Returns (spec, created) or (None, False) when no approved proposal is found.
    """
    if not overwrite:
        existing = get_recipe(clip_id)
        if existing is not None:
            return existing, False
    spec = build_rough_cut_spec(clip_id)
    if spec is None:
        return None, False
    save_recipe(clip_id, spec)
    append_event("editor", "recipe_created", "Created rough-cut recipe", clip=clip_id)
    return spec, True


# ---------------------------------------------------------------------------
# recordings
# ---------------------------------------------------------------------------

def list_recording_ids():
    ensure_dir(paths.recordings_dir())
    ids = []
    try:
        for name in os.listdir(paths.recordings_dir()):
            if name.endswith(".json"):
                ids.append(name[:-5])
    except FileNotFoundError:
        pass
    return ids


def unique_recording_id(title, explicit=None):
    if explicit:
        return _unique_id(slugify(explicit), lambda: set(list_recording_ids()))
    return _unique_id(slugify(title), lambda: set(list_recording_ids()))


def get_recording(rec_id):
    return read_json(paths.recording_file(rec_id), None)


def list_recordings():
    return [get_recording(rid) for rid in list_recording_ids() if get_recording(rid) is not None]


def create_recording(title, file, id=None, transcript=None, batch=None, date=None,
                      notes="", probe=None):
    rec_id = unique_recording_id(title, explicit=id)
    if batch:
        ensure_batch(batch)
    rec = {
        "id": rec_id,
        "title": title,
        "batch": batch or "",
        "date": date or "",
        "file": file,
        "transcript": transcript or "",
        "duration": (probe or {}).get("duration"),
        "width": (probe or {}).get("width"),
        "height": (probe or {}).get("height"),
        "notes": notes or "",
        "status": "new",
        "agent": _empty_agent(),
        "created": now_iso(),
        "updated": now_iso(),
        "proposals": [],
        "comments": [],
    }
    with locked(paths.recording_lock_file(rec_id)):
        write_json_atomic(paths.recording_file(rec_id), rec)
    append_event("director", "recording_added", "Added recording \"%s\"" % title, rec=rec_id)
    return rec


def mutate_recording(rec_id, fn):
    lock_path = paths.recording_lock_file(rec_id)
    with locked(lock_path):
        rec = get_recording(rec_id)
        if rec is None:
            return None
        result = fn(rec)
        if result is not None:
            rec = result
        rec["updated"] = now_iso()
        write_json_atomic(paths.recording_file(rec_id), rec)
        return rec


def update_recording_fields(rec_id, patch):
    def fn(rec):
        for k in ("title", "notes", "batch", "date", "status"):
            if k in patch and patch[k] is not None:
                rec[k] = patch[k]
        if patch.get("batch"):
            ensure_batch(patch["batch"])
        return rec
    return mutate_recording(rec_id, fn)


def add_recording_comment(rec_id, text, t=None, t_end=None, proposal=None,
                           author="director", parent=None, status=None):
    result = {}

    def fn(rec):
        comments = rec.get("comments", [])
        cid = _next_comment_id(comments)
        st = status
        if st is None:
            st = "resolved" if (author == "editor" and parent) else "draft"
        comment = {
            "id": cid, "version": None, "t": t, "t_end": t_end, "text": text,
            "author": author, "parent": parent, "status": st, "proposal": proposal,
            "addressed_in": None, "created": now_iso(), "updated": now_iso(),
        }
        comments.append(comment)
        rec["comments"] = comments
        result["comment"] = comment
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None, None
    kind = "reply" if (author == "editor" and parent) else "comment_added"
    append_event(author, kind, text, rec=rec_id)
    return rec, result["comment"]


def update_recording_comment(rec_id, cid, patch):
    result = {}

    def fn(rec):
        for c in rec.get("comments", []):
            if c.get("id") == cid:
                for k in ("text", "status", "t", "t_end"):
                    if k in patch and patch[k] is not None:
                        c[k] = patch[k]
                c["updated"] = now_iso()
                result["comment"] = c
                break
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None or "comment" not in result:
        return None, None
    return rec, result["comment"]


def delete_recording_comment(rec_id, cid, force=False):
    result = {"ok": False}

    def fn(rec):
        comments = rec.get("comments", [])
        for c in comments:
            if c.get("id") == cid:
                if c.get("status") != "draft" and not force:
                    result["error"] = "only draft comments can be deleted"
                    return rec
                rec["comments"] = [x for x in comments if x.get("id") != cid]
                result["ok"] = True
                break
        else:
            result["error"] = "not found"
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None, {"error": "not found"}
    return rec, result


def send_recording_notes(rec_id):
    sent_count = {"n": 0}

    def fn(rec):
        for c in rec.get("comments", []):
            if c.get("author") == "director" and c.get("status") == "draft":
                c["status"] = "sent"
                c["updated"] = now_iso()
                sent_count["n"] += 1
                if c.get("proposal"):
                    for p in rec.get("proposals", []):
                        if p.get("id") == c["proposal"]:
                            p["status"] = "needs_changes"
                            p["updated"] = now_iso()
        rec["status"] = "queued"
        rec["agent"]["state"] = "queued"
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None, 0
    append_event("director", "notes_sent", "Sent %d note(s)" % sent_count["n"], rec=rec_id)
    return rec, sent_count["n"]


def claim_recording(rec_id, message=None):
    def fn(rec):
        rec["status"] = "working"
        rec["agent"]["state"] = "working"
        rec["agent"]["started"] = now_iso()
        rec["agent"]["ended"] = None
        rec["agent"]["message"] = message or ""
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None
    append_event("editor", "claimed", message or "Claimed", rec=rec_id)
    return rec


def _next_proposal_id(proposals):
    n = 0
    for p in proposals:
        m = re.match(r"^p(\d+)$", p.get("id", ""))
        if m:
            n = max(n, int(m.group(1)))
    return "p%d" % (n + 1)


def add_proposal(rec_id, title, ranges, hook="", summary="", score=None,
                  transcript="", author="editor", addresses=None):
    result = {}

    def fn(rec):
        proposals = rec.get("proposals", [])
        pid = _next_proposal_id(proposals)
        proposal = {
            "id": pid, "title": title, "hook": hook or "", "ranges": ranges,
            "summary": summary or "", "transcript": transcript or "",
            "score": score, "status": "proposed", "clip_id": None,
            "author": author, "created": now_iso(), "updated": now_iso(),
        }
        proposals.append(proposal)
        rec["proposals"] = proposals
        if addresses:
            for c in rec.get("comments", []):
                if c.get("id") in addresses:
                    c["status"] = "addressed"
                    c["addressed_in"] = pid
                    c["updated"] = now_iso()
        result["proposal"] = proposal
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None, None
    append_event(author, "proposal_added", "Proposed \"%s\"" % title, rec=rec_id)
    return rec, result["proposal"]


def update_proposal(rec_id, pid, patch, addresses=None):
    result = {}

    def fn(rec):
        for p in rec.get("proposals", []):
            if p.get("id") == pid:
                for k in ("title", "ranges", "hook", "summary", "score", "status", "transcript"):
                    if k in patch and patch[k] is not None:
                        p[k] = patch[k]
                p["updated"] = now_iso()
                result["proposal"] = p
                break
        if addresses:
            for c in rec.get("comments", []):
                if c.get("id") in addresses:
                    c["status"] = "addressed"
                    c["addressed_in"] = pid
                    c["updated"] = now_iso()
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None or "proposal" not in result:
        return None, None
    append_event("editor", "proposal_updated", result["proposal"].get("title", ""), rec=rec_id)
    return rec, result["proposal"]


def proposals_ready(rec_id, addresses=None):
    def fn(rec):
        if addresses:
            for c in rec.get("comments", []):
                if c.get("id") in addresses:
                    c["status"] = "addressed"
                    c["addressed_in"] = "proposals-ready"
                    c["updated"] = now_iso()
        rec["status"] = "proposed"
        rec["agent"]["state"] = "idle"
        rec["agent"]["ended"] = now_iso()
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None
    append_event("editor", "proposals_ready", "Finished proposing clips", rec=rec_id)
    return rec


def reject_proposal(rec_id, pid):
    result = {}

    def fn(rec):
        for p in rec.get("proposals", []):
            if p.get("id") == pid:
                p["status"] = "rejected"
                p["updated"] = now_iso()
                result["proposal"] = p
                break
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None or "proposal" not in result:
        return None, None
    append_event("director", "proposal_rejected", result["proposal"].get("title", ""), rec=rec_id)
    return rec, result["proposal"]


def _clip_workdir_for(clip_id):
    return os.path.join(paths.renders_root(), clip_id)


def _fmt_mss(sec):
    if sec is None:
        return ""
    m = int(sec // 60)
    s = sec - m * 60
    return "%d:%04.1f" % (m, s)


def _words_in_ranges(words, ranges):
    picked = []
    for a, b in ranges:
        for w in words:
            ws, we = w.get("start"), w.get("end")
            if ws is None:
                continue
            if ws >= a and we <= b:
                picked.append((ws, w.get("word", "")))
    picked.sort(key=lambda x: x[0])
    return " ".join(w for _, w in picked).strip()


def approve_proposal(rec_id, pid, transcript_words=None):
    """Approve a proposal: mark it approved and create the resulting clip.

    Returns (rec, proposal, clip) or (None, None, None) if not found.
    """
    result = {}

    def fn(rec):
        for p in rec.get("proposals", []):
            if p.get("id") == pid:
                if p.get("status") == "approved" and p.get("clip_id"):
                    result["existing"] = p
                    return rec
                result["proposal"] = dict(p)
                result["rec_file"] = rec.get("file")
                result["rec_title"] = rec.get("title")
                result["batch"] = rec.get("batch")
                # Claim the proposal inside the same lock so a double click / concurrent request can't
                # create a second clip.
                result["clip_id"] = unique_clip_id(p.get("title", "clip"))
                p["status"] = "approved"
                p["clip_id"] = result["clip_id"]
                p["updated"] = now_iso()
                break
        return rec

    rec = mutate_recording(rec_id, fn)
    if rec is None:
        return None, None, None
    if "existing" in result:
        p = result["existing"]
        return rec, p, get_clip(p.get("clip_id"))
    if "proposal" not in result:
        return rec, None, None

    proposal = result["proposal"]
    ranges = proposal.get("ranges") or []
    hook = proposal.get("hook", "")
    summary = proposal.get("summary", "")
    transcript_text = proposal.get("transcript") or ""
    if not transcript_text and transcript_words:
        transcript_text = _words_in_ranges(transcript_words, ranges)

    range_lines = ", ".join("%s-%s" % (_fmt_mss(a), _fmt_mss(b)) for a, b in ranges)
    brief_parts = []
    if hook:
        brief_parts.append(hook.strip())
    if summary:
        brief_parts.append(summary.strip())
    brief_parts.append("Ranges (source time): %s" % range_lines)
    if transcript_text:
        brief_parts.append("Transcript of kept speech:\n\n%s" % transcript_text)
    brief = "\n\n".join(brief_parts)

    source = "%s ranges %s" % (result.get("rec_file", ""), range_lines)
    clip_id = result["clip_id"]
    workdir = _clip_workdir_for(clip_id)

    clip = create_clip(
        title=proposal.get("title", clip_id),
        id=clip_id,
        batch=result.get("batch"),
        brief=brief,
        source=source,
        workdir=workdir,
        status="queued",
    )
    set_clip_agent(clip_id, {"state": "queued"})
    clip = get_clip(clip_id)

    def fn2(rec2):
        for p in rec2.get("proposals", []):
            if p.get("id") == pid:
                p["status"] = "approved"
                p["clip_id"] = clip_id
                p["updated"] = now_iso()
        return rec2

    rec = mutate_recording(rec_id, fn2)
    updated_proposal = next((p for p in rec.get("proposals", []) if p.get("id") == pid), proposal)
    append_event("director", "proposal_approved",
                 "Approved \"%s\" -> clip %s" % (updated_proposal.get("title", ""), clip_id), rec=rec_id)
    return rec, updated_proposal, clip


def set_recording_agent(rec_id, patch):
    def fn(rec):
        rec["agent"].update(patch)
        return rec
    return mutate_recording(rec_id, fn)
