# Screen-motion workflow

Use screen motion after the clip timeline is polished. Motion should make the
currently discussed interface easier to follow; it must not decorate inactive
screen regions or chase the cursor blindly.

## Build the plan

1. Render or inspect the assembled output timeline.
2. Capture a storyboard at roughly two-second intervals and at every app,
   window, modal, or page change.
3. Use the transcript to identify the visible object being explained: a
   comparison column, button, command, result, form, panel, or document
   section.
4. Draw one `focus_box` around that semantic target. Split or end the event
   when the visible target changes.
5. Verify samples throughout the event, never only its first frame.

Do not add a zoom when the full screen is already the clearest view, the
target is not visible, or the interface changes too quickly to hold one
focus.

## Event format

Motion timestamps use the assembled clip timeline after hooks and jump cuts
have been remapped. For the standard renderer, focus boxes and centers are
relative to the rendered 1080x810 screen area, not the whole 1080x1920
canvas. In a Studio recipe (house-style) scene, explicitly transform the
verified target box into the actual screen crop/size used by that scene --
don't paste standard-renderer coordinates onto a different-sized screen, and
don't zoom already-zoomed media again.

```json
{
  "screen_region": [0, 280, 1080, 810],
  "events": [
    {
      "start": 24.0,
      "end": 33.2,
      "focus_box": [70, 340, 350, 300],
      "padding": 70,
      "max_zoom": 1.42,
      "transition": 0.55,
      "verified_samples": [24, 26, 28, 30, 32],
      "reason": "Focus the comparison column while it is explained"
    }
  ]
}
```

- Prefer `focus_box`; the renderer derives its center and the strongest zoom
  that fits the box plus padding.
- Direct `center: [x, y]` and `zoom` are allowed for a manually approved
  composition.
- Keep zoom between 1.05x and 1.8x. Most events should stay around
  1.15x-1.55x.
- Use eased transitions around 0.45-0.65 seconds.
- Keep verified sample gaps at 2.1 seconds or less.
- Motion events must be ordered and non-overlapping. They may span a jump
  cut only when the same semantic target remains visible and verified on
  both sides -- the renderer preserves the zoom state across that cut.
- Every event needs a semantic `reason`.

## Render and verify

Add the plan path to the clip as `motion_plan`; `scripts/render.py` applies
the zoom to the screen before composing any layout profile, so the same plan
works with all three standard profiles.

For an already-rendered compatible 9:16 video, `scripts/screen_motion.py`
can apply the same validated plan without touching its audio stream:

```bash
python3 scripts/screen_motion.py \
  --plan /absolute/path/motion-plan.json \
  --input /absolute/path/input.mp4 \
  --output /absolute/path/output-motion.mp4 \
  --overwrite
```

Inspect the beginning, midpoint, and end of every event. Reject a plan if it
focuses blank space, hides the discussed control, follows the previous
screen after a page change, or produces a visible jump at an edit boundary.
