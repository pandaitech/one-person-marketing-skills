# Final-polish workflow

Use this workflow after a clip already exists and the user wants a final
editorial pass: accurate word boundaries, tighter pacing, removed
repetition/filler, restored context, and a verified replacement candidate.

## 1. Recover the source story

Start from the original recording, not a compressed vertical export. Treat
the existing clip as evidence of prior intent.

Locate:

- the original recording;
- the complete master transcript (an existing SRT/VTT/Zoom/YouTube
  transcript, or a prior ASR result);
- the clip's earlier hook and full ranges;
- its current render and title;
- enough transcript before and after the old range to identify the complete
  setup, explanation, example, and conclusion.

Read the surrounding section before trimming. Restore omitted material when
the old clip introduces a promise, example, demonstration, pronoun, or
conclusion that it does not complete.

For a continuation, comparison, or tool-switch demo, recover both sides of
the story. Search beyond the current clip's nearby window when the earlier
part happened elsewhere in the recording. Keep enough of that earlier part
for viewers to recognize the same task or artifact later; omit unrelated
setup and waiting.

## 2. Build trustworthy word timing

Use two transcript layers:

1. **Master transcript** -- the topic map for full-recording discovery and
   surrounding context (whatever transcript the user already has, or a
   coarse ASR pass).
2. **Local Whisper.cpp word timeline** (`scripts/transcribe.py`) -- the
   precision layer, run locally on the original recording.

If the master transcript already contains accurate `word_segments`, the
renderer can use it directly -- don't rerun alignment without a reason. If
word timing is absent or coarse, use `scripts/transcribe.py`.

For one clip, transcribe a focused source window with generous context. For
a recording expected to produce many clips, create and cache a
full-recording word timeline once. Long sources may be processed as
sequential explicit windows with absolute offsets; keep Whisper.cpp threads
at 1 for the master timeline (parallel processors can misalign timestamps
across windows). Reconcile a short overlap at each boundary before merging
windows.

Use the multilingual model appropriate to the source language -- don't use
an English-only model on a Malay/English-mixed recording.

Example focused alignment:

```bash
python3 scripts/transcribe.py \
  /absolute/path/session.mp4 \
  --model ~/.cache/shortform-studio/whisper/models/ggml-medium.bin \
  --output /absolute/path/session-window-words.json \
  --language ms \
  --start 00:11:20 \
  --duration 00:05:20
```

The script writes absolute `segments` and `word_segments`, so its output can
replace the coarse transcript path in a render-manifest source profile.

When an opening, ending, or internal cut remains ambiguous, transcribe a
smaller 8-20 second window around it and compare that timing with the
waveform and audible phoneme.

Before an expensive styled render, assemble a rough cut from the original
source and re-transcribe it. If the assembled speech disagrees with the
intended cut, re-align a short source window around that join, compare the
waveform, correct the ranges, and check the new assembly. Lock the corrected
edit before remapping captions and screen motion.

### Place a cut from the waveform, then probe it

ASR word times commonly run 0.3-0.7s early or late, and the error varies
within one recording. Place each boundary from audio evidence:

1. List the real gaps: a short RMS envelope of the source window (quiet is
   low RMS), then a finer envelope around the chosen gap.
2. Probe candidate starts and ends: transcribe the source from each
   candidate point (2-5s, with ~0.4s of leading silence) and read the first
   or last word. Short windows can hallucinate, so try two window lengths
   and trust only consistent results.
3. After assembly, re-transcribe the whole export. A lead-in word that
   appears only in the full-file transcript while consistent short probes
   read cleanly is usually a transcription artifact -- flag it for listening
   rather than cutting into the next word.

## 3. Make the editorial cuts

Audit every retained and removed section for:

- silence around 1.1 seconds or longer;
- repeated words, sentences, examples, or hook claims;
- fillers and false starts that can be removed without making speech sound
  robotic;
- topic drift;
- a hook repeated later in the body;
- missing setup, antecedents, examples, demonstrations, or conclusions;
- cut points inside a word or before the speaker finishes its final sound.

Filler is more than "um/uh" -- remove short phrases that carry no meaning
when they sit in a clean gap, but keep a phrase that completes the sentence,
and keep a filler that runs directly into the next word with no gap:
clipping a word is worse than leaving a filler. Also remove muddled asides
and read-outs a viewer cannot parse, even inside restored context.

Keep approximately 0.12 seconds of room tone at a normal jump cut, adjusting
by ear when a plosive, breath, or immediate next word requires more or less.

For each proposed removal, apply the removal test and protect the teaching
arc -- see [editorial-rules.md](editorial-rules.md) sections 6-7.

Do not fear duration; fear unnecessary or boring parts. A short silent beat
(muted source picture) after a punchline is acceptable.

Represent every retained source span as an absolute manifest range. If a
prepended hook comes from inside the body, remove that occurrence from the
body so it is heard once. Use a cold open when the hook and opening make the
same claim.

When a hook is being selected or challenged, generate 3-5 viable verbatim
candidates from different parts of the complete story, rank them, then build
at least two short opening proofs using the strongest candidates before
choosing -- see [editorial-rules.md](editorial-rules.md) section 4.

Do not remove a hesitation when it conveys uncertainty or meaning. Do not
remove repetition that is necessary for emphasis or comprehension.

## 4. Record the decisions

Write a compact `edit-decisions.md` beside the proof artifacts containing:

- original and polished durations;
- central idea and complete story structure;
- restored source ranges and why they were restored;
- removed source ranges and the reason for each removal;
- hook mode and duplication decision;
- hook candidates tested, their proof paths, ranking, and rejection reasons;
- timing engine, model, source window, and any boundary rechecks;
- verification performed.

This report makes the proof reproducible and distinguishes editorial
removals from automatic silence deletion.

## 5. Verify the assembled proof

Verification is part of polishing, not an optional QA phase.

1. Full decode with `scripts/check.py` (or ffmpeg directly) and compare
   audio/video duration.
2. Inspect frames at the title, title-to-caption handoff, hook transition,
   every visually important jump, a late caption, and the ending.
3. Listen from at least 0.5 seconds before to 0.5 seconds after every join.
   Reject chopped consonants, swallowed endings, duplicated syllables,
   unnatural breath cuts, or unexplained visual jumps.
4. Re-transcribe the assembled output and compare its beginning, each join,
   restored material, and final sentence with the intended script.
5. Scan the output waveform for remaining accidental long silence.
6. Confirm the title describes the complete clip rather than a hook-only
   side remark.
7. Summarize the assembled video from playback alone, without consulting the
   source transcript. Confirm the subject, contrast/problem, mechanism/
   example, and conclusion can be identified in order. If a link is missing,
   restore the relevant original passage or screen action.

The polish succeeds only when the clip is understandable without prior
context, the complete teaching arc survives the removals, the promise is
completed, each spoken join sounds natural, the hook appears once, and the
final sentence lands cleanly. When pacing and comprehension conflict,
comprehension wins.

If auditory playback inspection is unavailable (no audio output in the
environment), complete the source recovery, rough-cut transcription, visual
and full-decode checks, and deliver a reviewable proof with listening
explicitly marked unverified.
