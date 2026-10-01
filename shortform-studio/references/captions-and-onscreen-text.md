# Captions and on-screen text

Rules for anything that appears as text on the clip: captions, titles,
headlines, and image pop-ins. Applies to both the standard renderer and the
Studio recipe (house-style) renderer.

## Captions

- Keep every visible caption at exactly **two balanced lines**.
- Use stable phrase chunks, normally 2-6 words and about 34 characters.
- Use **sentence case**: lowercase except at the start of an actual sentence,
  in acronyms/initialisms (AI, MCP, API, GPT, PDF), and in proper names. Do
  not capitalize merely because a word starts a new caption chunk.
- Correct obvious ASR (speech-to-text) errors without rewriting what the
  speaker said. Course- or speaker-specific corrections (names, products,
  local terms) go in the manifest's per-source `caption_replacements`.
- **No active-word highlight or per-word "karaoke" animation.** A brief
  whole-caption entrance is acceptable in a house-style render, as long as
  both lines stay readable and stable.
- Captions begin **after** the title disappears (title owns the first five
  seconds) and occupy the layout's documented text position.
- Default caption language follows the recording's own spoken language --
  Malay captions for a Malay recording are the normal case, not an exception.

When word timestamps are unavailable, estimate phrase timing from transcript
segment timing plus detected non-silent intervals (see `scripts/tighten.py`).
Remap the hook and every jump cut onto the assembled output timeline before
placing captions.

## On-screen text taste (headlines, in a house-style render)

These are the defaults seeded into `taste.json` (see
`references/taste-seed.json`); the director/user can add to or override them
per project, and the active rules always win over this file.

1. **Speaker first.** Leave long stretches as speaker + captions only. Many
   moments in a clip should have no headline at all -- never fill a moment
   just because the headline area is empty.
2. **Headlines are the speaker's own words, timed to the spoken word.**
   Short, one idea, at most three lines. Check the waveform: ASR word times
   can be 0.3-0.7s off, and a viewer must never read one thing while hearing
   another.
3. **No worked examples, mock UIs, or hypothetical diagrams.** Inventing a
   sample workflow or dashboard to illustrate the point makes people read
   instead of watch, and confuses what the clip is actually about.
4. **Never invent content.** No made-up end cards, recap steps, quotes, or
   example numbers on screen. Everything shown must be said or shown in the
   source recording.
5. **Images pop in only when literal to the words being said** -- illustrate
   the exact noun the speaker just said, not a generic decoration. Prefer
   real recording/screen evidence over a generated or stock image; if a
   non-recording image is used, record its source.
6. **Brief full-screen moments are welcome** when a visual carries the beat
   better than a talking head (a chart, a screenshot, a comparison). Time the
   exit so the next visual lands as the card leaves -- no empty frame -- and
   hide captions while the card crosses them.
7. **Give numbers and references context.** A bare number or year needs a
   short label naming what it is. Remove a line a viewer cannot parse rather
   than leaving it ambiguous.
8. **Title on frame 0** when the clip needs framing to make sense cold, fully
   drawn in the very first frame (it also becomes the thumbnail).

## Platform-safe area

- **Nothing important in the lowest 250px** of the 1080x1920 canvas -- no
  face, no title, no caption. That band is reserved for platform UI
  (TikTok/Reels/Shorts controls). Non-essential imagery may extend under it.
- The standard renderer additionally reserves the top ~280px for
  platform search/notch UI on the shared frame; see
  `references/layout-profiles.md`.

## Avoid

Overcrowded frames, two ideas on screen at once, decorative loops that add no
information, a background-only frame outside an approved transition, text
over the speaker's face, and anything placed in the bottom 250px safe area.
