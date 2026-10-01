// edit.js — the recipe editor (#/edit/<id>). Owns the shell: header + mode switch, recipe strip,
// preview (Rendered/Draft), lanes, undo/redo, autosave, and the Source/Captions/Text/Sound/Render
// step editors. Cut and Moments are built by ./edit-cut.js and ./edit-moments.js per the v2 module
// contract (mountCutStep/mountMomentsStep) — if either fails to import, this shows a friendly
// placeholder in that step instead of crashing the whole view.

import { registerView, navigate, getState } from './app.js';
import {
  get, post, put, patch, del,
} from './api.js';
import {
  h, fmtTime, fmtDur, relTime, md, toast, debounce,
} from './util.js';
import { createPlayer } from './player.js';

// ---- step metadata --------------------------------------------------------

const STEP_DEFS = [
  { key: 'source', num: 1, name: 'Source' },
  { key: 'cut', num: 2, name: 'Cut' },
  { key: 'captions', num: 3, name: 'Captions' },
  { key: 'text', num: 4, name: 'Text' },
  { key: 'moments', num: 5, name: 'Moments' },
  { key: 'sound', num: 6, name: 'Sound' },
];
const RENDER_STEP = { key: 'render', num: 7, name: 'Render' };
const ALL_STEP_KEYS = [...STEP_DEFS.map((s) => s.key), RENDER_STEP.key];
const KIND_LABEL = Object.fromEntries([...STEP_DEFS, RENDER_STEP].map((s) => [s.key, s.name]));
const MOMENT_KIND_LABEL = { fullscreen: 'full-screen', manuscript: 'page', zoom: 'zoom-in', screen: 'screen share' };

// ---- module state -----------------------------------------------------------

let root = null;
let clipId = null;
let clip = null;
let editData = null; // {spec, plan, rendered_version, dirty, changes, job}
let noRecipe = false;
let wordsData = null;
let wordsLoading = false;

let selected = { kind: 'source', id: null };
let previewMode = 'rendered'; // 'rendered' | 'draft'
let playhead = 0;
let player = null;

let undoStack = [];
let redoStack = [];
let saving = false;
let saveTimer = null;
let saveError = null;

let stillToken = 0;
let stillLoading = false;

let renderNote = '';
let renderPollTimer = null;

let shellRefs = null;
let stepModules = {}; // key -> {update(ctx), destroy()}
let lanesCleanup = null;

// ---- small pure helpers -------------------------------------------------------

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function clipCameFromIdea(c) {
  // Best-effort: clips created from an approved recording proposal get their `source` field
  // filled in automatically ("<file> ranges ..."); clips added directly via the CLI usually don't
  // set it. There's no explicit "from_proposal" flag on the Clip today, so this is a heuristic.
  return !!(c && c.source && c.source.trim());
}

function segMap() {
  return (editData?.plan?.segments || []).slice().sort((a, b) => a.a - b.a);
}
function srcToOut(src) {
  const segs = segMap();
  for (const seg of segs) {
    if (src >= seg.a && src <= seg.b) return seg.o + (src - seg.a);
  }
  const next = segs.find((s) => s.a > src);
  if (next) return next.o;
  const last = segs[segs.length - 1];
  if (last) return last.o + (last.b - last.a);
  return 0;
}
function outToSrc(out) {
  const segs = segMap();
  for (const seg of segs) {
    const o0 = seg.o;
    const o1 = seg.o + (seg.b - seg.a);
    if (out >= o0 && out <= o1) return seg.a + (out - o0);
  }
  if (!segs.length) return 0;
  if (out < segs[0].o) return segs[0].a;
  return segs[segs.length - 1].b;
}

function planDuration() {
  return editData?.plan?.duration || 0;
}

function stepSummaries() {
  const spec = editData.spec;
  const plan = editData.plan;
  const segCount = (plan.segments || []).length;
  const capCount = (plan.captions || []).length;
  const titleLines = spec.title?.lines?.length || 0;
  const headlineLines = (spec.headlines || []).reduce((n, hset) => n + (hset.lines?.length || 0), 0);
  const textSummary = titleLines
    ? `Title + ${headlineLines} line${headlineLines === 1 ? '' : 's'}`
    : (headlineLines ? `${headlineLines} line${headlineLines === 1 ? '' : 's'}` : 'No text yet');
  const momentCounts = {};
  (plan.moments || []).forEach((m) => { momentCounts[m.kind] = (momentCounts[m.kind] || 0) + 1; });
  const momentsSummary = Object.keys(momentCounts).length
    ? Object.entries(momentCounts).map(([k, n]) => `${n} ${MOMENT_KIND_LABEL[k] || k}`).join(' · ')
    : 'No moments yet';
  const sfxCount = (plan.sfx || []).length;
  const lufs = spec.sound?.voice_lufs ?? -17;
  return {
    source: plan.duration ? `${fmtDur(plan.duration)} total` : 'Reading the source…',
    cut: `${segCount} cut${segCount === 1 ? '' : 's'} · ${fmtDur(plan.duration || 0)}`,
    captions: `${capCount} caption${capCount === 1 ? '' : 's'}`,
    text: textSummary,
    moments: momentsSummary,
    sound: `${sfxCount} sound${sfxCount === 1 ? '' : 's'} · ${lufs} LUFS`,
  };
}

function stepDirtyFlags() {
  const flags = {
    cut: false, captions: false, text: false, moments: false, sound: false,
  };
  (editData?.changes || []).forEach((line) => {
    if (/^Cut:/.test(line)) flags.cut = true;
    else if (/^Captions:/.test(line)) flags.captions = true;
    else if (/^Text:/.test(line)) flags.text = true;
    else if (/^Moments:/.test(line)) flags.moments = true;
    else if (/^Sound:/.test(line)) flags.sound = true;
  });
  return flags;
}

function renderJob() {
  return editData?.job || { state: 'idle' };
}
function renderActive() {
  const s = renderJob().state;
  return s === 'running' || s === 'queued';
}

// ---- data loading -------------------------------------------------------------

async function loadClip() {
  clip = await get(`/api/clips/${clipId}`);
}

async function loadEdit() {
  try {
    editData = await get(`/api/clips/${clipId}/edit`);
    noRecipe = false;
  } catch (e) {
    if (String(e.message).toLowerCase().includes('no recipe')) {
      noRecipe = true;
      editData = null;
    } else {
      throw e;
    }
  }
}

async function loadWords() {
  if (wordsData || wordsLoading) return;
  wordsLoading = true;
  try {
    wordsData = await get(`/api/clips/${clipId}/words?pad=30`);
  } catch (e) {
    wordsData = { words: [] };
  }
  wordsLoading = false;
  notifyModules();
}

// ---- undo / redo -----------------------------------------------------------

function pushUndo(prevSpec, label) {
  undoStack.push({ spec: prevSpec, label: label || 'Edit' });
  if (undoStack.length > 100) undoStack.shift();
  redoStack = [];
}

async function undo() {
  if (!undoStack.length) return;
  const entry = undoStack.pop();
  redoStack.push({ spec: deepClone(editData.spec), label: entry.label });
  editData.spec = entry.spec;
  await saveSpec();
}
async function redo() {
  if (!redoStack.length) return;
  const entry = redoStack.pop();
  undoStack.push({ spec: deepClone(editData.spec), label: entry.label });
  editData.spec = entry.spec;
  await saveSpec();
}

// ---- autosave / update pipeline --------------------------------------------

function setSaving(state, message) {
  saving = state;
  saveError = null;
  if (!shellRefs) return;
  shellRefs.saveStatusEl.textContent = state ? 'Saving…' : (message || '');
  shellRefs.saveStatusEl.classList.toggle('ed-save-err', false);
}
function setSaveError(err) {
  saving = false;
  saveError = err;
  if (!shellRefs) return;
  const msg = (err && err.errors && err.errors.length) ? err.errors.join('; ') : (err?.message || 'Save failed');
  shellRefs.saveStatusEl.textContent = msg;
  shellRefs.saveStatusEl.classList.add('ed-save-err');
}

const debouncedSave = debounce(() => { saveSpec(); }, 400);

async function saveSpec() {
  if (!editData) return;
  setSaving(true);
  try {
    const res = await put(`/api/clips/${clipId}/edit`, { spec: editData.spec });
    editData = res;
    setSaving(false, 'Saved');
    notifyModules();
    refreshAll();
    scheduleStillRefresh();
  } catch (e) {
    setSaveError(e);
    toast((e.errors && e.errors.length) ? `Not saved: ${e.errors[0]}` : (e.message || 'Save failed'), 'err');
  }
}

function doUpdate(mutator, label) {
  if (!editData) return;
  const draft = deepClone(editData.spec);
  try {
    mutator(draft);
  } catch (e) {
    toast(`Edit failed: ${e.message}`, 'err');
    return;
  }
  pushUndo(deepClone(editData.spec), label);
  editData.spec = draft;
  setSaving(true);
  debouncedSave();
  refreshStrip();
  refreshLanes();
  scheduleStillRefresh();
}

// ---- draft still --------------------------------------------------------------

function scheduleStillRefresh() {
  if (previewMode !== 'draft') return;
  debouncedStill();
}
const debouncedStill = debounce(() => loadDraftStill(), 300);

function loadDraftStill() {
  if (!shellRefs || !clipId) return;
  const t = Math.max(0, playhead);
  const token = ++stillToken;
  stillLoading = true;
  shellRefs.draftSpinner.classList.remove('hidden');
  const img = new Image();
  img.onload = () => {
    if (token !== stillToken) return;
    stillLoading = false;
    shellRefs.draftSpinner.classList.add('hidden');
    shellRefs.draftImg.src = img.src;
  };
  img.onerror = () => {
    if (token !== stillToken) return;
    stillLoading = false;
    shellRefs.draftSpinner.classList.add('hidden');
  };
  img.src = `/api/clips/${clipId}/still.jpg?t=${t.toFixed(2)}&w=540`;
}

// ---- playhead / seek / mode -----------------------------------------------------

function seekTo(t) {
  playhead = Math.max(0, Math.min(planDuration() || t, t));
  if (previewMode === 'rendered' && player) {
    player.seek(playhead);
  } else {
    scheduleStillRefresh();
  }
  updatePlayheadUI();
}

function updatePlayheadUI() {
  if (!shellRefs) return;
  shellRefs.timeLabel.textContent = `${fmtTime(playhead)} / ${fmtTime(planDuration())}`;
  const frac = planDuration() ? playhead / planDuration() : 0;
  shellRefs.scrub.value = String(Math.round(frac * 1000));
  if (shellRefs.lanesPlayhead) {
    shellRefs.lanesPlayhead.style.left = `${Math.min(100, Math.max(0, frac * 100))}%`;
  }
}

function setPreviewMode(mode) {
  if (mode === previewMode) return;
  previewMode = mode;
  buildPreviewArea();
  updatePlayheadUI();
  if (mode === 'draft') loadDraftStill();
}

// ---- recipe strip -----------------------------------------------------------

function selectStep(kind, id) {
  selected = { kind, id: id || null };
  showSelectedStep();
  refreshStrip();
}

function buildStrip() {
  const summaries = stepSummaries();
  const dirty = stepDirtyFlags();
  const nodes = [];
  STEP_DEFS.forEach((step, i) => {
    const isDirty = dirty[step.key];
    nodes.push(h('button', {
      type: 'button',
      class: `ed-step-card${selected.kind === step.key ? ' active' : ''}`,
      onclick: () => selectStep(step.key),
      title: `${step.name} — ${summaries[step.key]}`,
    },
    h('span', { class: 'ed-step-num' }, String(step.num)),
    h('span', { class: 'ed-step-name' }, step.name),
    h('span', { class: 'ed-step-summary muted' }, summaries[step.key]),
    step.key !== 'source' ? h('span', { class: `ed-step-dot ${isDirty ? 'ed-dot-amber' : 'ed-dot-green'}` }) : null));
    nodes.push(h('span', { class: 'ed-arrow', 'aria-hidden': 'true' }, '→'));
  });
  const changeCount = (editData.changes || []).length;
  const nextV = (editData.rendered_version == null ? 0 : editData.rendered_version) + 1;
  const job = renderJob();
  let renderLabel;
  if (job.state === 'running') {
    const pct = job.progress != null ? Math.round(progressFrac(job.progress) * 100) : null;
    renderLabel = h('span', {}, `Rendering v${nextV}…${pct != null ? ` ${pct}%` : ''}`);
  } else if (job.state === 'queued') {
    renderLabel = h('span', {}, 'Queued to render…');
  } else {
    renderLabel = changeCount
      ? h('span', {}, `▶ Render v${nextV} · ${changeCount} change${changeCount === 1 ? '' : 's'}`)
      : h('span', {}, `✓ Up to date${editData.rendered_version != null ? ` · v${editData.rendered_version}` : ''}`);
  }
  nodes.push(h('button', {
    type: 'button',
    class: `ed-render-btn btn-primary${selected.kind === 'render' ? ' active' : ''}${renderActive() ? ' ed-rendering' : ''}${!renderActive() && !changeCount ? ' ed-up-to-date' : ''}`,
    title: 'First click shows what changed; click again (or press Enter) to render',
    onclick: () => {
      // First click opens the Render step so the director sees "what changed"; a second click renders.
      if (selected.kind === 'render' && !renderActive() && changeCount > 0) doRender();
      else selectStep('render');
    },
  }, renderLabel));
  return nodes;
}

function refreshStrip() {
  if (!shellRefs) return;
  shellRefs.stripEl.innerHTML = '';
  shellRefs.stripEl.append(...buildStrip());
}

// ---- lanes ------------------------------------------------------------------

function laneItemStyle(t0, t1) {
  const dur = planDuration() || 1;
  const left = Math.max(0, Math.min(100, (t0 / dur) * 100));
  const width = Math.max(0.4, Math.min(100 - left, ((t1 - t0) / dur) * 100));
  return `left:${left}%;width:${width}%`;
}
function lanePointStyle(t) {
  const dur = planDuration() || 1;
  const left = Math.max(0, Math.min(100, (t / dur) * 100));
  return `left:${left}%`;
}

function laneClickToSeek(e, laneEl) {
  const rect = laneEl.getBoundingClientRect();
  const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  seekTo(frac * planDuration());
}

function buildLanes() {
  const plan = editData.plan || {};
  const lanesEl = h('div', { class: 'ed-lanes' });

  function lane(name, key, items) {
    const body = h('div', {
      class: 'ed-lane-body',
      onclick: (e) => { if (e.target === body) laneClickToSeek(e, body); },
    }, items);
    return h('div', { class: 'ed-lane' }, h('div', { class: 'ed-lane-label muted small' }, name), body);
  }

  const cutItems = (plan.segments || []).map((seg) => h('div', {
    class: 'ed-lane-block ed-cut-block',
    style: laneItemStyle(seg.o, seg.o + (seg.b - seg.a)),
    title: `${fmtTime(seg.a)}–${fmtTime(seg.b)} (source)`,
    onclick: (e) => { e.stopPropagation(); selectStep('cut'); seekTo(seg.o); },
  }));
  const captionItems = (plan.captions || []).map((c) => h('div', {
    class: 'ed-lane-block ed-caption-block',
    style: laneItemStyle(c.t0, c.t1),
    title: c.text,
    onclick: (e) => { e.stopPropagation(); selectStep('captions', c.i); seekTo(c.t0); },
  }));
  const textItems = [];
  if (plan.title) {
    textItems.push(h('div', {
      class: 'ed-lane-block ed-text-block',
      style: laneItemStyle(plan.title.t0 ?? 0, plan.title.t1 ?? 0),
      title: 'Title',
      onclick: (e) => { e.stopPropagation(); selectStep('text', 'title'); seekTo(plan.title.t0 ?? 0); },
    }, 'Title'));
  }
  (plan.headlines || []).forEach((hl) => {
    textItems.push(h('div', {
      class: 'ed-lane-block ed-text-block',
      style: laneItemStyle(hl.t0, hl.t1),
      title: hl.id,
      onclick: (e) => { e.stopPropagation(); selectStep('text', hl.id); seekTo(hl.t0); },
    }, hl.id));
  });
  const momentItems = (plan.moments || []).map((m) => h('div', {
    class: 'ed-lane-block ed-moment-block',
    style: laneItemStyle(m.t0, m.t1),
    title: m.summary || m.kind,
    onclick: (e) => { e.stopPropagation(); selectStep('moments', m.id); seekTo(m.t0); },
  }, MOMENT_KIND_LABEL[m.kind] || m.kind));
  const soundItems = (plan.sfx || []).map((s) => h('div', {
    class: `ed-lane-dot ed-sound-dot${s.muted ? ' ed-muted' : ''}`,
    style: lanePointStyle(s.t),
    title: `${s.name} @ ${fmtTime(s.t)}${s.muted ? ' (muted)' : ''}`,
    onclick: (e) => { e.stopPropagation(); selectStep('sound', s.key); seekTo(s.t); },
  }));

  lanesEl.append(
    lane('Cut', 'cut', cutItems),
    lane('Captions', 'captions', captionItems),
    lane('Text', 'text', textItems),
    lane('Moments', 'moments', momentItems),
    lane('Sound', 'sound', soundItems));

  // The outer inset matches the lane-body column (offset past the lane labels); the inner bar's
  // `left` is then a plain 0–100% of that column's width, matching the lane-body percentages above.
  const playheadBar = h('div', { class: 'ed-lanes-playhead-bar' });
  const playheadInset = h('div', { class: 'ed-lanes-playhead' }, playheadBar);
  const wrap = h('div', { class: 'ed-lanes-wrap' }, lanesEl, playheadInset);
  return { wrap, playheadEl: playheadBar };
}

function refreshLanes() {
  if (!shellRefs) return;
  shellRefs.lanesMount.innerHTML = '';
  const { wrap, playheadEl } = buildLanes();
  shellRefs.lanesMount.appendChild(wrap);
  shellRefs.lanesPlayhead = playheadEl;
  updatePlayheadUI();
}

// ---- preview (rendered / draft) ---------------------------------------------

function latestVersionObj() {
  if (!clip || editData.rendered_version == null) return null;
  return (clip.versions || []).find((v) => v.n === editData.rendered_version) || null;
}

function buildPreviewArea() {
  if (!shellRefs) return;
  const mount = shellRefs.previewMount;
  mount.innerHTML = '';
  if (player) { player.destroy(); player = null; }

  const vObj = latestVersionObj();
  const toggle = h('div', { class: 'seg ed-preview-toggle' },
    h('button', {
      class: `seg-btn${previewMode === 'rendered' ? ' active' : ''}`,
      onclick: () => setPreviewMode('rendered'),
    }, vObj ? `Rendered v${vObj.n}` : 'Rendered'),
    h('button', {
      class: `seg-btn${previewMode === 'draft' ? ' active' : ''}`,
      onclick: () => setPreviewMode('draft'),
    }, 'Draft'));

  const frame = h('div', { class: 'phone-frame ed-preview-frame' });
  if (previewMode === 'rendered') {
    if (vObj) {
      player = createPlayer(frame, {
        src: vObj.media_url,
        aspect: '9/16',
        onTime: () => { playhead = player.time(); updatePlayheadUI(); },
      });
      player.seek(playhead);
    } else {
      frame.appendChild(h('div', { class: 'ed-preview-empty muted' }, 'No render yet — use Draft, or press Render below.'));
    }
  } else {
    const img = h('img', { class: 'ed-draft-img', alt: 'Draft preview' });
    const spinner = h('div', { class: 'ed-draft-spinner hidden' }, 'Loading…');
    const label = h('div', { class: 'ed-draft-label' }, 'Draft — not rendered yet');
    frame.appendChild(h('div', { class: 'ed-draft-wrap' }, img, spinner, label));
    shellRefs.draftImg = img;
    shellRefs.draftSpinner = spinner;
  }

  const scrub = h('input', {
    type: 'range', class: 'ed-scrub', min: '0', max: '1000', value: '0',
    oninput: (e) => {
      const frac = Number(e.target.value) / 1000;
      seekTo(frac * planDuration());
    },
  });
  const timeLabel = h('span', { class: 'ed-time muted small' }, '0:00.0 / 0:00.0');
  const transport = h('div', { class: 'ed-transport' }, scrub, timeLabel);

  mount.append(toggle, frame, transport);
  shellRefs.scrub = scrub;
  shellRefs.timeLabel = timeLabel;
  if (previewMode === 'draft') loadDraftStill();
  updatePlayheadUI();
}

// ---- "Ask Claude about this step" -------------------------------------------

async function sendStepComment(text) {
  if (!text.trim()) return;
  const label = KIND_LABEL[selected.kind] || 'Recipe';
  try {
    await post(`/api/clips/${clipId}/comments`, {
      version: editData.rendered_version ?? 0,
      t: playhead,
      text: `[${label}] ${text.trim()}`,
    });
    await post(`/api/clips/${clipId}/send`, {});
    toast('Sent to Claude');
  } catch (e) {
    toast(e.message, 'err');
  }
}

function buildAskClaude() {
  const ta = h('textarea', {
    class: 'textarea', rows: 2, placeholder: 'Ask Claude about this step…',
  });
  const send = h('button', {
    class: 'btn btn-sm',
    onclick: async () => {
      const text = ta.value;
      ta.value = '';
      await sendStepComment(text);
    },
  }, 'Send');
  ta.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      send.click();
    }
  });
  return h('div', { class: 'ed-ask-claude' }, ta, send);
}

// ---- built-in step editors ----------------------------------------------------

function fieldRow(label, node) {
  return h('div', { class: 'field' }, h('label', {}, label), node);
}

function mmss(sec) {
  return fmtTime(sec);
}

// Source (read-only)
function mountSourceStep(container, initCtx) {
  let ctx = initCtx;
  function render() {
    container.innerHTML = '';
    const { spec } = ctx;
    const segs = spec.cut?.segments || [];
    const total = segs.reduce((n, s) => n + Math.max(0, s.b - s.a), 0);
    container.append(
      h('div', { class: 'stack' },
        h('div', { class: 'field' },
          h('label', {}, 'Recording'),
          h('div', { class: 'row' },
            h('code', {}, spec.source?.file || '—'),
            clip?.workdir ? h('a', { class: 'btn-link', href: `#/clip/${clipId}` }, 'Open clip') : null)),
        h('div', { class: 'field' },
          h('label', {}, 'Kept ranges (source time)'),
          segs.length
            ? h('div', { class: 'stack', style: 'gap:4px' }, segs.map((s, i) => h('div', { class: 'row muted small' },
              `${i + 1}.`, ` ${mmss(s.a)} – ${mmss(s.b)}`, s.snap ? h('span', { class: 'chip' }, 'snaps') : null,
              s.mute ? h('span', { class: 'chip' }, 'muted') : null)))
            : h('div', { class: 'muted small' }, 'No ranges yet.')),
        h('div', { class: 'muted small' }, `Total kept: ${fmtDur(total)}`),
        h('div', { class: 'muted small' }, 'This step is read-only here — trim ranges in the Cut step.')));
  }
  render();
  return { update(newCtx) { ctx = newCtx; render(); }, destroy() { container.innerHTML = ''; } };
}

// Captions
function mountCaptionsStep(container, initCtx) {
  let ctx = initCtx;
  function ensureManualPhrases() {
    const { spec, plan } = ctx;
    if (spec.captions.mode === 'manual') return;
    const phrases = (plan.captions || []).map((c) => ({
      text: c.text,
      a: ctx.outToSrc(c.t0),
      b: ctx.outToSrc(c.t1),
    }));
    ctx.update((draft) => {
      draft.captions.mode = 'manual';
      draft.captions.phrases = phrases;
    }, 'Edit caption');
  }

  function render() {
    container.innerHTML = '';
    const { spec, plan } = ctx;
    const mode = spec.captions?.mode || 'auto';
    const hidden = !!spec.captions?.hidden;

    const modeBadge = h('span', { class: `pill ${mode === 'auto' ? 'pill-approved' : 'pill-queued'}` }, mode === 'auto' ? 'Auto' : 'Manual');
    const hideToggle = h('label', { class: 'checkbox' },
      h('input', {
        type: 'checkbox', checked: hidden,
        onchange: (e) => ctx.update((d) => { d.captions.hidden = e.target.checked; }, 'Hide captions'),
      }), h('span', {}, 'Hide captions'));
    const backAuto = mode === 'manual' ? h('button', {
      class: 'btn btn-sm',
      onclick: () => ctx.update((d) => { d.captions.mode = 'auto'; }, 'Back to auto captions'),
    }, 'Back to auto') : null;

    const rows = (plan.captions || []).map((c, idx) => {
      const ta = h('textarea', { class: 'textarea', rows: 1 }, c.text);
      ta.addEventListener('blur', () => {
        const text = ta.value.trim();
        if (text === c.text) return;
        ensureManualPhrases();
        ctx.update((d) => {
          if (d.captions.phrases[idx]) d.captions.phrases[idx].text = text;
        }, 'Edit caption text');
      });
      const merge = h('button', {
        class: 'btn-icon', title: 'Merge with next', 'aria-label': 'Merge with next',
        disabled: idx >= (plan.captions.length - 1),
        onclick: () => {
          ensureManualPhrases();
          ctx.update((d) => {
            const p = d.captions.phrases;
            if (!p[idx] || !p[idx + 1]) return;
            p[idx] = { text: `${p[idx].text} ${p[idx + 1].text}`.trim(), a: p[idx].a, b: p[idx + 1].b };
            p.splice(idx + 1, 1);
          }, 'Merge captions');
        },
      }, '⤵');
      const split = h('button', {
        class: 'btn-icon', title: 'Split at caret', 'aria-label': 'Split at caret',
        onclick: () => {
          const caret = ta.selectionStart ?? Math.floor(ta.value.length / 2);
          ensureManualPhrases();
          ctx.update((d) => {
            const p = d.captions.phrases[idx];
            if (!p) return;
            const words = p.text.split(/\s+/).filter(Boolean);
            const before = ta.value.slice(0, caret).trim();
            const splitIdx = Math.max(1, Math.min(words.length - 1, before.split(/\s+/).length || 1));
            const textA = words.slice(0, splitIdx).join(' ');
            const textB = words.slice(splitIdx).join(' ');
            if (!textA || !textB) return;
            const mid = p.a + (p.b - p.a) / 2;
            const newA = { text: textA, a: p.a, b: mid };
            const newB = { text: textB, a: mid, b: p.b };
            d.captions.phrases.splice(idx, 1, newA, newB);
          }, 'Split caption');
        },
      }, '✂');
      return h('div', { class: 'ed-caption-row', dataset: { i: String(c.i) } },
        h('span', { class: 'muted small ed-caption-time' }, mmss(c.t0)),
        ta,
        h('div', { class: 'row' }, split, merge));
    });

    container.append(
      h('div', { class: 'row' }, modeBadge, hideToggle, backAuto),
      h('div', { class: 'stack', style: 'gap:6px' }, rows.length ? rows : h('div', { class: 'muted small' }, 'No captions yet.')));
  }
  render();
  return { update(newCtx) { ctx = newCtx; render(); }, destroy() { container.innerHTML = ''; } };
}

// Text (title + headlines)
function stripTrailingPunct(s) {
  return s.replace(/[.,!?;:'")\]]+$/, '');
}

function wordChips(text, hl, onToggle) {
  // Tokenize while tracking each word's character span in `text`, then match `hl` by substring
  // (not by splitting both into arrays and comparing) — hl is often a clean phrase ("AI agent")
  // while the line's own last word may carry trailing punctuation ("agent?"), so a naive
  // words-array-equality check misses it. Any word whose span overlaps the matched range counts.
  const wordSpans = [];
  const re = /\S+/g;
  let m = re.exec(text);
  while (m) {
    wordSpans.push({ word: m[0], start: m.index, end: m.index + m[0].length });
    m = re.exec(text);
  }
  let hlStart = -1;
  let hlEnd = -1;
  if (hl) {
    const charStart = text.indexOf(hl);
    if (charStart >= 0) {
      const charEnd = charStart + hl.length;
      wordSpans.forEach((w, i) => {
        if (w.start < charEnd && w.end > charStart) {
          if (hlStart === -1) hlStart = i;
          hlEnd = i;
        }
      });
    }
  }
  // Shift-click extends the current highlight from its start to the clicked word (contiguous
  // selection). A plain click on the only highlighted word clears it; otherwise it becomes the
  // new (single-word) highlight.
  return h('div', { class: 'ed-word-chips' }, wordSpans.map(({ word }, i) => {
    const isHl = hlStart >= 0 && i >= hlStart && i <= hlEnd;
    return h('button', {
      type: 'button',
      class: `chip ed-word-chip${isHl ? ' active' : ''}`,
      onclick: (e) => {
        if (e.shiftKey && hlStart >= 0) {
          const lo = Math.min(hlStart, i);
          const hi = Math.max(hlStart, i);
          onToggle(stripTrailingPunct(wordSpans.slice(lo, hi + 1).map((w) => w.word).join(' ')));
        } else if (isHl && hlStart === i && hlEnd === i) {
          onToggle(null);
        } else {
          onToggle(stripTrailingPunct(word));
        }
      },
    }, word);
  }));
}

function timeFieldForSourceTime(label, srcTime, ctx, onSet) {
  const out = ctx.srcToOut(srcTime);
  const input = h('input', { class: 'input', style: 'width:100px', value: mmss(out) });
  input.addEventListener('blur', () => {
    const parsed = parseTimeLoose(input.value);
    if (parsed == null) return;
    onSet(ctx.outToSrc(parsed));
  });
  const setHere = h('button', { class: 'btn-icon', title: 'Set to playhead', onclick: () => onSet(ctx.outToSrc(ctx.time())) }, '⌖');
  const nudgeMinus = h('button', { class: 'btn-icon', title: '-0.1s', onclick: () => onSet(ctx.outToSrc(Math.max(0, out - 0.1))) }, '−');
  const nudgePlus = h('button', { class: 'btn-icon', title: '+0.1s', onclick: () => onSet(ctx.outToSrc(out + 0.1)) }, '+');
  return h('div', { class: 'row' }, h('span', { class: 'muted small' }, label), input, nudgeMinus, nudgePlus, setHere);
}
function parseTimeLoose(str) {
  str = String(str || '').trim();
  if (!str) return null;
  const parts = str.split(':').map((p) => parseFloat(p));
  if (parts.some((p) => Number.isNaN(p))) return null;
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return parts[0];
}

function mountTextStep(container, initCtx) {
  let ctx = initCtx;
  function render() {
    container.innerHTML = '';
    const { spec } = ctx;
    const title = spec.title;

    const titleCard = h('div', { class: 'ed-card' });
    titleCard.append(h('div', { class: 'ed-card-head' }, 'Title card'));
    if (!title || !title.lines) {
      titleCard.append(
        h('div', { class: 'muted small' }, 'No title.'),
        h('button', {
          class: 'btn btn-sm',
          onclick: () => ctx.update((d) => {
            d.title = { lines: [{ text: 'New title', hl: null }], until: ctx.outToSrc(ctx.time() + 3) };
          }, 'Add title'),
        }, 'Add title'));
    } else {
      title.lines.forEach((line, i) => {
        const ta = h('input', { class: 'input', value: line.text, style: 'width:100%' });
        ta.addEventListener('blur', () => {
          if (ta.value === line.text) return;
          ctx.update((d) => { d.title.lines[i].text = ta.value; }, 'Edit title text');
        });
        titleCard.append(
          h('div', { class: 'field' }, h('label', {}, `Line ${i + 1}`), ta),
          wordChips(line.text, line.hl, (hl) => ctx.update((d) => { d.title.lines[i].hl = hl; }, 'Highlight title word')));
      });
      titleCard.append(
        timeFieldForSourceTime('Until', title.until, ctx, (src) => ctx.update((d) => { d.title.until = src; }, 'Set title until')),
        h('button', {
          class: 'btn btn-ghost btn-sm',
          onclick: () => ctx.update((d) => { d.title = { lines: null, until: null }; }, 'Remove title'),
        }, 'Remove title'));
    }

    const headlinesWrap = h('div', { class: 'stack' });
    (spec.headlines || []).forEach((hset, hi) => {
      const card = h('div', { class: 'ed-card' });
      card.append(h('div', { class: 'ed-card-head row' },
        h('span', {}, hset.id),
        h('button', {
          class: 'btn-icon', title: 'Delete headline',
          onclick: () => ctx.update((d) => { d.headlines.splice(hi, 1); }, 'Delete headline'),
        }, '✕')));
      hset.lines.forEach((line, li) => {
        if (line.dim) {
          card.append(h('div', { class: 'row muted small ed-dim-row' },
            'dim marker',
            timeFieldForSourceTime('at', line.at, ctx, (src) => ctx.update((d) => { d.headlines[hi].lines[li].at = src; }, 'Move dim marker')),
            h('button', {
              class: 'btn-icon', title: 'Delete',
              onclick: () => ctx.update((d) => { d.headlines[hi].lines.splice(li, 1); }, 'Delete dim marker'),
            }, '✕')));
          return;
        }
        const input = h('input', { class: 'input', value: line.text, style: 'width:100%' });
        input.addEventListener('blur', () => {
          if (input.value === line.text) return;
          ctx.update((d) => { d.headlines[hi].lines[li].text = input.value; }, 'Edit headline text');
        });
        card.append(
          h('div', { class: 'row' },
            input,
            h('button', {
              class: 'btn-icon', title: 'Delete line',
              onclick: () => ctx.update((d) => { d.headlines[hi].lines.splice(li, 1); }, 'Delete headline line'),
            }, '✕')),
          wordChips(line.text, line.hl, (hl) => ctx.update((d) => { d.headlines[hi].lines[li].hl = hl; }, 'Highlight headline word')),
          timeFieldForSourceTime('at', line.at, ctx, (src) => ctx.update((d) => { d.headlines[hi].lines[li].at = src; }, 'Move headline line')));
      });
      card.append(h('div', { class: 'row' },
        h('button', {
          class: 'btn btn-sm',
          onclick: () => ctx.update((d) => {
            d.headlines[hi].lines.push({ text: 'New line', at: ctx.outToSrc(ctx.time()), hl: null });
          }, 'Add headline line'),
        }, '+ line'),
        h('button', {
          class: 'btn btn-sm btn-ghost',
          onclick: () => ctx.update((d) => {
            d.headlines[hi].lines.push({ dim: true, at: ctx.outToSrc(ctx.time()) });
          }, 'Add dim marker'),
        }, '+ dim marker')));
      card.append(timeFieldForSourceTime('Until', hset.until, ctx, (src) => ctx.update((d) => { d.headlines[hi].until = src; }, 'Set headline until')));
      headlinesWrap.append(card);
    });

    const addHeadlineBtn = h('button', {
      class: 'btn btn-primary btn-sm',
      onclick: () => ctx.update((d) => {
        d.headlines = d.headlines || [];
        const n = d.headlines.length + 1;
        const at = ctx.outToSrc(ctx.time());
        d.headlines.push({
          id: `h${n}`,
          until: ctx.outToSrc(ctx.time() + 3),
          lines: [{ text: 'New headline', at, hl: null }],
        });
      }, 'Add headline'),
    }, '+ Add headline at playhead');

    container.append(titleCard, h('div', { class: 'ed-card-head' }, 'Headlines'), headlinesWrap, addHeadlineBtn);
  }
  render();
  return { update(newCtx) { ctx = newCtx; render(); }, destroy() { container.innerHTML = ''; } };
}

// Sound
function mountSoundStep(container, initCtx) {
  let ctx = initCtx;
  function render() {
    container.innerHTML = '';
    const { spec, plan } = ctx;
    const sound = spec.sound || {};
    const autoToggle = h('label', { class: 'checkbox' },
      h('input', {
        type: 'checkbox', checked: sound.auto !== false,
        onchange: (e) => ctx.update((d) => { d.sound.auto = e.target.checked; }, 'Toggle auto SFX'),
      }), h('span', {}, 'Auto SFX'));

    const gainSlider = h('input', {
      type: 'range', min: '-12', max: '6', step: '0.5', value: String(sound.sfx_gain_db ?? 0),
    });
    const gainLabel = h('span', { class: 'muted small' }, `${sound.sfx_gain_db ?? 0} dB`);
    gainSlider.addEventListener('input', () => { gainLabel.textContent = `${gainSlider.value} dB`; });
    gainSlider.addEventListener('change', () => ctx.update((d) => { d.sound.sfx_gain_db = Number(gainSlider.value); }, 'SFX volume'));

    const lufsSel = h('select', { class: 'select' }, [-14, -16, -17, -18].map((v) => h('option', {
      value: String(v), selected: (sound.voice_lufs ?? -17) === v,
    }, `${v} LUFS`)));
    lufsSel.addEventListener('change', () => ctx.update((d) => { d.sound.voice_lufs = Number(lufsSel.value); }, 'Voice loudness'));

    const muted = new Set(sound.muted || []);
    const events = (plan.sfx || []).map((s) => {
      const isMuted = muted.has(s.key);
      return h('div', { class: 'row ed-sfx-row' },
        h('span', { class: 'muted small', style: 'width:60px' }, mmss(s.t)),
        h('span', { style: 'flex:1' }, s.name),
        h('button', { class: 'btn-icon', title: 'Play here', onclick: () => ctx.seek(s.t) }, '▶'),
        h('label', { class: 'checkbox' },
          h('input', {
            type: 'checkbox', checked: isMuted,
            onchange: (e) => ctx.update((d) => {
              d.sound.muted = d.sound.muted || [];
              const idx = d.sound.muted.indexOf(s.key);
              if (e.target.checked && idx === -1) d.sound.muted.push(s.key);
              if (!e.target.checked && idx !== -1) d.sound.muted.splice(idx, 1);
            }, 'Mute sound'),
          }), h('span', {}, 'Mute')));
    });

    container.append(
      h('div', { class: 'row' }, autoToggle),
      fieldRow('SFX volume', h('div', { class: 'row' }, gainSlider, gainLabel)),
      fieldRow('Voice loudness', lufsSel),
      h('div', { class: 'field' }, h('label', {}, 'Sound events'),
        events.length ? h('div', { class: 'stack', style: 'gap:4px' }, events) : h('div', { class: 'muted small' }, 'No sounds yet.')));
  }
  render();
  return { update(newCtx) { ctx = newCtx; render(); }, destroy() { container.innerHTML = ''; } };
}

// Render
function mountRenderStep(container, initCtx) {
  let ctx = initCtx;
  function render() {
    container.innerHTML = '';
    const changes = editData.changes || [];
    const job = renderJob();
    const noteTa = h('textarea', { class: 'textarea', rows: 2, placeholder: 'Optional note for this version…' }, renderNote);
    noteTa.addEventListener('input', () => { renderNote = noteTa.value; });

    const nextV = (editData.rendered_version == null ? 0 : editData.rendered_version) + 1;
    const renderBtn = h('button', {
      class: 'btn btn-primary',
      disabled: renderActive(),
      onclick: () => doRender(),
    }, renderActive() ? 'Rendering…' : `▶ Render v${nextV} · ${changes.length} change${changes.length === 1 ? '' : 's'}`);

    const progress = renderActive()
      ? h('div', { class: 'ed-progress' }, h('div', {
        class: 'ed-progress-bar', style: `width:${Math.round(progressFrac(job.progress) * 100)}%`,
      }))
      : null;
    if (job.state === 'error') {
      container.append(h('div', { class: 'agent-line agent-error' }, job.message || 'Render failed'));
    }

    const history = (clip?.versions || []).slice().sort((a, b) => b.n - a.n).map((v) => {
      const notesEl = h('div', { class: 'change-notes small' });
      notesEl.innerHTML = md(v.notes || '_No changelog._');
      return h('div', { class: 'change-item' },
        h('div', { class: 'change-head' }, `v${v.n} · ${relTime(v.created)} · ${fmtDur(v.duration)}`),
        notesEl);
    });

    // Element.append() (unlike the h() helper's own child handling) stringifies a bare `null`
    // into the literal text "null", so any conditionally-null node must be filtered out first.
    container.append(...[
      h('div', { class: 'field' }, h('label', {}, 'What changed'),
        changes.length
          ? h('ul', { class: 'ed-change-list' }, changes.map((c) => h('li', {}, c)))
          : h('div', { class: 'muted small' }, 'Nothing changed since the last render.')),
      fieldRow('Note (optional)', noteTa),
      h('div', { class: 'row' }, renderBtn, h('a', { class: 'btn btn-ghost', href: `#/clip/${clipId}` }, 'Open Review')),
      progress,
      h('div', { class: 'field' }, h('label', {}, 'Past versions'),
        history.length ? h('div', { class: 'changes-list' }, history) : h('div', { class: 'muted small' }, 'No versions yet.')),
    ].filter(Boolean));
  }
  render();
  return { update(newCtx) { ctx = newCtx; render(); }, destroy() { container.innerHTML = ''; } };
}

// ---- Cut / Moments (external modules, imported with fallback) --------------

let cutModuleApi = null;
let momentsModuleApi = null;

function placeholderStep(container, name) {
  container.innerHTML = '';
  container.append(h('div', { class: 'empty-state' },
    h('div', {}, `The ${name} editor couldn't load.`),
    h('div', { class: 'muted small' }, 'It may still be in progress. Try refreshing in a bit.')));
  return { update() {}, destroy() { container.innerHTML = ''; } };
}

async function loadExternalModules() {
  try {
    cutModuleApi = await import('./edit-cut.js');
  } catch (e) {
    cutModuleApi = null;
  }
  try {
    momentsModuleApi = await import('./edit-moments.js');
  } catch (e) {
    momentsModuleApi = null;
  }
}

// ---- ctx / step mounting -----------------------------------------------------

function buildCtx() {
  return {
    clip,
    spec: editData.spec,
    plan: editData.plan,
    words: (wordsData && wordsData.words) || [],  // the step modules take the plain [[w, s, e], …] list
    selected,
    update: doUpdate,
    select: selectStep,
    seek: seekTo,
    time: () => playhead,
    play: () => { if (previewMode === 'rendered' && player) player.play(); },
    pause: () => { if (previewMode === 'rendered' && player) player.pause(); },
    srcToOut,
    outToSrc,
    refreshStill: scheduleStillRefresh,
    api: {
      get, post, put, patch, del,
    },
  };
}

function mountAllSteps() {
  stepModules = {};
  const ctx = buildCtx();
  stepModules.source = mountSourceStep(shellRefs.stepContainers.source, ctx);
  stepModules.captions = mountCaptionsStep(shellRefs.stepContainers.captions, ctx);
  stepModules.text = mountTextStep(shellRefs.stepContainers.text, ctx);
  stepModules.sound = mountSoundStep(shellRefs.stepContainers.sound, ctx);
  stepModules.render = mountRenderStep(shellRefs.stepContainers.render, ctx);
  if (cutModuleApi && typeof cutModuleApi.mountCutStep === 'function') {
    try {
      stepModules.cut = cutModuleApi.mountCutStep(shellRefs.stepContainers.cut, ctx);
    } catch (e) {
      stepModules.cut = placeholderStep(shellRefs.stepContainers.cut, 'Cut');
    }
  } else {
    stepModules.cut = placeholderStep(shellRefs.stepContainers.cut, 'Cut');
  }
  if (momentsModuleApi && typeof momentsModuleApi.mountMomentsStep === 'function') {
    try {
      stepModules.moments = momentsModuleApi.mountMomentsStep(shellRefs.stepContainers.moments, ctx);
    } catch (e) {
      stepModules.moments = placeholderStep(shellRefs.stepContainers.moments, 'Moments');
    }
  } else {
    stepModules.moments = placeholderStep(shellRefs.stepContainers.moments, 'Moments');
  }
}

function notifyModules() {
  const ctx = buildCtx();
  Object.values(stepModules).forEach((m) => {
    try { m.update(ctx); } catch (e) { /* step module error is non-fatal to the shell */ }
  });
}

function showSelectedStep() {
  if (!shellRefs) return;
  ALL_STEP_KEYS.forEach((key) => {
    shellRefs.stepContainers[key].classList.toggle('hidden', key !== selected.kind);
  });
  shellRefs.stepTitleEl.textContent = KIND_LABEL[selected.kind];
  shellRefs.askLabel.textContent = `Ask Claude about this step — ${KIND_LABEL[selected.kind]}`;
}

// ---- render job (POST /render, poll GET /render) ------------------------------

// The backend reports render progress as 0–100; accept 0–1 too.
function progressFrac(p) {
  const v = Number(p) || 0;
  return Math.max(0, Math.min(1, v > 1 ? v / 100 : v));
}

async function doRender() {
  try {
    await post(`/api/clips/${clipId}/render`, { note: renderNote || undefined });
    renderNote = '';
    editData.job = { state: 'running', progress: 0 };
    refreshAll();
    schedulePollRender();
  } catch (e) {
    toast(e.message, 'err');
  }
}

function schedulePollRender() {
  clearTimeout(renderPollTimer);
  renderPollTimer = setTimeout(pollRender, 700);
}

async function pollRender() {
  if (!clipId) return;
  try {
    const res = await get(`/api/clips/${clipId}/render`);
    const job = res.job || { state: 'idle' };
    const wasActive = renderActive();
    editData.job = job;
    if (job.state === 'running' || job.state === 'queued') {
      refreshAll();
      schedulePollRender();
      return;
    }
    if (job.state === 'done') {
      toast(`v${job.version} ready — open Review to check it`, 'ok');
      await Promise.all([loadClip(), loadEdit()]);
      refreshAll();
    } else if (job.state === 'error') {
      toast(job.message || 'Render failed', 'err');
      refreshAll();
    } else if (wasActive) {
      refreshAll();
    }
  } catch (e) {
    /* transient — the periodic edit poll will recover */
  }
}

// ---- shell build / refresh ---------------------------------------------------

function buildHeader() {
  const modeSwitch = h('div', { class: 'seg ed-mode-switch' },
    h('a', { class: 'seg-btn', href: `#/clip/${clipId}` }, 'Review'),
    h('span', { class: 'seg-btn active' }, 'Edit'));
  return h('div', { class: 'ed-header' },
    h('div', { class: 'row', style: 'justify-content:space-between' },
      h('h2', {}, clip?.title || clipId),
      modeSwitch),
    h('div', { class: 'muted small' }, clip?.batch || ''));
}

function buildShell() {
  root.innerHTML = '';

  const header = buildHeader();
  const stripEl = h('div', { class: 'ed-strip' });

  const previewMount = h('div', { class: 'ed-preview' });
  const lanesMount = h('div', {});
  const left = h('div', { class: 'ed-left' }, previewMount, lanesMount);

  const stepContainers = {};
  ALL_STEP_KEYS.forEach((key) => {
    stepContainers[key] = h('div', { class: `ed-step-panel${key === selected.kind ? '' : ' hidden'}` });
  });
  const stepMount = h('div', { class: 'ed-step-mount' }, ALL_STEP_KEYS.map((k) => stepContainers[k]));
  const askLabel = h('div', { class: 'ed-ask-label muted small' }, 'Ask Claude about this step');
  const askClaude = buildAskClaude();
  const saveStatusEl = h('div', { class: 'ed-save-status muted small' }, '');
  const stepTitleEl = h('div', { class: 'ed-step-title' }, KIND_LABEL[selected.kind]);
  const right = h('div', { class: 'ed-right panel' },
    h('div', { class: 'row', style: 'justify-content:space-between;padding:8px 12px' },
      stepTitleEl, saveStatusEl),
    stepMount,
    h('div', { class: 'ed-ask-wrap' }, askLabel, askClaude));

  root.append(header, h('div', { class: 'ed-strip-row' }, stripEl), h('div', { class: 'ed-layout' }, left, right));

  shellRefs = {
    stripEl, previewMount, lanesMount, stepContainers, askLabel, saveStatusEl, stepTitleEl,
  };

  mountAllSteps();
  buildPreviewArea();
  refreshLanes();
  refreshStrip();
  showSelectedStep();
  loadWords();
}

function refreshAll() {
  if (!shellRefs || !editData) return;
  refreshStrip();
  refreshLanes();
  notifyModules();
}

// ---- no-recipe state ----------------------------------------------------------

function renderNoRecipe() {
  root.innerHTML = '';
  const cameFromIdea = clipCameFromIdea(clip);
  root.append(
    buildHeader(),
    h('div', { class: 'empty-state large' },
      h('div', { class: 'empty-icon' }, '🧩'),
      h('div', {}, 'This clip was made before recipes.'),
      h('div', { class: 'muted', style: 'max-width:420px' },
        cameFromIdea
          ? 'It came from an approved idea, so a rough-cut recipe can be built from its source ranges.'
          : "It wasn't made from an idea's source ranges, so there's nothing to build a recipe from automatically. Ask Claude to convert it, or start a new clip from an idea."),
      cameFromIdea ? h('button', {
        class: 'btn btn-primary',
        onclick: async () => {
          try {
            editData = await post(`/api/clips/${clipId}/edit/rough-cut`, {});
            noRecipe = false;
            await loadExternalModules();
            buildShell();
            schedulePoll();
          } catch (e) {
            toast(e.message, 'err');
          }
        },
      }, 'Build rough-cut recipe') : null,
      h('a', { class: 'btn btn-ghost', href: `#/clip/${clipId}` }, 'Back to Review')));
}

// ---- keyboard -----------------------------------------------------------------

function isTyping(e) {
  const t = e.target;
  return !!(t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable));
}

function handleKeydown(e) {
  // Enter in a one-line field saves it (fields commit on blur), like people expect from a form.
  if (e.key === 'Enter' && e.target && e.target.tagName === 'INPUT' && !e.isComposing) {
    e.preventDefault();
    e.target.blur();
    return;
  }
  if (isTyping(e) && e.key !== 'Escape') return;
  if ((e.metaKey || e.ctrlKey) && (e.key === 'z' || e.key === 'Z')) {
    e.preventDefault();
    if (e.shiftKey) redo(); else undo();
    return;
  }
  if (e.key === 'Escape') { selected = { kind: selected.kind, id: null }; return; }
  switch (e.key) {
    case ' ':
      e.preventDefault();
      if (previewMode === 'rendered' && player) player.toggle();
      break;
    case 'ArrowLeft': seekTo(playhead - 1); break;
    case 'ArrowRight': seekTo(playhead + 1); break;
    case 'j': case 'J': seekTo(playhead - 5); break;
    case 'l': case 'L': seekTo(playhead + 5); break;
    case '1': selectStep('source'); break;
    case '2': selectStep('cut'); break;
    case '3': selectStep('captions'); break;
    case '4': selectStep('text'); break;
    case '5': selectStep('moments'); break;
    case '6': selectStep('sound'); break;
    case '7': selectStep('render'); break;
    case 'Enter':
      if (selected.kind === 'render') doRender();
      break;
    default: break;
  }
}

// ---- polling --------------------------------------------------------------------

// GET /edit is re-polled every 2s only while a render job is running (schedulePollRender already
// runs at 700ms while active, which covers this); otherwise this view relies on the shell's
// /api/state poll (onState below) to notice changes made elsewhere.
function schedulePoll() {
  if (renderActive()) schedulePollRender();
}

// ---- lifecycle ------------------------------------------------------------------

async function mountEdit(el, params, query) {
  root = el;
  root.className = 'view-edit';
  clipId = params.id;
  clip = null;
  editData = null;
  noRecipe = false;
  wordsData = null;
  const STEPS = ['source', 'cut', 'captions', 'text', 'moments', 'sound', 'render'];
  const wanted = query && typeof query.get === 'function' ? query.get('step') : null;
  selected = { kind: STEPS.includes(wanted) ? wanted : 'source', id: null };  // #/edit/<id>?step=cut deep-links a step
  previewMode = 'rendered';
  playhead = 0;
  undoStack = [];
  redoStack = [];
  renderNote = '';
  shellRefs = null;
  stepModules = {};

  root.innerHTML = '';
  root.appendChild(h('div', { class: 'empty-state' }, 'Loading…'));

  await loadExternalModules();

  try {
    await loadClip();
    await loadEdit();
  } catch (e) {
    toast(`Failed to load: ${e.message}`, 'err');
    root.innerHTML = '';
    root.appendChild(h('div', { class: 'empty-state' }, `Couldn't load this clip: ${e.message}`));
    return;
  }

  document.addEventListener('keydown', handleKeydown);

  if (noRecipe) {
    renderNoRecipe();
    return;
  }
  buildShell();
  schedulePoll();
}

function unmountEdit() {
  document.removeEventListener('keydown', handleKeydown);
  clearTimeout(renderPollTimer);
  if (player) { player.destroy(); player = null; }
  if (lanesCleanup) { lanesCleanup(); lanesCleanup = null; }
  Object.values(stepModules).forEach((m) => { try { m.destroy(); } catch (e) { /* ignore */ } });
  stepModules = {};
  root = null;
  shellRefs = null;
}

registerView('edit', {
  mount: mountEdit,
  unmount: unmountEdit,
  onState(state) {
    // Reload the recipe when this clip's summary changes elsewhere (e.g. Claude registered a
    // version from a headless run) — but never while a render we started is actively polling,
    // to avoid fighting our own faster 700ms loop.
    if (!clip || renderActive()) return;
    const summary = (state?.clips || []).find((c) => c.id === clipId);
    if (summary && clip.updated && summary.updated && summary.updated !== clip.updated) {
      loadClip().then(() => loadEdit()).then(() => refreshAll()).catch(() => {});
    }
  },
});
