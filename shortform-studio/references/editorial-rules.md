# Editorial rules

The rules that decide *which* seconds of a recording become a clip, before any
rendering happens. Read this before proposing or approving a clip bank.

## Contents

1. The clip bank
2. Cold-viewer test and context audit
3. Length
4. Hook rules
5. Title rules
6. Tightening rules
7. Removal test and teaching arc

## 1. The clip bank

From a full recording (a class, webinar, live, podcast, meeting recording),
propose 15-30 distinct clip candidates by default. The count is a target, not
permission to include confusing or repetitive clips -- prefer fewer strong
candidates over padding the list.

Read the complete transcript, not keyword matches alone. For a business
recording, prioritize whatever the user's own themes are (ask, or infer from
the recording's subject): a concrete lesson, a demonstration, a surprising
number, a mistake and its fix, a before/after, a customer story. Deprioritize
pure housekeeping and meeting logistics.

Merge candidates that are one continuous story. Split only when each result
independently explains its own subject and conclusion.

## 2. Cold-viewer test and context audit

A publishable clip must pass the cold-viewer test: someone who has never seen
the rest of the recording can watch it and understand it completely.

A publishable clip:

- identifies its subject without relying on an earlier part of the recording;
- contains a complete claim, explanation, example, or conclusion;
- gives a cold viewer enough setup to understand pronouns ("this", "it", "that
  thing");
- does not end halfway through the next example;
- differs materially from the other proposed clips;
- earns its duration -- no boring stretch just because it was said.

Audit every candidate as one of:

- **Clear** -- a cold viewer can identify the subject and follow the complete
  thought.
- **Fixable** -- the core idea is strong but needs an earlier setup, a later
  conclusion, a merge with another candidate, or a precise internal trim.
  Propose the repaired timestamps, not just a description of the problem.
- **Reject** -- the candidate stays confusing, repetitive, weak, or dependent
  on context that isn't available inside the clip.

## 3. Length

Length is set by the idea, not a platform rule. A typical clip runs 45 seconds
to 3 minutes, but a complete thought that takes 4 minutes is better than a cut
version that loses the setup or the payoff. Never impose a fixed ceiling.

The test is: **does removing this part still let a first-time viewer
understand the clip?** If not, keep it, regardless of duration.

## 4. Hook rules

Choose the complete cut first, and know its central subject and payoff,
*before* choosing its hook.

A hook is a brief **verbatim** excerpt (word-for-word from the transcript --
never paraphrased or invented) with the strongest surprise, consequence,
tension, concrete result, or contrarian claim. Normally one short sentence or
fragment, about **2-6 seconds**, and never more than **8 seconds** combined.

Use one of two explicit hook modes:

- **Cold open** -- the strongest hook is already at the complete cut's
  beginning, or a separate hook would repeat or paraphrase the first 10-15
  seconds. Play only the full ranges; no prepended clip, no transition.
- **Prepended hook** -- a distinct excerpt from later in the cut creates a
  stronger opening without duplicating the opening. The standard renderer adds
  a short (0.28s) transition before the full ranges. Remove the hook's later
  occurrence from the body if it would otherwise repeat the same point twice.

Audit both timestamp overlap and meaning: if the hook begins at or within the
first second of the first full range, or expresses substantially the same
claim as the opening, use a cold open instead.

Hook selection is comparative, not one-shot:

1. Extract 3-5 viable verbatim candidates once the complete cut and its
   payoff are known. Look across the beginning, middle and end for genuinely
   different angles.
2. Rank each for cold-viewer clarity, centrality to the full story,
   specificity, clean 2-6 second delivery, exact word boundaries, and whether
   removing its body occurrence preserves coherence.
3. Keep one provisional winner and one or two runners-up.
4. After editorial approval, render the strongest two as short (8-12s)
   opening proofs with the proposed title and transition. Listen to and
   re-transcribe both -- transcript-only ranking is not the final test.
5. Choose the winner from actual playback: prefer the opening that makes the
   clip's practical promise immediately understandable over one that is
   merely dramatic.

If fewer than three viable hook candidates exist, say why instead of
manufacturing weak ones.

## 5. Title rules

The on-screen title:

- uses 4-10 words;
- describes the central subject, explanation, or payoff of the **complete
  cut**, not just the hook;
- is supported by the complete-cut transcript independently of the prepended
  hook;
- creates curiosity without changing the claim;
- appears for the first five seconds only.

Write and audit the title *after* choosing the complete cut. Never title a
broader clip around a side remark that only appears in the hook.

## 6. Tightening rules

Use transcript meaning and waveform evidence together:

- Remove pauses around **1.1 seconds** or longer, when pacing improves.
- Retain roughly **0.12 seconds** of room tone before and after each cut.
- Keep normal thinking pauses (shorter than the threshold) -- don't make
  speech sound robotic.
- Remove false starts, repeated filler, and topic drift only when the full
  idea remains intact.
- Never cut the noun that resolves an earlier pronoun, the evidence
  supporting a claim, or the conclusion of an example.
- Represent discontinuous retained material as multiple ranges in the
  manifest; keep source timestamps absolute.

`scripts/tighten.py` detects measurable silence candidates from the audio.
Treat its output as an editorial aid, not an automatic deletion decision --
decide each removal by meaning, not just duration.

## 7. Removal test and teaching arc

For every proposed removal, ask: **if this part is removed, will a
first-time viewer still understand the video?** Check whether they can still
identify the task or subject, the thing being referred to, why the next
action happens, and the payoff.

Before finalizing ranges, state the clip's cold-viewer teaching arc where it
applies:

1. **setup** -- what object, situation or problem is being discussed;
2. **contrast** -- what the ordinary approach does differently, or why the
   issue matters;
3. **mechanism/example** -- how the demonstrated method works in concrete
   terms;
4. **payoff/conclusion** -- what the viewer should now understand.

These don't need to be four separate scenes, but the assembled clip must
preserve the causal connection between them. A sentence is not removable
merely because the next sentence remains grammatical -- restore it if a later
explanation depends on its noun, number, comparison, or premise.

Do not optimize toward a predetermined duration. A 60-90 second clip that
communicates the complete lesson beats a 30-45 second clip that is
technically shorter but obscures the point. Fear unnecessary or boring parts,
not length.
