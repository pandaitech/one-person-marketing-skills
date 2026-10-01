#!/usr/bin/env python3
"""Shortform Studio CLI.

Works directly against the JSON store (studio_core.store) -- no server
required for any subcommand except `serve`. Python 3.9 stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from studio_core import dispatch, jobs, media, paths, server, store  # noqa: E402


def _read_text_or_file(text, file_path):
    if file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return text or ""


def _parse_ranges(spec):
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([\d.]+)\s*-\s*([\d.]+)$", part)
        if not m:
            raise SystemExit("bad range %r (expected start-end seconds)" % part)
        ranges.append([float(m.group(1)), float(m.group(2))])
    return ranges


def _fmt_mss(sec):
    if sec is None:
        return "?"
    m = int(sec // 60)
    s = sec - m * 60
    return "%d:%04.1f" % (m, s)


def _print_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# clip commands
# ---------------------------------------------------------------------------

def cmd_serve(args):
    server.run(port=args.port, open_browser=args.open)


def cmd_list(args):
    clips = store.list_clips()
    if not clips:
        print("(no clips)")
        return
    for c in sorted(clips, key=lambda c: c.get("updated", ""), reverse=True):
        latest = c.get("versions", [])
        n = max((v["n"] for v in latest), default=None)
        print("%-28s %-10s agent=%-8s v=%-4s  %s" % (
            c["id"], c.get("status"), c.get("agent", {}).get("state"),
            n if n is not None else "-", c.get("title", "")))


def cmd_pending(args):
    clips = []
    for c in store.list_clips():
        if c.get("status") in ("queued", "working"):
            sent = [x for x in c.get("comments", []) if x.get("status") == "sent"]
            clips.append({
                "id": c["id"], "title": c.get("title"), "status": c.get("status"),
                "agent": c.get("agent"), "workdir": c.get("workdir"),
                "sent_notes": [{"id": x["id"], "version": x.get("version"), "t": x.get("t"),
                                "text": x.get("text")} for x in sent],
            })
    recordings = []
    for r in store.list_recordings():
        if r.get("status") in ("queued", "working"):
            sent = [x for x in r.get("comments", []) if x.get("status") == "sent"]
            recordings.append({
                "id": r["id"], "title": r.get("title"), "status": r.get("status"),
                "agent": r.get("agent"),
                "sent_notes": [{"id": x["id"], "t": x.get("t"), "proposal": x.get("proposal"),
                                "text": x.get("text")} for x in sent],
            })
    taste = store.list_rules(status="active")
    payload = {"clips": clips, "recordings": recordings, "taste": taste}
    if args.json:
        _print_json(payload)
        return
    if not clips and not recordings:
        print("(nothing pending)")
    for c in clips:
        print("CLIP %s [%s/%s] %s" % (c["id"], c["status"], c["agent"]["state"], c["title"]))
        for n in c["sent_notes"]:
            print("  - v%s @ %s: %s" % (n["version"], _fmt_mss(n["t"]), n["text"]))
    for r in recordings:
        print("REC  %s [%s/%s] %s" % (r["id"], r["status"], r["agent"]["state"], r["title"]))
        for n in r["sent_notes"]:
            print("  - @ %s: %s" % (_fmt_mss(n["t"]), n["text"]))
    if taste:
        print("Active taste rules:")
        for r in taste:
            print("  - %s" % r["text"])


def cmd_brief(args):
    clip = store.get_clip(args.clip)
    if clip is None:
        raise SystemExit("unknown clip %s" % args.clip)
    print(dispatch.clip_brief(clip))


def cmd_claim(args):
    clip = store.claim_clip(args.clip, message=args.message)
    if clip is None:
        raise SystemExit("unknown clip %s" % args.clip)
    print("claimed %s" % args.clip)


def cmd_add_clip(args):
    brief = _read_text_or_file(args.brief, args.brief_file)
    clip = store.create_clip(
        title=args.title, id=args.id, batch=args.batch, brief=brief,
        source=args.source or "", workdir=args.workdir, status="drafting")
    print("created %s" % clip["id"])
    _print_json(clip)


def cmd_add_version(args):
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    import os
    if not os.path.isfile(args.file):
        raise SystemExit("file does not exist: %s" % args.file)
    notes = _read_text_or_file(args.notes, args.notes_file)
    addresses = [x.strip() for x in args.addresses.split(",")] if args.addresses else []
    info = media.probe(args.file)
    clip, version = store.add_clip_version(
        args.clip, args.file, notes=notes, addresses=addresses,
        label=args.label, kind=args.kind, probe=info)
    print("added %s to %s" % (version["label"], args.clip))
    _print_json(version)


def cmd_comment(args):
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    clip = store.get_clip(args.clip)
    version = args.version
    if version is None:
        vs = clip.get("versions", [])
        version = max((v["n"] for v in vs), default=0)
    _, comment = store.add_clip_comment(
        args.clip, version, args.text, t=args.t, author=args.author,
        status=args.status)
    _print_json(comment)


def cmd_reply(args):
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    clip = store.get_clip(args.clip)
    target = next((c for c in clip.get("comments", []) if c["id"] == args.comment_id), None)
    if target is None:
        raise SystemExit("unknown comment %s" % args.comment_id)
    _, comment = store.add_clip_comment(
        args.clip, target.get("version"), args.text, t=target.get("t"),
        author="editor", parent=args.comment_id)
    _print_json(comment)


def cmd_status(args):
    clip = store.set_clip_status(args.clip, args.status)
    if clip is None:
        raise SystemExit("unknown clip %s" % args.clip)
    print("%s -> %s" % (args.clip, args.status))


def cmd_taste(args):
    if args.add:
        rule = store.add_rule(args.add, author="director", status="active")
        _print_json(rule)
        return
    if args.propose:
        rule = store.add_rule(args.propose, author="editor", status="proposed")
        _print_json(rule)
        return
    for r in store.list_rules():
        print("%-4s [%-8s] %s" % (r["id"], r["status"], r["text"]))


def cmd_dispatch(args):
    try:
        run_id, log_path = dispatch.dispatch_clip(args.clip)
    except dispatch.DispatchError as e:
        raise SystemExit(str(e))
    print("dispatched %s run_id=%s log=%s" % (args.clip, run_id, log_path))


# ---------------------------------------------------------------------------
# v2: recipe / render commands
# ---------------------------------------------------------------------------

def cmd_recipe(args):
    import os
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    path = paths.edit_file(args.clip)
    if not os.path.isfile(path):
        if not args.create:
            raise SystemExit("no recipe yet for %s (use --create)" % args.clip)
        spec, _created = store.create_rough_cut_recipe(args.clip)
        if spec is None:
            raise SystemExit("no approved proposal found for clip %s; cannot create recipe" % args.clip)
    spec = store.get_recipe(args.clip)
    try:
        from studio_core import house_plan
        errors = house_plan.validate(spec)
    except ImportError:
        errors = []
    if errors:
        print(path)
        print("INVALID:")
        for e in errors:
            print("  - %s" % e)
        raise SystemExit(1)
    print(path)


def cmd_render(args):
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    addresses = [x.strip() for x in args.addresses.split(",")] if args.addresses else None
    try:
        version = jobs.run_render_sync(args.clip, note=args.note, addresses=addresses)
    except jobs.RenderError as e:
        raise SystemExit(str(e))
    print("added %s to %s" % (version["label"], args.clip))
    _print_json(version)


def cmd_rough_cut(args):
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    spec, _created = store.create_rough_cut_recipe(args.clip, overwrite=True)
    if spec is None:
        raise SystemExit("no approved proposal found for clip %s" % args.clip)
    print(paths.edit_file(args.clip))


def cmd_still(args):
    if not store.clip_exists(args.clip):
        raise SystemExit("unknown clip %s" % args.clip)
    try:
        target = jobs.still_jpg(args.clip, args.t, width=args.width)
    except jobs.RenderError as e:
        raise SystemExit(str(e))
    import shutil
    shutil.copyfile(target, args.out)
    print(args.out)


# ---------------------------------------------------------------------------
# recording commands
# ---------------------------------------------------------------------------

def cmd_add_recording(args):
    import os
    info = media.probe(args.file) if os.path.isfile(args.file) else {}
    rec = store.create_recording(
        title=args.title, file=args.file, id=args.id, transcript=args.transcript,
        batch=args.batch, date=args.date, notes=args.notes or "", probe=info)
    print("created %s" % rec["id"])
    _print_json(rec)


def cmd_recordings(args):
    recs = store.list_recordings()
    if not recs:
        print("(no recordings)")
        return
    for r in sorted(recs, key=lambda r: r.get("updated", ""), reverse=True):
        counts = {}
        for p in r.get("proposals", []):
            counts[p["status"]] = counts.get(p["status"], 0) + 1
        print("%-32s %-10s agent=%-8s proposals=%s  %s" % (
            r["id"], r.get("status"), r.get("agent", {}).get("state"), counts, r.get("title", "")))


def cmd_proposals(args):
    rec = store.get_recording(args.rec)
    if rec is None:
        raise SystemExit("unknown recording %s" % args.rec)
    proposals = rec.get("proposals", [])
    if args.json:
        _print_json(proposals)
        return
    if not proposals:
        print("(no proposals)")
    for p in proposals:
        ranges = ", ".join("%s-%s" % (_fmt_mss(a), _fmt_mss(b)) for a, b in p.get("ranges", []))
        print("%-4s [%-13s] score=%-5s %s (%s)" % (
            p["id"], p["status"], p.get("score"), p.get("title"), ranges))


def cmd_propose(args):
    if args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            items = json.load(f)
        created = []
        for item in items:
            _, proposal = store.add_proposal(
                args.rec, item["title"], item["ranges"], hook=item.get("hook", ""),
                summary=item.get("summary", ""), score=item.get("score"),
                transcript=item.get("transcript", ""))
            created.append(proposal)
        _print_json(created)
        return
    if not args.title or not args.ranges:
        raise SystemExit("--title and --ranges are required (or use --json-file)")
    ranges = _parse_ranges(args.ranges)
    _, proposal = store.add_proposal(
        args.rec, args.title, ranges, hook=args.hook or "", summary=args.summary or "",
        score=args.score, transcript=args.transcript or "")
    _print_json(proposal)


def cmd_update_proposal(args):
    patch = {}
    if args.title is not None:
        patch["title"] = args.title
    if args.summary is not None:
        patch["summary"] = args.summary
    if args.hook is not None:
        patch["hook"] = args.hook
    if args.score is not None:
        patch["score"] = args.score
    if args.ranges is not None:
        patch["ranges"] = _parse_ranges(args.ranges)
    addresses = [x.strip() for x in args.addresses.split(",")] if args.addresses else None
    rec, proposal = store.update_proposal(args.rec, args.pid, patch, addresses=addresses)
    if rec is None or proposal is None:
        raise SystemExit("unknown recording or proposal")
    _print_json(proposal)


def cmd_proposals_ready(args):
    addresses = [x.strip() for x in args.addresses.split(",")] if args.addresses else None
    rec = store.proposals_ready(args.rec, addresses=addresses)
    if rec is None:
        raise SystemExit("unknown recording %s" % args.rec)
    print("%s ready for review (%d proposals)" % (args.rec, len(rec.get("proposals", []))))


def cmd_brief_rec(args):
    rec = store.get_recording(args.rec)
    if rec is None:
        raise SystemExit("unknown recording %s" % args.rec)
    print(dispatch.recording_brief(rec))


def cmd_claim_rec(args):
    rec = store.claim_recording(args.rec)
    if rec is None:
        raise SystemExit("unknown recording %s" % args.rec)
    print("claimed %s" % args.rec)


def cmd_dispatch_rec(args):
    try:
        run_id, log_path = dispatch.dispatch_recording(args.rec)
    except dispatch.DispatchError as e:
        raise SystemExit(str(e))
    print("dispatched %s run_id=%s log=%s" % (args.rec, run_id, log_path))


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="studio.py", description="Shortform Studio CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("serve", help="run the local web server")
    sp.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5055)))  # PORT: assigned by the preview launcher
    sp.add_argument("--open", action="store_true")
    sp.set_defaults(func=cmd_serve)

    sp = sub.add_parser("list", help="list clips")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("pending", help="queued/working clips + recordings with sent notes")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_pending)

    sp = sub.add_parser("brief", help="print the editor brief for a clip")
    sp.add_argument("clip")
    sp.set_defaults(func=cmd_brief)

    sp = sub.add_parser("claim", help="editor claims a clip")
    sp.add_argument("clip")
    sp.add_argument("--message")
    sp.set_defaults(func=cmd_claim)

    sp = sub.add_parser("add-clip", help="create a clip")
    sp.add_argument("--title", required=True)
    sp.add_argument("--id")
    sp.add_argument("--batch")
    sp.add_argument("--workdir")
    sp.add_argument("--brief")
    sp.add_argument("--brief-file")
    sp.add_argument("--source")
    sp.set_defaults(func=cmd_add_clip)

    sp = sub.add_parser("add-version", help="register a new render")
    sp.add_argument("clip")
    sp.add_argument("file")
    sp.add_argument("--notes")
    sp.add_argument("--notes-file")
    sp.add_argument("--addresses", help="comma separated comment ids")
    sp.add_argument("--label")
    sp.add_argument("--kind", default="render", choices=["original", "render", "variant"])
    sp.set_defaults(func=cmd_add_version)

    sp = sub.add_parser("comment", help="add a note")
    sp.add_argument("clip")
    sp.add_argument("text")
    sp.add_argument("--t", type=float)
    sp.add_argument("--version", type=int)
    sp.add_argument("--author", default="director", choices=["director", "editor"])
    sp.add_argument("--status", default="draft", choices=["draft", "sent"])
    sp.set_defaults(func=cmd_comment)

    sp = sub.add_parser("reply", help="editor replies to a note")
    sp.add_argument("clip")
    sp.add_argument("comment_id")
    sp.add_argument("text")
    sp.set_defaults(func=cmd_reply)

    sp = sub.add_parser("status", help="set clip status")
    sp.add_argument("clip")
    sp.add_argument("status")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("taste", help="show/add/propose taste rules")
    sp.add_argument("--add")
    sp.add_argument("--propose")
    sp.set_defaults(func=cmd_taste)

    sp = sub.add_parser("dispatch", help="start a headless editor run for a clip")
    sp.add_argument("clip")
    sp.set_defaults(func=cmd_dispatch)

    sp = sub.add_parser("recipe", help="print (and validate) a clip's recipe path")
    sp.add_argument("clip")
    sp.add_argument("--create", action="store_true", help="create from the approved proposal if missing")
    sp.set_defaults(func=cmd_recipe)

    sp = sub.add_parser("render", help="render a clip's current recipe (registers the new version)")
    sp.add_argument("clip")
    sp.add_argument("--note")
    sp.add_argument("--addresses", help="comma separated comment ids")
    sp.add_argument("--wait", action="store_true", help="(CLI renders synchronously by default anyway)")
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("rough-cut", help="(re)build the rough-cut recipe from the approved proposal")
    sp.add_argument("clip")
    sp.set_defaults(func=cmd_rough_cut)

    sp = sub.add_parser("still", help="render a draft still of the current recipe")
    sp.add_argument("clip")
    sp.add_argument("--t", type=float, required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--width", type=int, default=540)
    sp.set_defaults(func=cmd_still)

    sp = sub.add_parser("add-recording", help="register a class recording")
    sp.add_argument("--title", required=True)
    sp.add_argument("--file", required=True)
    sp.add_argument("--transcript")
    sp.add_argument("--batch")
    sp.add_argument("--date")
    sp.add_argument("--id")
    sp.add_argument("--notes")
    sp.set_defaults(func=cmd_add_recording)

    sp = sub.add_parser("recordings", help="list recordings")
    sp.set_defaults(func=cmd_recordings)

    sp = sub.add_parser("proposals", help="list a recording's proposals")
    sp.add_argument("rec")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_proposals)

    sp = sub.add_parser("propose", help="register a clip-bank proposal")
    sp.add_argument("rec")
    sp.add_argument("--title")
    sp.add_argument("--ranges", help="start-end,start-end (source seconds)")
    sp.add_argument("--hook")
    sp.add_argument("--summary")
    sp.add_argument("--score", type=float)
    sp.add_argument("--transcript")
    sp.add_argument("--json-file", help="[{title, ranges, hook, summary, score, transcript}]")
    sp.set_defaults(func=cmd_propose)

    sp = sub.add_parser("update-proposal", help="edit a proposal")
    sp.add_argument("rec")
    sp.add_argument("pid")
    sp.add_argument("--ranges")
    sp.add_argument("--title")
    sp.add_argument("--hook")
    sp.add_argument("--summary")
    sp.add_argument("--score", type=float)
    sp.add_argument("--addresses")
    sp.set_defaults(func=cmd_update_proposal)

    sp = sub.add_parser("proposals-ready", help="editor finished a proposal pass")
    sp.add_argument("rec")
    sp.add_argument("--addresses")
    sp.set_defaults(func=cmd_proposals_ready)

    sp = sub.add_parser("brief-rec", help="print the editor prompt for proposal work")
    sp.add_argument("rec")
    sp.set_defaults(func=cmd_brief_rec)

    sp = sub.add_parser("claim-rec", help="editor claims a recording")
    sp.add_argument("rec")
    sp.set_defaults(func=cmd_claim_rec)

    sp = sub.add_parser("dispatch-rec", help="start a headless editor run for a recording")
    sp.add_argument("rec")
    sp.set_defaults(func=cmd_dispatch_rec)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
