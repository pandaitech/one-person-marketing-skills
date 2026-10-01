# Studio recipe / house-style renderer

Use this route when a clip needs on-screen headlines, image pop-ins, and
full-screen explanation moments beyond what the standard fixed-layout
renderer (`scripts/render.py`) does. Read this after the editorial timeline
is approved, or when an existing clip needs a visual restyle.

## Keep four decisions separate

| Decision | Source of truth | May a styling-only request change it? |
| --- | --- | --- |
| Editorial | Approved source ranges, hook mode, transcript and audio | No |
| Layout | Measured media regions, scene roles, text positions and safe areas | Only as needed for the requested design |
| Theme | Colours, typography, materials | Yes |
| Motion | Narration-timed actions, focus targets, entrances and handoffs | Yes |

A clip's visual approval is not permission to rerender a batch, publish, or
rewrite its teaching point. Never decorate an unclear clip into looking
acceptable -- fix the edit first.

## Renderer

Clips managed through Studio render through the recipe renderer
(`studio/studio_core/house_render.py`; full recipe/plan schema in
`studio/docs/STUDIO-V2.md`):

- `studio.py recipe <clip>` -- validate the clip's recipe JSON.
- `studio.py still <clip> --t <sec> --out f.jpg` -- a draft still frame.
- `studio.py render <clip>` -- render and register a new version.

The recipe holds every timestamp in **source seconds** (positions in the
original recording); the renderer maps them to output time for you.

## Theme

There is no fixed brand palette. The renderer reads a neutral default theme
and a `theme` object from Studio settings (`studio.py` Settings view, or
`PATCH /api/settings`):

```json
{
  "theme": {
    "background": "#F4F3EF",
    "text": "#1C1C1C",
    "accent": "#3B6EA5",
    "accent2": "#2B4C6F",
    "font": "Inter"
  }
}
```

When the user has a `marketing-brain.md` (from the `marketing-brain` skill)
with a brand section, fill `background`/`text`/`accent`/`accent2` from its
stated brand colours and `font` from its stated typeface before the first
render, instead of asking. Otherwise leave the neutral defaults.

`font` names a Google Fonts family; the renderer downloads the weights it
needs into `$STUDIO_DATA_DIR/assets/house/` the first time they're used, and
falls back to a system sans-serif automatically if it's offline or the
family isn't available. No font files are ever committed to the skill.

The background is a solid theme colour plus a light procedural grain
(generated in code -- there is no background image asset to swap).

## What goes on screen

See [captions-and-onscreen-text.md](captions-and-onscreen-text.md) for the
full on-screen-text taste rules (speaker first, sparse text, never invent
content, nothing in the bottom 250px). The same rules apply here.

Motion vocabulary available in the recipe schema (see `STUDIO-V2.md` for the
exact fields): pop-in with slight overshoot and a soft shadow; a small
"stamp" mark under a pop-in; a rolling counter for a number/year, landing
with a soft impact; a "manuscript page" moment for a quoted line or number
(aged-paper look, typed-in text) -- useful for a stat or quote that needs to
stand alone for a beat; a short punch-in on an expressive gesture; dimming an
earlier line when a contrasting one arrives. Use a few per clip, not all of
them.

Avoid: overcrowded frames, two ideas at once, decorative loops, a
background-only frame outside an approved transition, text over the face,
and anything in the lowest 250px platform-control band.

## Sound

Voice only by default. Subtle SFX (whoosh, pop, soft click, typing) are
supported but **off unless the user supplies their own SFX files** in
`$STUDIO_DATA_DIR/assets/house/sfx/` -- no sound effects ship with the
skill. Mix SFX well under the voice; a starting reference is voice around
-17 LUFS integrated / -1.5 dBTP.

## Verify before delivery

- Preview stills at every beat, scene entry/settled pose, and card slide
  before the full render (`studio.py still`).
- Full decode of the export (`scripts/check.py`); check duration, 1080x1920
  H.264, AAC.
- Re-transcribe the export and compare every join and every removed phrase
  with the intended edit.
- Inspect frames at each headline, full-screen moment, punch-in, join, and
  the ending.
- Deliver a new versioned MP4 (Studio's `add-version`/`render` never
  overwrites an existing version file); keep previous versions.
- Say plainly what was not verified (e.g. no audio listening available in
  this environment).

## Taste book

The director's accumulated preferences live in `$STUDIO_DATA_DIR/taste.json`
(`studio.py taste`), seeded on first run from
[taste-seed.json](taste-seed.json). Read the active rules before designing
a clip -- they override this file where they differ. Propose a new rule
(`studio.py taste --propose "..."`) when the same director note recurs
across clips.
