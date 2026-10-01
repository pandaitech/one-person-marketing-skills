# Layout profiles (standard renderer)

Choose the visual profile only after the editorial ranges and captions are
stable. Layout changes must never alter the spoken timeline. This file covers
the **standard renderer** (`scripts/render.py`) only -- for the Studio
recipe / house-style route, see
[recipe-and-motion-design.md](recipe-and-motion-design.md).

## Shared frame

Every standard profile uses:

- 1080x1920 at 24fps;
- a top safe area for platform search/notch UI;
- a centered 4:3 screen crop;
- title for the first five seconds, then captions;
- bold sans-serif type, at most two balanced lines;
- a platform-content safe guide covering the lowest 250px (see
  [captions-and-onscreen-text.md](captions-and-onscreen-text.md)).

## Profiles

`scripts/render.py --layout-profile <name>` accepts:

### `floating-card` -- default, "screen + speaker card"

Use this for ordinary recordings and lower-resolution speaker feeds (Zoom,
Meet, Teams tiles).

- Keeps the complete speaker tile, including any name label.
- Scaled down, centered, rounded corners.
- Speaker tile ends well above the bottom safe area.
- Screen feathers into a soft gradient background above the speaker card.
- Title/captions on a restrained translucent dark card.

The smaller tile reduces the perceived pixelation of a weak video-call feed
and leaves an explicit platform-safe bottom area.

### `immersive-speaker` -- "speaker only", enlarged

Use this only when the presenter is the main visual subject and the speaker
feed remains acceptable after enlargement.

- Speaker tile scaled up and center-cropped to fill most of the canvas.
- The crop may remove a name label, hands, or room edges; it must **never**
  cut the face.
- Screen feathers directly into the speaker.
- Face and all text stay above the bottom 250px safe guide; non-essential
  imagery may extend beneath it.

Do not select this for a visibly pixelated speaker feed merely to make the
presenter larger -- upscaling a low-resolution tile makes it worse, not
better.

### `full-width-speaker` -- complete speaker, maximum width

Use this when preserving the complete, uncropped speaker tile at maximum
width matters more than the softer aesthetic of `floating-card`.

- Keeps the complete speaker tile and any name label.
- Scaled to the full canvas width without cropping or distortion.
- An off-white title/caption band sits between the screen and speaker areas.
- Outlined caption treatment for contrast against that lighter band.

## Selection gate

For a new batch with an unresolved layout choice, compare the suitable
profiles on the same representative 20-30 second section -- don't render an
obviously unsuitable enlarged-speaker crop, and don't render all three as a
ritual. Reuse an approved profile when the source layout remains suitable.
Recommend `floating-card` by default; use a per-clip override only when the
source quality or content genuinely requires it.

The renderer reads a top-level or per-clip `layout_profile` from the
manifest (see [manifest-schema.md](manifest-schema.md)); the CLI
`--layout-profile` flag exists for comparison proofs and deliberate
rerenders.
