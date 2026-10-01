// edit-cut.js — Cut step: a Descript-style transcript editor.
// "Edit the video by editing the words." Owns only its own DOM inside `container`.
//
// Recipe times are always SOURCE seconds; anything shown to the director is OUTPUT
// time via ctx.srcToOut(). This module never calls ctx.api.put — every change goes
// through ctx.update(mutator, label) so the shell can autosave/undo/refresh the plan.

import { h, fmtTime, fmtDur, parseTime } from './util.js';

const PARA_GAP = 1.2;       // seconds of silence that starts a new paragraph
const RUN_MERGE_GAP = 0.35; // merge two kept-word runs into one segment below this gap
const SEG_PAD = 0.12;       // padding added around a kept-word run when forming a segment
const ASR_EARLY = 0.6;      // ASR words can start up to this many seconds early

/** A word ([text, s, e]) is kept if its midpoint is inside a segment, or it starts
 * slightly before the segment (ASR words run early) and ends inside it. */

const MIN_PIECE = 0.2;   // drop slivers shorter than this after a cut
const CUT_PAD = 0.04;    // tiny margin so the removed words' edges go too (the edge then snaps into silence)

// Remove [a, b] from the kept segments. Pieces left on either side keep their untouched edge exactly; the new
// edge is marked to snap into the nearest silence.
function cutSpan(segs, a, b) {
  const ra = a - CUT_PAD;
  const rb = b + CUT_PAD;
  const out = [];
  for (const sg of segs) {
    if (sg.b <= ra || sg.a >= rb) { out.push(sg); continue; }
    if (ra - sg.a >= MIN_PIECE) {
      out.push({ ...sg, b: ra, snap_a: edgeSnap(sg, 'a'), snap_b: true, snap: undefined });
    }
    if (sg.b - rb >= MIN_PIECE) {
      out.push({ ...sg, a: rb, snap_a: true, snap_b: edgeSnap(sg, 'b'), snap: undefined });
    }
  }
  return out.map(clean).sort((x, y) => x.a - y.a);
}

// Add [a, b] back. Existing edges stay; only edges that come from the added span snap.
function keepSpan(segs, a, b) {
  const ra = a - SEG_PAD;
  const rb = b + SEG_PAD;
  let merged = { a: ra, b: rb, snap_a: true, snap_b: true, mute: false };
  const out = [];
  for (const sg of segs) {
    if (sg.b < merged.a - 0.05 || sg.a > merged.b + 0.05) { out.push(sg); continue; }
    // overlaps or touches: absorb it, keeping whichever edge is outermost (and its snap setting)
    if (sg.a <= merged.a) { merged.a = sg.a; merged.snap_a = edgeSnap(sg, 'a'); }
    if (sg.b >= merged.b) { merged.b = sg.b; merged.snap_b = edgeSnap(sg, 'b'); }
    merged.mute = merged.mute || !!sg.mute;
  }
  out.push(merged);
  return out.map(clean).sort((x, y) => x.a - y.a);
}

function edgeSnap(sg, side) {
  const k = side === 'a' ? 'snap_a' : 'snap_b';
  return sg[k] !== undefined ? !!sg[k] : !!sg.snap;
}

function clean(sg) {
  const o = { a: +sg.a.toFixed(3), b: +sg.b.toFixed(3), mute: !!sg.mute };
  const sa = edgeSnap(sg, 'a');
  const sb = edgeSnap(sg, 'b');
  if (sa === sb) o.snap = sa; else { o.snap = false; o.snap_a = sa; o.snap_b = sb; }
  return o;
}

const norm = (t) => String(t).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');

// Remove the first occurrence of the cut word sequence from phrases overlapping [a, b]; drop emptied phrases.
function removeWordsFromPhrases(phrases, cutWords, a, b) {
  const target = cutWords.map(norm).filter(Boolean);
  if (!target.length) return phrases;
  const out = [];
  for (const p of phrases) {
    if (p.b < a - 0.6 || p.a > b + 0.6) { out.push(p); continue; }
    const toks = String(p.text).split(/\s+/).filter(Boolean);
    const n = toks.map(norm);
    let at = -1;
    for (let i = 0; i + target.length <= n.length; i++) {
      if (target.every((t, k) => n[i + k] === t)) { at = i; break; }
    }
    if (at === -1) { out.push(p); continue; }
    toks.splice(at, target.length);
    const text = toks.join(' ').replace(/[,\s]+$/, '').replace(/^[,\s]+/, '');
    if (text) out.push({ ...p, text });
  }
  return out;
}

function isWordKept(word, segments) {
  const s = word[1], e = word[2];
  const mid = (s + e) / 2;
  for (const seg of segments) {
    if (mid >= seg.a - 1e-9 && mid <= seg.b + 1e-9) return true;
    if (s <= seg.a + 1e-9 && (seg.a - s) <= ASR_EARLY + 1e-9 && e >= seg.a - 1e-9 && e <= seg.b + 1e-9) return true;
  }
  return false;
}

function computeParagraphs(words) {
  const paras = [];
  let start = 0;
  for (let i = 1; i < words.length; i++) {
    if (words[i][1] - words[i - 1][2] >= PARA_GAP) {
      paras.push({ start, end: i - 1 });
      start = i;
    }
  }
  paras.push({ start, end: words.length - 1 });
  return paras;
}

function computeClipBounds(spec) {
  const segs = (spec.cut && spec.cut.segments) || [];
  if (!segs.length) return null;
  return { min: Math.min(...segs.map((s) => s.a)), max: Math.max(...segs.map((s) => s.b)) };
}

function wordsKeptWithin(words, seg) {
  return words.filter((w) => isWordKept(w, [seg]));
}

export function mountCutStep(container, ctx0) {
  let ctx = ctx0;
  let words = null;          // current word list reference (rebuild trigger)
  let paras = [];
  let wordEls = [];
  let paraTimeEls = [];
  let clipBounds = null;     // computed once, from the recipe as first mounted
  let headerEl = null;
  let bodyEl = null;
  let joinsEl = null;
  let cutBtn = null;
  let keepBtn = null;

  let selAnchor = null;
  let selFocus = null;
  let selStart = null;
  let selEnd = null;
  let dragging = false;

  container.classList.add('ed-cut');
  container.tabIndex = 0;
  container.addEventListener('keydown', onKeydown);
  window.addEventListener('mouseup', onWindowMouseUp);

  update(ctx0);
  return { update, destroy };

  // ---- lifecycle ----------------------------------------------------------

  function update(newCtx) {
    const hadWords = !!words;
    const willHaveWords = !!(newCtx.words && newCtx.words.length);
    const wordsChanged = newCtx.words !== words || (words && newCtx.words && newCtx.words.length !== words.length);
    ctx = newCtx;

    if (!willHaveWords) {
      words = null;
      renderEmptyState();
      return;
    }
    if (!hadWords || wordsChanged || !bodyEl) {
      build();
      return;
    }
    refreshWordClasses();
    renderHeader();
    renderJoins();
  }

  function destroy() {
    window.removeEventListener('mouseup', onWindowMouseUp);
    container.innerHTML = '';
  }

  // ---- full (words present) build -----------------------------------------

  function build() {
    words = ctx.words;
    if (!clipBounds) clipBounds = computeClipBounds(ctx.spec);
    selAnchor = selFocus = selStart = selEnd = null;

    container.innerHTML = '';
    headerEl = h('div', { class: 'ed-cut-header' });
    bodyEl = h('div', { class: 'ed-cut-text' });
    joinsEl = h('div', { class: 'ed-joins' });
    cutBtn = h('button', { class: 'btn btn-sm', onclick: () => applyAction('cut') }, '✂ Cut selected');
    keepBtn = h('button', { class: 'btn btn-sm', onclick: () => applyAction('keep') }, '↺ Keep selected');

    container.append(
      headerEl,
      h('div', { class: 'ed-cut-actions row' }, cutBtn, keepBtn),
      bodyEl,
      h('div', { class: 'ed-joins-wrap' },
        h('div', { class: 'ed-joins-title' }, 'Joins'),
        joinsEl),
    );

    renderParagraphs();
    renderHeader();
    renderJoins();
  }

  function renderParagraphs() {
    bodyEl.innerHTML = '';
    wordEls = new Array(words.length);
    paraTimeEls = [];
    paras = computeParagraphs(words);
    paras.forEach((p) => {
      const timeEl = h('span', { class: 'ed-para-time' }, '');
      paraTimeEls.push(timeEl);
      const textEl = h('span', { class: 'ed-para-text' });
      for (let i = p.start; i <= p.end; i++) {
        const w = words[i];
        const span = h('span', {
          class: 'ed-word',
          onmousedown: (e) => onWordMouseDown(e, i),
          onmouseenter: () => onWordMouseEnter(i),
        }, `${w[0]} `);
        wordEls[i] = span;
        textEl.append(span);
      }
      bodyEl.append(h('div', { class: 'ed-para' }, timeEl, textEl));
    });
    refreshWordClasses();
  }

  function refreshWordClasses() {
    const segs = (ctx.spec.cut && ctx.spec.cut.segments) || [];
    const kept = words.map((w) => isWordKept(w, segs));
    words.forEach((w, i) => {
      const el = wordEls[i];
      if (!el) return;
      el.classList.remove('ed-word-kept', 'ed-word-cut', 'ed-word-outside');
      if (kept[i]) {
        el.classList.add('ed-word-kept');
      } else if (clipBounds) {
        const mid = (w[1] + w[2]) / 2;
        el.classList.add(mid >= clipBounds.min && mid <= clipBounds.max ? 'ed-word-cut' : 'ed-word-outside');
      } else {
        el.classList.add('ed-word-outside');
      }
    });
    paras.forEach((p, pi) => {
      let firstKept = null;
      for (let i = p.start; i <= p.end; i++) {
        if (kept[i]) { firstKept = i; break; }
      }
      paraTimeEls[pi].textContent = firstKept == null ? 'cut' : fmtTime(ctx.srcToOut(words[firstKept][1]));
    });
    applySelectionClasses();
    return kept;
  }

  function renderHeader() {
    const segs = (ctx.spec.cut && ctx.spec.cut.segments) || [];
    const cuts = Math.max(0, segs.length - 1);
    headerEl.innerHTML = '';
    headerEl.append(
      h('div', { class: 'ed-cut-summary' }, `Clip length ${fmtDur(ctx.plan.duration)} · ${cuts} cut${cuts === 1 ? '' : 's'}`),
      h('div', { class: 'ed-cut-hint muted small' },
        'Click a word to jump there. Select words and press ✂ to cut them, ↺ to bring them back. Cuts snap to the nearest silence.'),
    );
  }

  function renderJoins() {
    joinsEl.innerHTML = '';
    const segs = (ctx.spec.cut && ctx.spec.cut.segments) || [];
    if (segs.length < 2) {
      joinsEl.append(h('div', { class: 'empty-state small' }, 'No joins yet — one continuous segment.'));
      return;
    }
    const planSegs = (ctx.plan && ctx.plan.segments) || [];
    for (let i = 0; i < segs.length - 1; i++) {
      const segA = segs[i];
      const segB = segs[i + 1];
      const planB = planSegs[i + 1];
      const joinOut = planB ? planB.o : ctx.srcToOut(segB.a);
      const before = wordsKeptWithin(words, segA).slice(-3).map((w) => w[0]).join(' ');
      const after = wordsKeptWithin(words, segB).slice(0, 3).map((w) => w[0]).join(' ');
      joinsEl.append(h('div', { class: 'ed-join row' },
        h('span', { class: 'ed-join-time muted' }, fmtTime(joinOut)),
        h('span', { class: 'ed-join-words' }, `…${before} | ${after}…`),
        h('button', { class: 'btn btn-sm', onclick: () => { ctx.seek(Math.max(0, joinOut - 2)); ctx.play(); } }, '▶ Play join'),
        h('span', { class: 'ed-join-nudges row' },
          h('button', { class: 'btn-icon', title: 'Move out point earlier', onclick: () => nudgeSeg(i, 'b', -0.1) }, '◀'),
          h('span', { class: 'muted small' }, 'out'),
          h('button', { class: 'btn-icon', title: 'Move out point later', onclick: () => nudgeSeg(i, 'b', 0.1) }, '▶'),
          h('button', { class: 'btn-icon', title: 'Move in point earlier', onclick: () => nudgeSeg(i + 1, 'a', -0.1) }, '◀'),
          h('span', { class: 'muted small' }, 'in'),
          h('button', { class: 'btn-icon', title: 'Move in point later', onclick: () => nudgeSeg(i + 1, 'a', 0.1) }, '▶')),
        h('label', { class: 'checkbox' },
          h('input', {
            type: 'checkbox', checked: !!segB.mute,
            onchange: (e) => toggleMute(i + 1, e.target.checked),
          }),
          'Mute this part')));
    }
  }

  // ---- empty state (no transcript) ----------------------------------------

  function renderEmptyState() {
    container.innerHTML = '';
    const segs = (ctx.spec.cut && ctx.spec.cut.segments) || [];
    const rows = h('div', { class: 'stack ed-cut-rows' });
    segs.forEach((seg, i) => {
      rows.append(h('div', { class: 'row ed-cut-row panel' },
        h('div', { class: 'field' }, h('label', {}, `Segment ${i + 1} start (source)`),
          h('input', { class: 'input', value: fmtTime(seg.a), onchange: (e) => updateSeg(i, 'a', parseTime(e.target.value)) })),
        h('div', { class: 'field' }, h('label', {}, 'end (source)'),
          h('input', { class: 'input', value: fmtTime(seg.b), onchange: (e) => updateSeg(i, 'b', parseTime(e.target.value)) })),
        h('label', { class: 'checkbox' },
          h('input', { type: 'checkbox', checked: !!seg.mute, onchange: (e) => updateSeg(i, 'mute', e.target.checked) }),
          'Mute'),
        h('button', { class: 'btn-icon', title: 'Delete segment', onclick: () => deleteSeg(i) }, '✕')));
    });
    container.append(
      h('div', { class: 'empty-state' },
        h('div', { class: 'empty-icon' }, '📝'),
        h('p', {}, "The transcript isn't available for this clip, so words can't be shown here. "
          + 'You can still edit the kept ranges directly below — times are in the source recording, not the edited video.')),
      rows,
      h('button', { class: 'btn btn-sm', onclick: addSeg }, '+ Add segment'));
  }

  function updateSeg(i, key, value) {
    ctx.update((draft) => {
      draft.cut.segments[i][key] = value;
      if (key === 'a' || key === 'b') draft.cut.segments[i].snap = false;
    }, `Cut: edited segment ${i + 1}`);
  }

  function deleteSeg(i) {
    ctx.update((draft) => { draft.cut.segments.splice(i, 1); }, `Cut: removed segment ${i + 1}`);
  }

  function addSeg() {
    const t = ctx.outToSrc(ctx.time());
    ctx.update((draft) => {
      draft.cut.segments = draft.cut.segments || [];
      draft.cut.segments.push({ a: t, b: t + 1, snap: true, mute: false });
      draft.cut.segments.sort((x, y) => x.a - y.a);
    }, 'Cut: added segment');
  }

  // ---- selection ------------------------------------------------------------

  function onWordMouseDown(e, i) {
    e.preventDefault();
    container.focus();
    if (e.shiftKey && selAnchor != null) {
      selFocus = i;
    } else {
      selAnchor = i;
      selFocus = i;
      dragging = true;
      ctx.seek(ctx.srcToOut(words[i][1]));
    }
    updateSelectionRange();
  }

  function onWordMouseEnter(i) {
    if (!dragging) return;
    selFocus = i;
    updateSelectionRange();
  }

  function onWindowMouseUp() {
    dragging = false;
  }

  function updateSelectionRange() {
    if (selAnchor == null) { selStart = selEnd = null; } else {
      selStart = Math.min(selAnchor, selFocus);
      selEnd = Math.max(selAnchor, selFocus);
    }
    applySelectionClasses();
  }

  function applySelectionClasses() {
    if (!wordEls.length) return;
    wordEls.forEach((el, i) => {
      if (!el) return;
      el.classList.toggle('ed-word-selected', selStart != null && i >= selStart && i <= selEnd);
    });
    const has = selStart != null;
    if (cutBtn) cutBtn.disabled = !has;
    if (keepBtn) keepBtn.disabled = !has;
  }

  function onKeydown(e) {
    const tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;
    if (selStart == null) return;
    if (e.key === 'Backspace' || e.key === 'Delete') { e.preventDefault(); applyAction('cut'); } else if (e.key === 'Enter') { e.preventDefault(); applyAction('keep'); }
  }

  // ---- cut / keep -------------------------------------------------------------

  function applyAction(kind) {
    if (selStart == null) return;
    const from = selStart;
    const to = selEnd;
    const text = words.slice(from, to + 1).map((w) => w[0]).join(' ');
    const snippet = text.length > 40 ? `${text.slice(0, 37)}…` : text;
    const label = kind === 'cut' ? `Cut: removed "${snippet}"` : `Cut: kept "${snippet}"`;

    // Minimal edit: only the selected words' span changes. Every other boundary keeps its exact value — they
    // were tuned by ear/waveform and must survive (rebuilding all segments from ASR word times would undo that).
    const spanA = words[from][1];
    const spanB = words[to][2];
    const cutWords = words.slice(from, to + 1).map((w) => w[0]);
    ctx.update((draft) => {
      const segs = (draft.cut.segments || []).map((sg) => ({ ...sg }));
      draft.cut.segments = kind === 'cut' ? cutSpan(segs, spanA, spanB) : keepSpan(segs, spanA, spanB);
      // Hand-set captions don't follow the words by themselves: drop the cut words from the caption lines that
      // cover them (auto captions regenerate from the kept words anyway).
      if (kind === 'cut' && draft.captions && draft.captions.mode === 'manual') {
        draft.captions.phrases = removeWordsFromPhrases(draft.captions.phrases || [], cutWords, spanA, spanB);
      }
    }, label);

    selAnchor = selFocus = selStart = selEnd = null;
    applySelectionClasses();
  }

  function nudgeSeg(i, key, delta) {
    ctx.update((draft) => {
      const seg = draft.cut.segments[i];
      if (!seg) return;
      const other = key === 'a' ? 'b' : 'a';
      const otherSnap = edgeSnap(seg, other);
      seg[key] = Math.max(0, seg[key] + delta);
      // a hand-nudged edge is kept exactly; the other edge keeps its own setting
      seg[key === 'a' ? 'snap_a' : 'snap_b'] = false;
      seg[other === 'a' ? 'snap_a' : 'snap_b'] = otherSnap;
      seg.snap = false;
    }, `Cut: nudged ${key === 'b' ? 'out' : 'in'} point`);
  }

  function toggleMute(i, muted) {
    ctx.update((draft) => {
      const seg = draft.cut.segments[i];
      if (seg) seg.mute = muted;
    }, `Cut: ${muted ? 'muted' : 'unmuted'} segment ${i + 1}`);
  }
}
