# Shortform Studio — design

A local web app where the **director** (Faiq: taste, decisions) reviews many videos at once and the
**editor** (Claude, one agent run per clip, many in parallel) keeps improving them from time-stamped notes.

Think Frame.io's review loop, re-shaped for one director managing ~20 AI editors:

- **Triage, not browsing.** The main screen is a review queue: watch → note → send / approve → next clip
  auto-loads. One keystroke per decision.
- **Notes are pinned to a moment of a specific version.** The editor gets exact timestamps; the director sees
  every note's life: draft → sent → addressed in vN → resolved.
- **Versions are a stack, never overwritten.** Every render is a new file. Compare any two versions side by side,
  synced.
- **The editor explains itself.** Each version carries a short changelog and the list of notes it addresses,
  so review starts from "what changed".
- **Taste book.** Rules the director keeps repeating ("speaker first, sparse literal text", "no invented end
  cards") live in one place and are injected into every editor run. Editors may *propose* rules; the director
  accepts or rejects.
- **Board / wall for the 20-editor overview.** Columns by state (Your review · Queued · Editing · Approved ·
  Published) or a wall of 9:16 posters with state chips.
- **Headless dispatch (optional).** "Send notes" can immediately start a `claude -p` run for that clip, which
  claims the job, edits, renders a new version, registers it and replies. Off by default; toggle in Settings.
  Without it, the director tells Claude in chat "process the studio queue".

Local only: binds 127.0.0.1, stdlib Python (3.9+) server, vanilla-JS frontend, no build step, no network.

## Layout

```
studio/
  studio.py              CLI entry: serve | list | pending | brief | claim | add-clip | add-version |
                         comment | reply | status | taste | dispatch
  studio_core/
    __init__.py
    paths.py             repo root, workspace root, DATA_DIR resolution
    store.py             JSON store: clips, batches, taste, settings, events (atomic writes + fcntl lock)
    media.py             ffprobe, poster/thumb, filmstrip sprite, waveform (cached)
    server.py            ThreadingHTTPServer: REST API, static web/, media with HTTP Range
    dispatch.py          build editor brief/prompt, start/track headless agent runs
  web/
    index.html  styles.css
    js/app.js js/api.js js/board.js js/review.js js/player.js js/taste.js js/activity.js js/settings.js js/util.js
  tests/                 unittest: store transitions, API, range requests
  docs/DESIGN.md         this file
  README.md              run it, the director loop, the editor (agent) loop
```

## Data

`DATA_DIR` = `$STUDIO_DATA_DIR`, or `./shortform-studio-data` relative to the current working directory when Studio was started. Never inside Git.

```
DATA_DIR/
  clips/<clip_id>.json     one file per clip (parallel editors never contend on one file)
  batches.json             [{id, name, note, created}]
  taste.json               {"rules": [Rule]}
  settings.json            Settings
  events.jsonl             append-only activity feed
  cache/<clip>/<n>/        poster.jpg, t-<ms>.jpg, filmstrip.jpg, waveform.png, probe.json
  logs/<clip>-<ts>.log     dispatch run output
```

All writes: write temp file in same dir + `os.replace`; guard read-modify-write of a clip with an exclusive
`fcntl.flock` on `clips/<clip_id>.lock`. Timestamps: ISO-8601 UTC with `Z`.

### Clip

```json
{
  "id": "v02-dua-masalah",                       // slug [a-z0-9-]
  "title": "V02 · 2 masalah buat Meta Ads sorang-sorang",
  "batch": "meta-ads-260827",
  "brief": "markdown: what the clip is, its point, constraints",
  "source": "free text: source recording + ranges",
  "workdir": "/abs/path/to/project",           // where the editor works (render.py etc.)
  "status": "review",                           // drafting | queued | working | review | approved | published | archived
  "approved_version": null,
  "priority": 0,
  "tags": [],
  "created": "...Z", "updated": "...Z",
  "director_seen_version": 5,                   // latest version n the director has opened
  "versions": [Version],
  "comments": [Comment],
  "agent": {"state": "idle", "pid": null, "run_id": null, "started": null, "ended": null,
            "log": null, "message": ""}      // state: idle | queued | working | error
}
```

### Version

```json
{"n": 5, "label": "v5", "kind": "render",      // kind: original | render | variant
 "file": "/abs/…/V02-dua-masalah-v5.mp4", "created": "...Z",
 "notes": "markdown changelog written by the editor",
 "addresses": ["c12", "c13"],
 "duration": 95.5, "width": 1080, "height": 1920, "size": 23667696}
```

`n` starts at 0 when the first version is kind `original` (the pre-studio cut), otherwise 1. Always
`max(n)+1` on add. Probe fields are filled by `media.probe()` when the version is added.

### Comment

```json
{"id": "c12", "version": 4, "t": 36.2, "t_end": null,   // t null = general note for the whole version
 "text": "remove the treat ads as salespeople part", "author": "director",   // director | editor
 "parent": null,                                           // reply thread: parent comment id
 "status": "sent",                                         // draft | sent | addressed | resolved | wontfix
 "addressed_in": null, "created": "...Z", "updated": "...Z"}
```

Ids: `c<N>` unique within the clip (N = max+1). Editor replies have `author: editor`, `parent`, status `resolved`
(replies are not work items).

### Rule (taste book)

```json
{"id": "r3", "text": "Speaker first. Most of the clip is just the speaker + captions.",
 "status": "active",        // active | proposed | retired
 "author": "director",      // director | editor (editor-proposed rules start as proposed)
 "source": {"clip": "v01-workflow-dulu", "comment": "c4"}, "created": "...Z"}
```

### Settings

```json
{"director_name": "Faiq", "editor_name": "Claude",
 "auto_dispatch": false,
 "dispatch_command": ["claude", "-p", "{prompt}", "--permission-mode", "acceptEdits",
                      "--allowedTools", "Bash Read Edit Write Glob Grep", "--add-dir", "{workdir}",
                      "--add-dir", "{studio_dir}"],
 "media_roots": ["<workspace>/agents-output", "~/Downloads"]}
```

`{prompt}` = the text of `brief(clip)`; `{workdir}` = clip.workdir; `{studio_dir}` = the studio folder.
Media is only served for version files under a media root.

## State machine

| Action | Who | Effect |
| --- | --- | --- |
| add note | director | comment `draft` on the version being watched |
| send notes | director | all director `draft` → `sent`; clip `queued`; agent `queued`; if `auto_dispatch` → dispatch |
| claim | editor | clip `working`; agent `working`, started=now |
| add-version (+addresses) | editor | new version; listed comments `addressed`, `addressed_in=n`; clip `review`; agent `idle` |
| reply | editor | reply comment under a note (explain, disagree, ask) |
| resolve / reopen | director | `addressed`→`resolved`; any → `draft` (reopen, will be resent) |
| wontfix | director | comment `wontfix` |
| approve | director | clip `approved`, `approved_version=n` |
| unapprove | director | clip `review` |
| publish / archive | director | clip `published` / `archived` |
| dispatch exits without a new version | system | agent `error`, message = last log lines; clip back to `queued` |

"Your review" = status `review` (new versions first), plus any clip with director drafts not yet sent.

## HTTP API (JSON, 127.0.0.1:5055)

| Method | Path | Body / query | Returns |
| --- | --- | --- | --- |
| GET | `/api/state` | | `{now, settings, batches, taste, clips:[ClipSummary], counts:{review,queued,working,approved,published,drafts}}` |
| GET | `/api/clips/<id>` | | full Clip + for each version `media_url`, `poster_url`, `filmstrip_url`, `waveform_url` |
| POST | `/api/clips` | `{id?, title, batch?, brief?, source?, workdir?}` | Clip |
| PATCH | `/api/clips/<id>` | any of `title, brief, source, workdir, batch, priority, tags, status` | Clip |
| POST | `/api/clips/<id>/comments` | `{version, t?, t_end?, text, author?, parent?}` | Comment |
| PATCH | `/api/clips/<id>/comments/<cid>` | `{text?, status?, t?}` | Comment |
| DELETE | `/api/clips/<id>/comments/<cid>` | | `{ok}` (drafts only unless `?force=1`) |
| POST | `/api/clips/<id>/send` | | Clip (and `dispatched: true/false`) |
| POST | `/api/clips/<id>/approve` | `{version}` | Clip |
| POST | `/api/clips/<id>/unapprove` | | Clip |
| POST | `/api/clips/<id>/seen` | `{version}` | `{ok}` |
| POST | `/api/clips/<id>/versions` | `{file, notes?, addresses?, label?, kind?}` | Version |
| POST | `/api/clips/<id>/claim` | `{message?}` | Clip |
| POST | `/api/clips/<id>/dispatch` | | `{ok, run_id, log}` |
| GET | `/api/clips/<id>/log` | `?lines=200` | `{text, running}` |
| GET | `/api/clips/<id>/brief` | | `{text}` (the editor prompt) |
| GET | `/api/taste` | | `{rules}` |
| POST | `/api/taste` | `{text, author?, source?}` | Rule |
| PATCH | `/api/taste/<rid>` | `{text?, status?}` | Rule |
| DELETE | `/api/taste/<rid>` | | `{ok}` |
| GET | `/api/events` | `?limit=100&clip=<id>` | `{events:[{ts, clip, actor, type, text}]}` newest first |
| PATCH | `/api/settings` | partial Settings | Settings |
| GET | `/media/<id>/<n>` | HTTP Range | the video bytes (`video/mp4`, 206 partial) |
| GET | `/thumb/<id>/<n>.jpg` | `?t=seconds` (default: poster at 15% of duration) | jpeg 360px wide |
| GET | `/filmstrip/<id>/<n>.jpg` | | jpeg sprite: 60 tiles in one row, each 72×128 |
| GET | `/waveform/<id>/<n>.png` | | png 1600×96, transparent bg, lime wave |
| GET | `/` , `/static/...` | | web/ files |

ClipSummary = `{id, title, batch, status, agent, approved_version, latest_version, version_count, duration,
poster_url, updated, open:{draft, sent, addressed}, new_version: latest_version > director_seen_version,
last_event}`.

Errors: `{"error": "message"}` with 4xx. Unknown clip → 404.

## CLI (for the editor agent and the director)

```
python3 studio/studio.py serve [--port 5055] [--open]
python3 studio/studio.py list
python3 studio/studio.py pending [--json]          # queued/working clips + sent notes + taste rules
python3 studio/studio.py brief <clip>              # full editor prompt (what dispatch sends)
python3 studio/studio.py claim <clip> [--message "…"]
python3 studio/studio.py add-clip --title … [--id …] [--batch …] [--workdir …] [--brief …|--brief-file …] [--source …]
python3 studio/studio.py add-version <clip> <file> [--notes "…"|--notes-file f] [--addresses c1,c2] [--label …] [--kind render]
python3 studio/studio.py comment <clip> "text" [--t 12.3] [--version n] [--author director|editor] [--status draft|sent]
python3 studio/studio.py reply <clip> <comment_id> "text"
python3 studio/studio.py status <clip> <status>
python3 studio/studio.py taste [--add "rule"] [--propose "rule"]
python3 studio/studio.py dispatch <clip>
```

## Editor brief (the dispatch prompt)

Generated per clip: who you are (editor for the director), the clip (title, brief, source, workdir, latest
version file, version history with one-line notes), the **sent notes** with version + mm:ss.s + text, the
**active taste rules**, the addressed-but-unresolved notes (context), and the exact procedure:

1. `claim` the clip. 2. Read the workdir README / render script. 3. Apply every sent note; keep everything else
   unchanged. 4. Render to a **new** file (`…-v<N+1>.mp4`), never overwrite. 5. Verify: full decode, frames at
   the changed moments, re-transcribe changed joins. 6. `add-version` with a short changelog (what changed per
   note, anything left out and why) and `--addresses` for the notes you handled. 7. `reply` to any note you
   could not or chose not to do, explaining why. 8. Optionally `taste --propose` a rule you inferred.

## Frontend

Dark, video-first, dense. Accent = the theme accent colour. Status colours: review lime, queued amber, working
blue (pulsing), approved green, published grey, error red.

- **Top bar:** "Shortform Studio" · Board · Review (count) · Taste · Activity · Settings · editor status
  ("Claude: 2 editing, 1 queued").
- **Board** (`#/`): batch filter + search; toggle Columns / Wall. Columns: Your review · Queued · Editing ·
  Approved · Published. Card: 9:16 poster, title, `v5 · 1:35`, badges (NEW version, N drafts, N addressed to
  confirm, error), relative time. Wall: grid of posters, hover plays muted preview. "Start review" button.
- **Review** (`#/clip/<id>?v=<n>`, `#/review` = first in queue):
  - Left: 9:16 player in a phone-shaped frame; custom controls (play, time, speed 1/1.5/2×, frame step, mute);
    timeline = filmstrip + waveform + note markers (colour by status) + playhead; hover shows thumb. Version
    tabs (v0 original … vN, NEW dot); Compare toggle → second player, synced play/pause/seek.
  - Right: title, status pill, tabs **Notes · Changes · Brief · Log**.
    Notes: composer ("at 00:12.4 on v5", toggle whole-video), Enter adds, Shift+Enter newline, typing pauses
    the video. Groups: Drafts (not sent) · Sent · Addressed — confirm (✓ resolve / ↺ reopen) · Resolved.
    Timestamp chips seek (switching version if needed). Editor replies threaded.
    Changes: each version's changelog, newest first, with the notes it addressed. Brief: editable brief, source,
    workdir, file paths (copy). Log: dispatch log tail.
  - Bottom bar: **Send N notes** (⌘⏎) · **Approve vN** (⇧A) · Next clip (⇧N). After send/approve, auto-advance to
    the next clip in the review queue with a toast.
  - Keys: Space play · K pause · J/L ∓5s · ←/→ ∓1s · , . frame · N note at playhead · [ ] version · G compare ·
    Esc blur · ? help.
- **Taste** (`#/taste`): active rules (edit/retire), proposed rules (accept/reject), add rule.
- **Activity** (`#/activity`): feed. **Settings** (`#/settings`): names, auto-dispatch, dispatch command, roots.

Polling: `/api/state` every 3 s; open clip every 2 s while its agent is queued/working. Never re-create the
`<video>` element on refresh (it would reset playback); patch panels only.

---

# Part 2 — from full class recording to clips

The studio covers the whole pipeline, not only the review loop:

```
Recording (full class video + word transcript)
   └─ Clip bank: editor proposes candidates (title, hook, source ranges, why)      ← director triages
        └─ approved proposal → Clip (status queued, brief = proposal)              ← editor produces v1
             └─ review loop (notes → versions) → approved → published
```

## Recording data

`DATA_DIR/recordings/<rec_id>.json` (lock file `recordings/<rec_id>.lock`):

```json
{
  "id": "meta-ads-ai-agent-260827",
  "title": "Meta Ads dengan AI Agent — kelas 27 Aug",
  "batch": "meta-ads-260827",
  "date": "2026-08-27",
  "file": "/abs/…/source-trimmed.mp4",
  "transcript": "/abs/…/word-timeline.json",     // {segments:[{start,end,text}], word_segments:[{word,start,end}]}
  "duration": 6283.5, "width": 1280, "height": 720,
  "notes": "markdown: context for the editor (speaker tile position, audience, goals)",
  "status": "proposed",           // new | queued | working | proposed | done | archived
  "agent": {…same shape as Clip.agent…},
  "created": "...Z", "updated": "...Z",
  "proposals": [Proposal],
  "comments": [Comment]           // same model as clip comments; t/t_end are SOURCE seconds;
                                   // extra optional field "proposal": "<pid>" (null = note about the whole bank)
}
```

### Proposal

```json
{"id": "p4", "title": "2 masalah buat Meta Ads sorang-sorang",
 "hook": "Tapi biasanya kita akan ada 2 masalah…",
 "ranges": [[674.14, 693.64], [693.98, 731.36]],       // source seconds, in play order
 "summary": "why this is a strong standalone clip; setup → point → payoff",
 "transcript": "plain text of the kept speech (optional; UI derives it from words if absent)",
 "score": 8.5,                                         // editor's 0–10 confidence
 "status": "proposed",                                 // proposed | approved | rejected | needs_changes
 "clip_id": null,                                      // set when approved → clip created
 "author": "editor", "created": "...Z", "updated": "...Z"}
```

Duration = sum of range lengths. Ids `p<N>`.

### Recording state machine

| Action | Who | Effect |
| --- | --- | --- |
| add recording | director/editor | status `new` |
| "Find clips" / send notes | director | director draft comments → `sent`; recording `queued`; agent queued (+auto-dispatch) |
| claim | editor | recording `working` |
| propose / update proposals | editor | add or edit proposals; notes it handled → `addressed` |
| done proposing (`proposals-ready`) | editor | recording `proposed`; agent idle |
| approve proposal | director | proposal `approved`; creates Clip {id from title slug (unique), title, batch, brief = hook + summary + ranges + transcript, source = "<file> ranges …", workdir = `$STUDIO_DATA_DIR/renders/<clip_id>`, status `queued`}; if auto_dispatch → dispatch clip |
| reject proposal | director | proposal `rejected` |
| edit ranges/title | director | proposal updated in place (director's cut decision) |
| note on proposal | director | comment with `proposal: pid`, `t` = source time; `needs_changes` when sent |

## Recording API

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/api/recordings` | | `{recordings:[RecSummary]}` |
| POST | `/api/recordings` | `{id?, title, file, transcript?, batch?, date?, notes?}` | Recording |
| GET | `/api/recordings/<id>` | | Recording (+ `media_url`, `poster_url`, `waveform_url`) |
| PATCH | `/api/recordings/<id>` | `title, notes, batch, date, status` | Recording |
| GET | `/api/recordings/<id>/transcript` | | `{segments:[[start,end,text]], words:[[word,start,end]]}` (compact arrays) |
| POST | `/api/recordings/<id>/proposals` | `{title, ranges, hook?, summary?, score?, transcript?, author?}` | Proposal |
| PATCH | `/api/recordings/<id>/proposals/<pid>` | `title, ranges, hook, summary, score, status` | Proposal |
| POST | `/api/recordings/<id>/proposals/<pid>/approve` | | `{proposal, clip}` |
| POST | `/api/recordings/<id>/comments` | `{t?, t_end?, text, proposal?, author?, parent?}` | Comment |
| PATCH/DELETE | `/api/recordings/<id>/comments/<cid>` | | as clips |
| POST | `/api/recordings/<id>/send` | | Recording |
| POST | `/api/recordings/<id>/claim` | | Recording |
| POST | `/api/recordings/<id>/dispatch` | | `{ok, run_id, log}` |
| GET | `/api/recordings/<id>/log` | | `{text, running}` |
| GET | `/api/recordings/<id>/brief` | | `{text}` |
| GET | `/media/rec/<id>` | Range | video |
| GET | `/thumb/rec/<id>.jpg?t=` | | jpeg 480px wide |
| GET | `/waveform/rec/<id>.png` | | png 3000×80 of the whole recording |

RecSummary = `{id, title, batch, date, duration, status, agent, poster_url, proposals:{proposed, approved,
rejected, needs_changes}, open:{draft, sent}, updated}`. `/api/state` also includes `recordings:[RecSummary]`
and `counts.proposals` (= proposed proposals awaiting the director).

## Recording CLI

```
studio.py add-recording --title … --file … [--transcript …] [--batch …] [--date …] [--id …] [--notes …]
studio.py recordings                                   # list
studio.py proposals <rec> [--json]
studio.py propose <rec> --title … --ranges "674.14-693.64,693.98-731.36" [--hook …] [--summary …] [--score 8]
studio.py propose <rec> --json-file proposals.json     # [{title, ranges, hook, summary, score, transcript}]
studio.py update-proposal <rec> <pid> [--ranges …] [--title …] [--summary …] [--addresses c1,c2]
studio.py proposals-ready <rec> [--addresses c1,c2]    # editor finished a proposal pass
studio.py brief-rec <rec>                              # editor prompt for proposal work
studio.py claim-rec <rec>
studio.py dispatch-rec <rec>
```
`pending` lists queued/working recordings too (with their sent notes).

The recording brief tells the editor to follow the skill's `SKILL.md` Part 2 steps 2 (clip bank:
complete ideas, 3–5 hook candidates, cold-viewer clarity, merge/split, context audit) using the transcript file,
to check word boundaries against the waveform for ranges, and to register proposals with the CLI, then run
`proposals-ready`. Existing proposals and director notes (with their source timestamps) are included.

## Recording UI

- Nav gains **Recordings** (first item; the pipeline starts here).
- **Recordings list** (`#/recordings`): cards (poster, title, date, duration, proposal counts by status,
  status/agent chip) + "Find clips" button (sends a general note "Propose clips" if none drafted).
- **Recording view** (`#/rec/<id>`):
  - Left (~58%): 16:9 player; below it the **recording timeline**: waveform strip of the whole class with proposal
    ranges as coloured bands (status colours), playhead, zoomable? (not required) — click to seek, hover a band to
    see its title. Under it the **transcript**: segments as clickable paragraphs with timestamps, the current
    segment highlighted and auto-scrolled (toggle "follow"), search box (highlights matches, Enter jumps),
    words inside the selected proposal's ranges tinted lime. Select transcript text → floating
    "＋ New clip from selection" (creates a director proposal with that range) and "Note here".
  - Right (~42%): **Clip bank**: filter chips (Proposed · Approved · Rejected · All), sort (score/time).
    Proposal card: title, score, total duration, hook (italic), ranges as chips `11:14.1–11:33.6` (click → seek),
    summary (collapsible), status. Selected card expands: **▶ Preview cut** (plays ranges back-to-back, skipping
    the gaps), editable title, range editor rows (start/end inputs in m:ss.s, "⤓ set start = playhead",
    "⤒ set end = playhead", ± 0.1 s nudges, add/remove range), notes thread for this proposal + composer
    (timestamp = playhead in source time), actions **Approve → make clip** (A), **Reject** (R),
    **Needs changes** (sends note). Next/prev proposal J/K… (use ↑/↓ for proposals, since J/K/L are player keys).
  - Bottom bar: **Send N notes to editor** · **Find more clips** (general note) · status of the editor on this
    recording.
- After approving, the new clip appears on the Board in **Queued** (or Editing if dispatched); link "Open clip".

## Frontend module contract (parallel builders must follow exactly)

- Plain ES modules, no dependencies, no build. `web/index.html` loads `styles.css`, `recordings.css`, and
  `js/app.js` as `type="module"`.
- `js/api.js`
  - `export async function get(path)`, `post(path, body)`, `patch(path, body)`, `del(path)` → parsed JSON;
    on non-2xx throw `Error(json.error || statusText)`.
- `js/util.js`
  - `export function h(tag, attrs = {}, ...children)` — DOM builder. attrs: `class`, `style` (string or
    object), `on<Event>` handlers (e.g. `onclick`), `dataset` object, boolean props, others via setAttribute.
    children: Node | string | number | null/false (skipped) | arrays (flattened).
  - `fmtTime(sec)` → `m:ss.s` (h:mm:ss.s when ≥ 1 h), `fmtDur(sec)` → `m:ss` (h:mm:ss ≥ 1 h),
    `parseTime(str)` → seconds (accepts `ss`, `m:ss(.s)`, `h:mm:ss(.s)`), `relTime(iso)` → "3m ago",
    `md(text)` → safe HTML (escape, then paragraphs, `- ` bullets, `**bold**`, `` `code` ``),
    `statusPill(status)` → span.pill.pill-<status>, `toast(msg, kind='ok'|'err')`, `copy(text)`,
    `debounce(fn, ms)`, `escapeHtml(s)`.
- `js/player.js`
  - `export function createPlayer(container, {src, aspect = '9/16', onTime, onPlayState})` → object with
    `video` (HTMLVideoElement), `el`, `play()`, `pause()`, `toggle()`, `seek(t)`, `time()`, `duration()`,
    `setSrc(src, keepTime = false)`, `setRate(r)`, `step(frames)`, `playRanges(ranges)` (plays [[a,b],…] in
    order, skipping gaps, stops at the end; any manual seek/pause cancels), `destroy()`.
    Renders the video + a compact control row (play/pause, time/duration, speed, mute). Timelines are separate.
- `js/app.js`
  - Router on `location.hash`: `#/` board, `#/review`, `#/clip/<id>` (query `?v=n`), `#/recordings`,
    `#/rec/<id>` (query `?p=<pid>`), `#/taste`, `#/activity`, `#/settings`.
  - `export function registerView(name, view)`; view = `{mount(el, params, query), unmount(), onState(state)}`.
    Recordings views are registered by `import './recordings.js'` and `import './recording.js'` at the top of
    app.js; those modules call `registerView('recordings', …)` / `registerView('recording', …)`.
  - Polls `/api/state` every 3 s; `export function getState()` returns the last state; calls
    `view.onState(state)` on the mounted view after each poll. `export function refresh()` forces a poll.
  - `export function navigate(hash)`.
  - Global keys: `?` help overlay, `g r` recordings, `g b` board (optional). Views add/remove their own
    `keydown` listeners in mount/unmount and must ignore keys while typing in inputs/textareas.
  - Top bar with nav + counts badges (Recordings: `counts.proposals`; Review: `counts.review`) + editor status.
- CSS: `styles.css` defines tokens on `:root` (`--bg`, `--panel`, `--panel-2`, `--border`, `--text`,
  `--muted`, `--accent`, `--amber`, `--blue`, `--green`, `--red`, `--radius`) and base components: `.btn`,
  `.btn-primary`, `.btn-ghost`, `.pill`, `.pill-<status>`, `.card`, `.tabs`/`.tab`/`.tab.active`, `.chip`,
  `.kbd`, `.toast`, `.split` (two-column layout), `.panel`, `.muted`, `.row`, `.stack`. `recordings.css` holds
  recording-view specifics only and uses those tokens.
