# Render manifest (standard renderer)

This is the executable contract for `scripts/render.py`, the bundled
standard renderer. For the Studio recipe / house-style route, the recipe
format is different -- see
[recipe-and-motion-design.md](recipe-and-motion-design.md) and
`studio/docs/STUDIO-V2.md`. The standard renderer's `--check` does not
validate a recipe, and the recipe renderer does not read this manifest.

## Contents

1. Minimal example
2. Fields
3. Commands

## Minimal example

```json
{
  "output_dir": "/absolute/path/to/shortform-videos",
  "layout_profile": "floating-card",
  "sources": {
    "session-1": {
      "video": "/absolute/path/to/session-1.mp4",
      "transcript": "/absolute/path/to/session-1-transcript.json",
      "screen_region": [0, 50, 960, 620],
      "speaker_region": [962, 270, 318, 180],
      "caption_replacements": {
        "the co pilot": "Copilot"
      }
    }
  },
  "clips": [
    {
      "id": "01",
      "source": "session-1",
      "title": "The One Habit That Fixed Our Follow-Ups",
      "motion_plan": "./01-screen-motion.json",
      "hook_ranges": [],
      "full_ranges": [
        [1950.000, 2003.606],
        [2004.501, 2013.834],
        [2014.953, 2029.428]
      ]
    }
  ]
}
```

## Fields

Top level:

- `output_dir`: an explicit absolute path to write renders to. Prefer a path
  under `$STUDIO_DATA_DIR/renders/<clip>/` (or another explicit local folder)
  over the renderer's default so output location is predictable.
- `layout_profile`: optional batch default -- `floating-card`,
  `immersive-speaker`, or `full-width-speaker`; omitted defaults to
  `floating-card`. See [layout-profiles.md](layout-profiles.md).
- `sources`: named recording profiles.
- `clips`: approved clip definitions.

Source profile:

- `video`: source recording path.
- `transcript`: timestamped JSON transcript path. Must contain `segments`
  with `start`, `end`, `text`; may additionally contain `word_segments` with
  `start`, `end`, and `word` or `text`. The renderer prefers usable
  `word_segments` and falls back to estimating words inside coarse segments.
- `screen_region`: measured `[x, y, width, height]` of the full screen-share
  region. The renderer derives its centered 4:3 crop from this.
- `speaker_region`: measured `[x, y, width, height]` of the complete speaker
  tile, including its name label if any.
- `caption_replacements`: optional raw-ASR-to-display-text mapping for
  speaker names, product names, or obvious transcription errors specific to
  this recording.

Clip:

- `id`: unique string or number used in the filename.
- `source`: key from `sources`.
- `title`: approved opening title, 4-10 words, describing the complete cut
  (see [editorial-rules.md](editorial-rules.md)).
- `layout_profile`: optional per-clip override of the batch profile.
- `motion_plan`: optional absolute or manifest-relative JSON plan using
  assembled-output timestamps and screen-relative focus coordinates -- see
  [screen-motion.md](screen-motion.md).
- `hook_ranges`: zero or more absolute source ranges. Use `[]` for a cold
  open. Otherwise, distinct prepended excerpts totaling no more than eight
  seconds.
- `full_ranges`: one or more absolute source ranges forming the complete
  cut.

Ranges use seconds and may include decimals. Convert `HH:MM:SS` timestamps
before writing the manifest.

The renderer rejects a prepended hook that begins at or within the first
second of the full cut, since that would create the same opening twice.
Complete the opening-comparison audit (see
[editorial-rules.md](editorial-rules.md)) before writing the manifest, and
use `hook_ranges: []` whenever the meaning repeats.

## Commands

Validate without rendering:

```bash
python3 scripts/render.py --manifest /absolute/path/manifest.json --check
```

Render one proof:

```bash
python3 scripts/render.py \
  --manifest /absolute/path/manifest.json \
  --clip 01 \
  --preview-seconds 30 \
  --overwrite
```

Render one complete clip:

```bash
python3 scripts/render.py --manifest /absolute/path/manifest.json --clip 01 --overwrite
```

Render the approved batch:

```bash
python3 scripts/render.py --manifest /absolute/path/manifest.json --all
```

Verify a rendered clip (full decode + boundary contact sheet):

```bash
python3 scripts/check.py --manifest /absolute/path/manifest.json --clip 01 \
  --rendered /absolute/path/to/01.mp4 --out-dir /absolute/path/to/frames
```

The renderer resolves relative paths against the manifest directory.
