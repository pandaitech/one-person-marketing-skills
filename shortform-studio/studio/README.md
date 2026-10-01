# Shortform Studio

A local web app for directing many AI video edits at once. The director (taste, decisions) reviews; Claude
(the editor, one run per clip, many in parallel) cuts, renders and revises.

```
Full class recording ─▶ Clip bank (Claude proposes, you pick/adjust cuts) ─▶ Clips (Claude renders v1)
                                                                            ─▶ Review loop: notes ▶ vN+1 ▶ … ▶ Approve ▶ Publish
```

Design and API: [docs/DESIGN.md](docs/DESIGN.md) (review loop) and [docs/STUDIO-V2.md](docs/STUDIO-V2.md) (the recipe).

## The recipe (v2)

Every clip is built by the same 7 steps, shown left to right in its **Edit** tab:
① Source → ② Cut → ③ Captions → ④ Text → ⑤ Moments → ⑥ Sound → ⑦ Render.

- **Cut** is edited like a document: click a word to jump there, select words and press ✂ to cut them (the cut
  snaps to the nearest silence), ↺ to bring them back. Only the part you touch changes.
- **Captions / Text / Moments / Sound**: change wording, timing, the highlighted word, pop-up images, the year
  counter, the manuscript page, zoom-ins, SFX volume. **Draft** shows a still of your change instantly.
- **Render** (≈1 min) makes the next version and writes "what changed" for you. It then appears in Review.
- Each step has **Ask Claude…** for creative changes; Claude edits the same recipe.
- Approving an idea builds a **rough cut** automatically (cuts + captions + title) and renders v1.

The recipe lives at `DATA_DIR/edits/<clip>.json`; every render snapshots it (`edits/<clip>/v<N>.json`).
`python3 studio/studio.py render <clip> --note "…"` renders from the CLI. Rendering needs `uv` (it runs the
renderer with Pillow + numpy).

## Run it

```bash
python3 studio/studio.py serve --open          # http://127.0.0.1:5055
```

Python 3.9+ standard library, `ffmpeg`/`ffprobe` on PATH. No install, no build. Data lives outside Git in
`./shortform-studio-data/` relative to where you run `studio.py` (override with `STUDIO_DATA_DIR`).

## The director loop (you)

1. **Recordings** — open a class recording. Claude's clip proposals sit on the right (title, hook, score, exact
   source ranges). Press **P** to preview a cut (plays the ranges back to back), fix start/end from the playhead
   or by dragging the range handles, then **A** approve (becomes a clip) or **R** reject. Select transcript text
   to make your own clip. Notes you leave (pinned to source time) go to Claude with **Send notes**.
2. **Board** — every clip by state: *Your review · Queued · Editing · Approved · Published*. The wall view shows
   all posters at once.
3. **Review** — the triage loop. Watch, press **N** to drop a note at the playhead, **⌘⏎** to send the notes
   (the next clip loads), or **⇧A** to approve. Notes stay pinned to their version; when Claude ships a new
   version it lists which notes it addressed — confirm ✓ or reopen ↺. **G** compares two versions side by side.
4. **Taste** — rules you keep repeating. Every Claude run reads them. Claude can propose new ones; you accept.

Press **?** anywhere for shortcuts.

## The editor loop (Claude)

Two ways to start work:

- **In chat:** "process the studio queue". Claude runs `python3 studio/studio.py pending`, then handles each
  queued clip or recording, ideally one subagent per item in parallel.
- **Headless dispatch:** Settings → *Auto-dispatch* (or the Retry/Dispatch button). Sending notes starts
  `claude -p <brief>` for that clip; its log streams into the Log tab. The command is configurable. The `claude`
  CLI must be logged in (`claude` → `/login` in a terminal); a failed run shows its log and puts the clip back
  in Queued.
- **First cuts:** an approved proposal becomes a clip with no version. Its brief tells the editor to start from
  the *house-style template* (Settings; default: the approved V02 project's `render.py` + `assets/`).

For one item the editor always:

```bash
python3 studio/studio.py brief <clip>                 # the full job: notes with timestamps, taste rules, files
python3 studio/studio.py claim <clip>
#   …edit in the clip's workdir, render to a NEW file (…-v<N+1>.mp4), verify…
python3 studio/studio.py add-version <clip> /abs/new.mp4 --notes "what changed" --addresses c12,c13
python3 studio/studio.py reply <clip> c14 "Kept this because …"      # anything not done, with the reason
python3 studio/studio.py taste --propose "Rule inferred from repeated notes"
```

Recordings: `brief-rec`, `claim-rec`, `propose` (or `propose --json-file`), `update-proposal`,
`proposals-ready`. Follow the skill's `SKILL.md` for the editorial rules and verification.

Never overwrite a version file, never mark notes addressed that weren't, and verify renders (decode, frames at
the changed moments, re-transcribe changed joins) before `add-version`.

## Add material

```bash
python3 studio/studio.py add-recording --title "…" --file /abs/class.mp4 --transcript /abs/word-timeline.json --batch …
python3 studio/studio.py add-clip --title "…" --batch … --workdir /abs/project --brief "…"
python3 studio/studio.py add-version <clip> /abs/original.mp4 --kind original --notes "cut before the studio"
```

## Tests

```bash
cd studio && python3 -m unittest discover -s tests -v
```
