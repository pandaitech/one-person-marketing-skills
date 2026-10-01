"""Editor briefs + headless dispatch: start `settings.dispatch_command` for a
clip or recording, track pid/log, and watch for completion in a background
thread."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time

from . import paths, store

STUDIO_PY = os.path.join(paths.studio_dir(), "studio.py")


def _fmt_mss(sec):
    if sec is None:
        return "?"
    m = int(sec // 60)
    s = sec - m * 60
    return "%d:%04.1f" % (m, s)


def _py(*args):
    parts = ["python3", STUDIO_PY]
    parts.extend(args)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# briefs
# ---------------------------------------------------------------------------

def clip_brief(clip):
    cid = clip["id"]
    lines = []
    lines.append("# Editor brief: %s" % clip.get("title", cid))
    lines.append("")
    lines.append("You are the editor for the Shortform Studio director on clip `%s`." % cid)
    lines.append("The studio CLI (stdlib Python, no server needed) is at:")
    lines.append("  %s" % STUDIO_PY)
    lines.append("")
    lines.append("## Clip")
    lines.append("- Title: %s" % clip.get("title", ""))
    lines.append("- Workdir: %s" % clip.get("workdir", ""))
    lines.append("- Source: %s" % clip.get("source", ""))
    if clip.get("brief"):
        lines.append("")
        lines.append("### Brief")
        lines.append(clip["brief"])
    versions = clip.get("versions", [])
    if versions:
        lines.append("")
        lines.append("### Version history")
        for v in versions:
            lines.append("- %s (%s): %s -- %s" % (
                v.get("label"), v.get("kind"), v.get("file"),
                (v.get("notes") or "").splitlines()[0] if v.get("notes") else ""))
        latest = max(versions, key=lambda v: v.get("n", 0))
        lines.append("")
        lines.append("Latest version file: %s" % latest.get("file"))
    else:
        lines.append("")
        lines.append("No versions yet -- this is a fresh clip queued from an approved proposal.")

    sent = [c for c in clip.get("comments", []) if c.get("status") == "sent"]
    lines.append("")
    lines.append("## Sent notes (%d) -- apply every one of these" % len(sent))
    if sent:
        for c in sent:
            lines.append("- [%s] v%s @ %s: %s" % (c.get("id"), c.get("version"),
                                                    _fmt_mss(c.get("t")), c.get("text")))
    else:
        lines.append("(none -- this is the first pass)")

    addressed = [c for c in clip.get("comments", [])
                 if c.get("status") == "addressed"]
    if addressed:
        lines.append("")
        lines.append("## Addressed but not yet confirmed by the director (context, don't redo)")
        for c in addressed:
            lines.append("- [%s] v%s @ %s: %s (addressed in v%s)" % (
                c.get("id"), c.get("version"), _fmt_mss(c.get("t")), c.get("text"),
                c.get("addressed_in")))

    rules = store.list_rules(status="active")
    lines.append("")
    lines.append("## Active taste rules")
    if rules:
        for r in rules:
            lines.append("- %s" % r.get("text"))
    else:
        lines.append("(none yet)")

    lines.append("")
    lines.append("## Procedure")
    lines.append("1. Claim the clip:")
    lines.append("   `python3 %s claim %s`" % (STUDIO_PY, cid))
    if store.recipe_exists(cid):
        recipe_path = paths.edit_file(cid)
        spec_doc = os.path.join(paths.studio_dir(), "docs", "STUDIO-V2.md")
        lines.append("2. This is a RECIPE clip (v2, \"the recipe\"). Edit the recipe JSON directly -- "
                     "never hand-edit render scripts or the rendered mp4 for a recipe clip:")
        lines.append("   %s" % recipe_path)
        lines.append("   Field-by-field schema and the resolved \"plan\" shape are in %s "
                     "(\"The recipe (edit spec)\" and \"The plan\" sections)." % spec_doc)
        lines.append("   Every time value in the recipe is in SOURCE seconds (positions in the class "
                     "recording), never output seconds -- the renderer/plan maps them for you.")
        lines.append("3. Apply every sent note above by editing the recipe JSON; keep everything else unchanged.")
        lines.append("4. Validate the recipe before rendering (exits non-zero and prints errors if invalid):")
        lines.append("   `python3 %s recipe %s`" % (STUDIO_PY, cid))
        lines.append("5. Register the new version by rendering it -- the diff between this recipe and the "
                     "last rendered one becomes the changelog automatically:")
        lines.append("   `python3 %s render %s --note \"why you made this pass\" --addresses %s`" % (
            STUDIO_PY, cid, ",".join(c.get("id") for c in sent) or "c1,c2"))
        lines.append("6. Verify the new version: full decode, check frames at each changed moment, "
                     "re-transcribe changed joins to confirm words line up.")
        lines.append("7. For any sent note you could not or chose not to address, reply explaining why:")
        lines.append("   `python3 %s reply %s <comment_id> \"why not\"`" % (STUDIO_PY, cid))
        lines.append("8. Optionally propose a taste rule you inferred:")
        lines.append("   `python3 %s taste --propose \"rule text\"`" % STUDIO_PY)
        lines.append("")
        lines.append("Verification expectation: the director will watch the new version and the "
                     "changelog must let them confirm each sent note from title/comment alone, "
                     "without re-reading your code.")
        return "\n".join(lines)
    if clip.get("versions"):
        lines.append("2. Read the workdir's README / render script at %s." % clip.get("workdir", ""))
        lines.append("3. Apply every sent note above; keep everything else unchanged.")
    else:
        template = (store.get_settings().get("house_template") or "").strip()
        lines.append("2. FIRST CUT. The workdir is new. Build v1 from the source ranges above:")
        if template:
            lines.append("   - Start from the approved bespoke renderer: copy %s/render.py and its assets/ "
                         "into the workdir, then adapt SEGMENTS, SEG_WORDS, "
                         "PHRASES (captions), HEADLINES and SCENES for this clip; OUT = renders/<clip>-v1.mp4." % template)
        else:
            lines.append("   - No bespoke renderer configured; use the Studio recipe renderer above, or "
                         "`scripts/render.py` (the standard fixed-layout renderer) from the skill root.")
        lines.append("   - Follow %s (editorial rules and final-polish reference) for word-precise cuts. "
                     "ASR word times run ~0.3-0.7 s early: place every range boundary in a real pause "
                     "(waveform RMS) and confirm each join by re-transcribing it with whisper-cli." % os.path.join(
                         paths.skill_root(), "SKILL.md"))
        lines.append("   - Keep the proposal's story (hook -> point -> payoff); cut filler only at clean gaps.")
        lines.append("3. Keep on-screen text sparse and literal, per the taste rules; speaker first.")
    lines.append("4. Render to a NEW file (never overwrite an existing version file).")
    lines.append("5. Verify: full decode of the new render, check frames at each changed moment, "
                  "re-transcribe changed joins to confirm words line up.")
    lines.append("6. Register the version with a short changelog and the notes it addresses:")
    lines.append("   `python3 %s add-version %s /abs/path/to/new-file.mp4 --notes \"what changed\" "
                  "--addresses %s`" % (STUDIO_PY, cid,
                                        ",".join(c.get("id") for c in sent) or "c1,c2"))
    lines.append("7. For any sent note you could not or chose not to address, reply explaining why:")
    lines.append("   `python3 %s reply %s <comment_id> \"why not\"`" % (STUDIO_PY, cid))
    lines.append("8. Optionally propose a taste rule you inferred:")
    lines.append("   `python3 %s taste --propose \"rule text\"`" % STUDIO_PY)
    lines.append("")
    lines.append("Verification expectation: the director will watch the new version and the "
                  "changelog must let them confirm each sent note from title/comment alone, "
                  "without re-reading your code.")
    return "\n".join(lines)


def recording_brief(rec):
    rid = rec["id"]
    lines = []
    lines.append("# Editor brief: recording %s" % rec.get("title", rid))
    lines.append("")
    lines.append("You are proposing short-form clip candidates from a full recording for the "
                 "Shortform Studio director.")
    lines.append("The studio CLI is at: %s" % STUDIO_PY)
    lines.append("")
    lines.append("## Recording")
    lines.append("- Title: %s" % rec.get("title", ""))
    lines.append("- File: %s" % rec.get("file", ""))
    lines.append("- Transcript (word timeline JSON): %s" % rec.get("transcript", ""))
    lines.append("- Duration: %s" % _fmt_mss(rec.get("duration")))
    if rec.get("notes"):
        lines.append("")
        lines.append("### Context")
        lines.append(rec["notes"])

    sent = [c for c in rec.get("comments", []) if c.get("status") == "sent"]
    lines.append("")
    lines.append("## Sent notes (%d)" % len(sent))
    if sent:
        for c in sent:
            tag = (" on proposal %s" % c["proposal"]) if c.get("proposal") else ""
            lines.append("- [%s]%s @ %s: %s" % (c.get("id"), tag, _fmt_mss(c.get("t")), c.get("text")))
    else:
        lines.append("(none -- general 'propose clips' pass)")

    existing = rec.get("proposals", [])
    if existing:
        lines.append("")
        lines.append("## Existing proposals")
        for p in existing:
            ranges = ", ".join("%s-%s" % (_fmt_mss(a), _fmt_mss(b)) for a, b in p.get("ranges", []))
            lines.append("- [%s] %s (%s): %s" % (p.get("id"), p.get("title"), p.get("status"), ranges))

    rules = store.list_rules(status="active")
    lines.append("")
    lines.append("## Director's taste (also applies to which clips are worth proposing)")
    for r in rules or []:
        lines.append("- %s" % r.get("text"))
    if not rules:
        lines.append("(none yet)")
    lines.append("- Propose only complete ideas a cold viewer understands: setup -> point -> payoff. Prefer "
                 "concrete, surprising points; skip housekeeping and class logistics.")

    lines.append("")
    lines.append("## Procedure")
    lines.append("Follow `%s` (editorial rules reference): find complete ideas, "
                 "propose 3-5 hook candidates, keep every clip clear to a cold viewer, merge/split "
                 "ranges as needed, and audit surrounding context so a range isn't cut mid-thought." % (
                     os.path.join(paths.skill_root(), "SKILL.md")))
    lines.append("1. Claim: `python3 %s claim-rec %s`" % (STUDIO_PY, rid))
    lines.append("2. Read the transcript JSON above. ASR word times run ~0.3-0.7 s early: put each range "
                 "boundary in a real pause (ffmpeg -> 16 kHz mono PCM, 10 ms RMS; silence is RMS < ~60) and "
                 "spot-check openings/joins with `whisper-cli -m ~/.cache/shortform-studio/whisper/models/"
                 "ggml-medium.bin -l ms -f probe.wav -np -nt` (swap -l for the recording's language). Titles/hooks in the recording's own language, verbatim hooks only.")
    lines.append("3. Register each candidate:")
    lines.append("   `python3 %s propose %s --title \"...\" --ranges \"674.14-693.64,693.98-731.36\" "
                 "--hook \"...\" --summary \"...\" --score 8.5`" % (STUDIO_PY, rid))
    lines.append("   (or `--json-file proposals.json` for several at once)")
    lines.append("4. To revise one you already made: "
                 "`python3 %s update-proposal %s <pid> --ranges \"...\"`" % (STUDIO_PY, rid))
    lines.append("5. When done, mark the pass finished and clear the notes you handled:")
    lines.append("   `python3 %s proposals-ready %s --addresses %s`" % (
        STUDIO_PY, rid, ",".join(c.get("id") for c in sent) or "c1"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

class DispatchError(Exception):
    pass


def _substitute(cmd_list, mapping):
    out = []
    for part in cmd_list:
        for k, v in mapping.items():
            part = part.replace("{%s}" % k, v)
        out.append(part)
    return out


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _watch(kind, ident, proc, log_path, run_id):
    proc.wait()
    if kind == "clip":
        get_fn, set_agent = store.get_clip, lambda p: store.set_clip_agent(ident, p)
    else:
        get_fn, set_agent = store.get_recording, lambda p: store.set_recording_agent(ident, p)

    record = get_fn(ident)
    if record is None:
        return
    agent = record.get("agent", {})
    if agent.get("run_id") != run_id:
        return  # superseded by a newer dispatch

    progressed = False
    if kind == "clip":
        versions = record.get("versions", [])
        started = agent.get("started")
        progressed = any(v.get("created", "") >= (started or "") for v in versions) if started else bool(versions)
        # simplest reliable signal: a version was added after dispatch started
        progressed = record.get("status") == "review" or record.get("status") == "approved"
    else:
        progressed = record.get("status") == "proposed"

    if progressed:
        set_agent({"state": "idle", "ended": store.now_iso(), "pid": None})
    else:
        tail = _log_tail(log_path, 15)
        set_agent({"state": "error", "ended": store.now_iso(), "pid": None,
                   "message": tail})
        if kind == "clip":
            store.mutate_clip(ident, lambda c: _reset_status(c, "queued"))
            store.append_event("system", "dispatch_error", tail or "editor exited without a new version",
                                clip=ident)
        else:
            store.mutate_recording(ident, lambda r: _reset_status(r, "queued"))
            store.append_event("system", "dispatch_error", tail or "editor exited without proposals-ready",
                                rec=ident)


def _reset_status(record, status):
    if record.get("status") == "working":
        record["status"] = status
    return record


def _log_tail(log_path, n):
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:]).strip()
    except OSError:
        return ""


def _resolve_executable(name):
    """PATH first; then the usual install locations (a server started from a GUI/launchd has a thin PATH)."""
    if os.path.isabs(name):
        return name if os.access(name, os.X_OK) else None
    found = shutil.which(name)
    if found:
        return found
    for d in ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin", "~/.claude/local"):
        cand = os.path.join(os.path.expanduser(d), name)
        if os.access(cand, os.X_OK):
            return cand
    return None


def _start(kind, ident, prompt, workdir, log_prefix):
    settings = store.get_settings()
    cmd_template = settings.get("dispatch_command") or []
    if not cmd_template:
        raise DispatchError("no dispatch_command configured")
    executable = _resolve_executable(cmd_template[0])
    if not executable:
        raise DispatchError("dispatch executable not found on PATH: %s" % cmd_template[0])

    # A clip created from an approved proposal gets a fresh workdir under the data dir; make it exist.
    if workdir and not os.path.isdir(workdir) and os.path.abspath(workdir).startswith(
            paths.data_dir() + os.sep):
        os.makedirs(workdir, exist_ok=True)

    mapping = {"prompt": prompt, "workdir": workdir or "", "studio_dir": paths.studio_dir(),
               "data_dir": paths.data_dir()}
    cmd = [executable] + _substitute(cmd_template[1:], mapping)

    store.ensure_dir(paths.logs_dir())
    ts = time.strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(paths.logs_dir(), "%s-%s.log" % (log_prefix, ts))
    run_id = "%s-%s" % (log_prefix, ts)

    cwd = workdir if workdir and os.path.isdir(workdir) else paths.data_dir()
    with open(log_path, "ab", buffering=0) as log_f:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=log_f, stderr=log_f,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
    # log_f is closed in the parent now; the child holds its own duplicated fd

    agent_patch = {"state": "working", "pid": proc.pid, "run_id": run_id,
                   "started": store.now_iso(), "ended": None, "log": log_path, "message": ""}
    if kind == "clip":
        store.set_clip_agent(ident, agent_patch)
    else:
        store.set_recording_agent(ident, agent_patch)

    t = threading.Thread(target=_watch, args=(kind, ident, proc, log_path, run_id), daemon=True)
    t.start()
    return run_id, log_path


def dispatch_clip(clip_id):
    clip = store.get_clip(clip_id)
    if clip is None:
        raise DispatchError("unknown clip %s" % clip_id)
    prompt = clip_brief(clip)
    run_id, log_path = _start("clip", clip_id, prompt, clip.get("workdir"), clip_id)
    store.append_event("system", "dispatch_started", "Dispatched editor run", clip=clip_id)
    return run_id, log_path


def dispatch_recording(rec_id):
    rec = store.get_recording(rec_id)
    if rec is None:
        raise DispatchError("unknown recording %s" % rec_id)
    prompt = recording_brief(rec)
    run_id, log_path = _start("rec", rec_id, prompt, None, rec_id)
    store.append_event("system", "dispatch_started", "Dispatched editor run", rec=rec_id)
    return run_id, log_path


def reconcile_on_start():
    """Called once at server startup: an agent left 'working' with a dead
    pid (e.g. the studio process was restarted) becomes an error."""
    # Only runs the studio itself started (they have a pid) can be judged dead. An editor that claimed work
    # through the CLI (chat session, subagent) has no pid and may still be busy — leave it alone.
    for clip in store.list_clips():
        agent = clip.get("agent", {})
        if agent.get("state") == "working" and agent.get("pid") and not _pid_alive(agent.get("pid")):
            tail = _log_tail(agent.get("log") or "", 15)
            store.set_clip_agent(clip["id"], {"state": "error", "message": tail or "process no longer running"})
            store.mutate_clip(clip["id"], lambda c: _reset_status(c, "queued"))
    for rec in store.list_recordings():
        agent = rec.get("agent", {})
        if agent.get("state") == "working" and agent.get("pid") and not _pid_alive(agent.get("pid")):
            tail = _log_tail(agent.get("log") or "", 15)
            store.set_recording_agent(rec["id"], {"state": "error", "message": tail or "process no longer running"})
            store.mutate_recording(rec["id"], lambda r: _reset_status(r, "queued"))
