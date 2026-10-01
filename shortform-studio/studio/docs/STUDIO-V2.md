# Shortform Studio v2 — the Recipe

## Why

v1 made review easy, but *changing* a clip still meant writing a note and waiting for Claude to edit a bespoke
Python script. The director can't see how a clip is built, and small fixes (a typo, a headline wording, a cut
that's 0.3 s late) take a full round trip.

v2 turns every clip into a **recipe**: the same 7 steps, left to right, each with visible settings and output —
the ComfyUI idea (nodes you can tweak, re-run downstream), without the spaghetti: the order is fixed, nothing can
be wired wrong, and everything is in plain words. The director and Claude edit the **same recipe** (a JSON file).
One button renders it (~15 s) into the next version. A draft still of any moment updates instantly while editing.

```
① Source → ② Cut → ③ Captions → ④ Text → ⑤ Moments → ⑥ Sound → ⑦ Render
```

| Step | Plain meaning | Director does |
| --- | --- | --- |
| ① Source | Which class recording, which parts | read-only summary, link to the recording |
| ② Cut | What he says in this clip | read the words; strike out words to cut (Descript-style); cuts snap to silence automatically |
| ③ Captions | Subtitles | auto from the kept words; fix a typo; split/merge a line |
| ④ Text | The few big on-screen lines + title | edit wording, when it appears, which word gets the lime highlight |
| ⑤ Moments | Optional visual beats | images pop in (speaker hides), year counter, manuscript page, zoom-in |
| ⑥ Sound | SFX + loudness | auto SFX from the above; volume; mute one |
| ⑦ Render | Make the next version | see "what changed", render, it goes to Review |

Every step also has **"Ask Claude…"**: a sentence becomes a note scoped to that step; Claude edits the recipe.

New flow for a fresh clip: approve an idea → the studio builds a **rough cut recipe automatically** (the
proposal's ranges, captions, title = proposal title) and renders v1 in ~20 s, no Claude needed. Then tweak, or
ask Claude for the creative pass (text, moments).

## Simpler app shell

Nav: **Home · Ideas · Clips · Taste · ⚙**. (Recordings → "Ideas"; Board → "Clips"; Activity lives on Home.)

- **Home** (`#/`): the 3 steps as a strip (① Pick ideas → ② Review & edit → ③ Approve & publish) with live
  counts, then "What needs you" cards with one primary button each, then recent activity.
- A clip page has two modes, switched by a segmented control in its header: **Review** (`#/clip/<id>` — watch,
  notes, approve; unchanged) and **Edit** (`#/edit/<id>` — the recipe).

## The recipe (edit spec) — `DATA_DIR/edits/<clip_id>.json`

All times are **source seconds** (positions in the class recording), so text stays attached to the words when
cuts change. The renderer maps them to output time; an anchor inside a removed part clamps to the nearest kept
moment and produces a warning.

```json
{
  "schema": 1,
  "clip": "v02-dua-masalah",
  "source": {
    "file": "/abs/…/source-trimmed.mp4",
    "words": "/abs/…/word-timeline.json",
    "speaker_tile": [962, 272, 318, 178]
  },
  "cut": {
    "segments": [ {"a": 599.49, "b": 603.41, "snap": false, "mute": false} ],
    "tail": 0.6
  },
  "captions": {
    "mode": "auto",                       // auto: phrases generated from kept words; manual: phrases below are used
    "phrases": [ {"text": "siapa yang pernah run ads dia tahulah", "a": 599.5, "b": 601.3} ],
    "hidden": false
  },
  "title": { "lines": [ {"text": "Apa yang menarik", "hl": null}, {"text": "dengan AI agent?", "hl": "AI agent"} ],
             "until": 603.30 },            // null = no title. Shown from frame 0 until `until`.
  "headlines": [
    { "id": "h1", "until": 636.40,
      "lines": [ {"text": "Test sebanyak", "at": 614.81, "hl": null},
                 {"dim": true, "at": 659.30},          // fades the lines above to 38%
                 {"text": "dapat winning ads.", "at": 632.50, "hl": "winning ads"} ] }
  ],
  "moments": [
    { "id": "m1", "kind": "fullscreen", "slide": 639.60, "until": 652.99,
      "head": { "lines": [ {"text": "Berkekalan", "at": 636.95, "hl": null} ], "until": 644.20 },
      "items": [ {"image": "/abs/…/book.jpg", "frame": "book", "label": null, "at": 644.69,
                  "x": 540, "y": 990, "scale": 1.38, "angle": -3} ],
      "counter": { "from": "2026", "to": "1923", "start": 640.10, "land": 641.62, "y": 960,
                   "shrink": 644.25, "shrink_to": [250, 0.42], "persist": 660.85 } },
    { "id": "m2", "kind": "manuscript", "at": 660.95, "until": 673.55, "header": "SCIENTIFIC ADVERTISING · 1923",
      "text": "Rigorous testing.", "type_at": 667.20, "type_end": 668.50, "x": 540, "y": 470, "angle": -2 },
    { "id": "m3", "kind": "zoom", "at": 696.55, "until": 697.95, "zoom": 1.16, "cx": 484, "cy": 190 }
  ],
  "sound": { "auto": true, "sfx_gain_db": 0, "muted": [], "extra": [ {"name": "pop", "at": 700.1, "gain": -13} ],
             "voice_lufs": -17, "true_peak": -1.5 },
  "look": { "preset": "house-v1" },
  "output": { "width": 1080, "height": 1920, "fps": 24 }
}
```

- `frame`: `photo` (off-white printed-photo border), `cutout` (transparent PNG with soft shadow), `book` (spine
  shading + shadow). `label`: optional lime tag under the item.
- `slide` (fullscreen): when the speaker card starts sliding out (0.5 s ease); card returns at `until`. If absent:
  0.5 s before the first item / counter start.
- `counter`: rolls year strings from `from` to `to` (ease-out, ~14 steps), lime marker on landing, optional shrink
  (to `[y, scale]`) and `persist` (stays pinned, small, until that time even after the card returns).
- `sound.auto`: SFX derived exactly as the V02 renderer does — whoosh on card out/in, pop per item, soft click per
  highlight, key-press ticks + soft impact for counters, whoosh + typing for manuscripts. `muted` holds SFX keys
  (from the plan) the director switched off. `extra` adds hand-placed SFX.
- Assets: house assets (fonts, sfx, paper texture) live in `DATA_DIR/assets/house/`; clip images are absolute paths
  (uploads go to `<clip workdir>/assets/img/`).
- Snapshots: every render saves the exact recipe to `DATA_DIR/edits/<clip_id>/v<N>.json`.

### The plan (resolved recipe, output time)

`plan(spec)` resolves the recipe into what the viewer sees, in **output seconds**, so the UI never re-implements
timing logic:

```json
{ "duration": 95.5,
  "segments": [ {"a": 599.49, "b": 603.41, "o": 0.0, "mute": false, "snapped": [599.49, 603.41]} ],
  "captions": [ {"i": 0, "text": "…", "t0": 0.0, "t1": 1.9} ],
  "title": {"t0": 0, "t1": 3.8, "lines": [ {"text": "…", "hl": null} ]},
  "headlines": [ {"id": "h1", "t0": 7.9, "t1": 11.3, "lines": [ {"i": 0, "text": "…", "t": 7.9, "hl": null} ], "dims": [21.5]} ],
  "moments": [ {"id": "m1", "kind": "fullscreen", "t0": 19.5, "t1": 28.6, "summary": "Year counter 2026→1923 · 1 image"} ],
  "sfx": [ {"key": "m1:whoosh-in", "name": "whoosh-short", "t": 19.5, "gain": -15, "muted": false, "source": "auto"} ],
  "warnings": [ "h3 line 2 is anchored inside a removed part; clamped to 28.6 s" ] }
```

## Python modules

- `studio_core/house_plan.py` — **stdlib only** (server imports it): `validate(spec) -> list[str] errors`,
  `plan(spec) -> dict`, `seg_map(spec) -> [(a, b, o)]`, `src_to_out(spec, src) -> float|None`,
  `out_to_src(spec, out) -> float`, `snap_segments(spec) -> segments` (moves `snap: true` boundaries into the
  quietest 10 ms window within ±0.3 s using ffmpeg-decoded 16 kHz audio and stdlib `array`; cached in
  `DATA_DIR/cache/snap.json`), `auto_captions(spec, words) -> phrases`, `sfx_events(spec, plan) -> list`,
  `diff(old, new) -> list[str]` human bullets ("Text: 'X' → 'Y'", "Cut: removed 'ok so kira' (−0.8 s)",
  "Moments: added manuscript"), `rough_cut_spec(clip_id, source_file, words_path, ranges, title) -> spec`.
- `studio_core/house_render.py` — numpy + Pillow, run through
  `uv run --with pillow --with numpy python -m studio_core.house_render …` (cwd = studio dir):
  `render <spec.json> <out.mp4> [--progress <file>]` (writes JSON progress `{"frame": n, "total": N}`),
  `still <spec.json> <t_out> <out.jpg> [--width 540]`. Visual output must match the approved V02 v5 renderer
  (an earlier approved bespoke renderer) — it is a port, not a restyle.

## HTTP API additions

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| GET | `/api/clips/<id>/edit` | | `{spec, plan, rendered_version, dirty, changes:[str], job}` (404 `{error:"no recipe"}` if none) |
| PUT | `/api/clips/<id>/edit` | `{spec}` | same as GET (400 with `errors` on invalid spec) |
| POST | `/api/clips/<id>/edit/rough-cut` | | create a recipe from the clip's source ranges (approved proposal) → same as GET |
| GET | `/api/clips/<id>/words` | `?pad=30` | `{words: [[w, s, e], …]}` source words from min(a)−pad to max(b)+pad |
| GET | `/api/clips/<id>/still.jpg` | `?t=<out s>&w=540` | draft still of the current recipe (cached by recipe hash + t) |
| POST | `/api/clips/<id>/render` | `{note?, addresses?}` | `{job}`; on success registers version N+1 (notes = note + changes), snapshots recipe |
| GET | `/api/clips/<id>/render` | | `{job: {state: idle|running|done|error, progress, message, version}}` |
| POST | `/api/clips/<id>/assets` | raw image body, `?name=file.png` | `{path}` saved under `<workdir>/assets/img/` |

`job` progress is also mirrored into `clip.agent`-like field `clip.render` so `/api/state` shows "Rendering 42%".
Approving a proposal also creates the rough-cut recipe and, when `settings.auto_rough_cut` (default true), starts
its render.

CLI: `studio.py recipe <clip>` (print path), `studio.py render <clip> [--note …] [--addresses c1,c2]`,
`studio.py rough-cut <clip>`, `studio.py still <clip> --t 12.3 --out f.jpg`.
The editor brief tells Claude to change the recipe JSON (never hand-edit render scripts for recipe clips) and to
run `studio.py render` to register the version.

## Edit view (`#/edit/<id>`)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ① Source → ② Cut → ③ Captions → ④ Text → ⑤ Moments → ⑥ Sound →   [ ▶ Render v6 · 3 changes ] │  recipe strip
├───────────────────────────┬──────────────────────────────────────────────────────────────┤
│  phone preview            │  STEP EDITOR (the selected step's settings)                  │
│  [Rendered v5 | Draft]    │                                                              │
│                           │                                                              │
│  lanes (output time):     │                                                              │
│  Cut      ▮▮ ▮▮▮ ▮ ▮▮▮    │                                                              │
│  Captions ▫▫▫▫▫▫▫▫▫▫▫     │                                                              │
│  Text        ▭   ▭  ▭     │                                                              │
│  Moments       ███   ▭    │                                                              │
│  Sound    · ·  ·· · ·     │  Ask Claude about this step… [Send]                          │
└───────────────────────────┴──────────────────────────────────────────────────────────────┘
```

- Recipe strip: 7 cards (number, name, one-line summary from the plan, dot: green = same as last render, amber =
  changed). Click → step editor. Arrow connectors. Render button at the end shows the change count; while
  rendering it shows progress; when done a toast "v6 ready — Review it".
- Preview: toggle **Rendered vN** (the video, player) / **Draft** (still of the current recipe at the playhead,
  refreshed 300 ms after an edit or seek; clearly labelled "not rendered yet"). Lanes share the playhead; click an
  item → opens its step and selects it.
- ⌘Z / ⇧⌘Z undo/redo (recipe history), autosave (debounced PUT, "Saved" indicator), Esc deselects.
- Step editors: Source (read-only), Cut (transcript word editor), Captions (list: time, editable text, merge/split,
  "Back to auto"), Text (title + headline cards: lines with text, `at` as m:ss.s in OUTPUT time with
  "set to playhead", highlight = click a word in the line, until; add at playhead; delete), Moments (list + "Add":
  Images · Year counter · Manuscript · Zoom-in; each with a form; image picker = existing clip images + upload),
  Sound (auto toggle, SFX volume slider, event list with mute, voice loudness), Render (changes list, note, button,
  render history).

### Frontend module contract (v2)

- `js/api.js` gains `export async function put(path, body)`.
- `js/edit.js` registers view `edit` (route `#/edit/<id>`) and owns the shell (strip, preview, lanes, undo, save,
  Source/Captions/Text/Sound/Render steps). It imports `./edit-cut.js` and `./edit-moments.js`:
  `export function mountCutStep(container, ctx)` / `export function mountMomentsStep(container, ctx)` → each
  returns `{ update(ctx), destroy() }`.
- `ctx = { clip, spec, plan, words, selected, update(mutator, label), select(kind, id), seek(tOut), time(),
  play(), pause(), srcToOut(src), outToSrc(out), refreshStill(), api: {get, post, put, patch, del} }`.
  `update(mutator, label)`: the shell deep-clones the spec, calls `mutator(draft)`, pushes undo, saves (debounced
  PUT), refetches the plan and calls every mounted step's `update(newCtx)`. Step modules never PUT directly.
  `srcToOut`/`outToSrc` use `plan.segments` (piecewise-linear; removed parts clamp to the next kept moment).
- CSS: `edit.css` (shell) and `edit-parts.css` (cut + moments), both linked from index.html, prefixed `.ed-`.
