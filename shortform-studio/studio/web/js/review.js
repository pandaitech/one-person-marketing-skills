// review.js — the review loop: player + timeline + versions on the left,
// Notes/Changes/Brief/Log on the right, send/approve/next on a sticky bottom bar.
// #/review resolves to the first clip in the review queue (or an empty state).
// #/clip/<id>?v=n opens a specific clip.

import { registerView, navigate, getState, refresh } from './app.js';
import { get, post, patch, del } from './api.js';
import {
  h, fmtTime, fmtDur, relTime, md, toast, copy, escapeHtml,
} from './util.js';
import { createPlayer } from './player.js';

// ---- module state -----------------------------------------------------

let root = null;
let clipId = null;
let clip = null;
let currentVersion = null;
let compareVersion = null;
let activeTab = 'notes';

let player = null;
let comparePlayer = null;
let pollTimer = null;
let logTimer = null;
let logText = '';
let briefBuilt = false;
let newVersionBanner = null;
let helpVisible = false;

let composerCaptured = null;
let composerWhole = false;
let composerTa = null;
let composerChipEl = null;

let shellRefs = null;
let timelineRefs = null;
let timelineCleanup = null;

// ---- small helpers ------------------------------------------------------

function versionsSorted() {
  return (clip?.versions || []).slice().sort((a, b) => a.n - b.n);
}
function currentVersionObj() {
  return (clip?.versions || []).find((v) => v.n === currentVersion) || null;
}
function directorInitial() {
  return (getState()?.settings?.director_name || 'F')[0].toUpperCase();
}
function editorInitial() {
  return (getState()?.settings?.editor_name || 'C')[0].toUpperCase();
}

function reviewQueueFromState(state) {
  const clips = state?.clips || [];
  return clips
    .filter((c) => c.status === 'review' || (c.open && c.open.draft > 0))
    .sort((a, b) => {
      if (!!a.new_version !== !!b.new_version) return a.new_version ? -1 : 1;
      return new Date(b.updated || 0) - new Date(a.updated || 0);
    });
}

async function autoAdvance() {
  await refresh();
  const state = getState();
  const queue = reviewQueueFromState(state).filter((c) => c.id !== clipId);
  if (queue.length) navigate(`#/clip/${queue[0].id}`);
  else navigate('#/');
}

// ---- data actions ---------------------------------------------------------

async function loadClip() {
  try {
    const data = await get(`/api/clips/${clipId}`);
    const isNewClip = !clip;
    const prevLatest = clip ? Math.max(0, ...(clip.versions || []).map((v) => v.n)) : null;
    clip = data;
    const newLatest = Math.max(0, ...(clip.versions || []).map((v) => v.n));
    if (isNewClip) {
      currentVersion = newLatest;
      briefBuilt = false;
      buildShell();
      markSeen(currentVersion);
    } else {
      if (prevLatest != null && newLatest > prevLatest && newLatest !== currentVersion) {
        newVersionBanner = newLatest;
      }
      updateAll();
    }
  } catch (e) {
    toast(`Failed to load clip: ${e.message}`, 'err');
  }
}

async function markSeen(n) {
  if (!clip) return;
  try {
    await post(`/api/clips/${clip.id}/seen`, { version: n });
    if (clip.director_seen_version == null || n > clip.director_seen_version) {
      clip.director_seen_version = n;
    }
    updateVersionTabs();
  } catch (e) {
    /* non-fatal */
  }
}

async function sendNotes() {
  try {
    const res = await post(`/api/clips/${clip.id}/send`, {});
    toast(res && res.dispatched ? 'Notes sent · dispatched' : 'Notes sent to editor');
    await autoAdvance();
  } catch (e) {
    toast(e.message, 'err');
  }
}
async function approveCurrent() {
  try {
    await post(`/api/clips/${clip.id}/approve`, { version: currentVersion });
    toast(`Approved v${currentVersion}`);
    await autoAdvance();
  } catch (e) {
    toast(e.message, 'err');
  }
}
async function unapprove() {
  try {
    await post(`/api/clips/${clip.id}/unapprove`, {});
    toast('Unapproved');
    await loadClip();
  } catch (e) {
    toast(e.message, 'err');
  }
}
async function dispatchClip() {
  try {
    await post(`/api/clips/${clip.id}/dispatch`, {});
    toast('Dispatched');
    await loadClip();
  } catch (e) {
    toast(e.message, 'err');
  }
}
async function nextClip() {
  await autoAdvance();
}

async function submitDraftNote() {
  const text = composerTa.value.trim();
  if (!text) return;
  const t = composerWhole ? null : (composerCaptured != null ? composerCaptured : player.time());
  try {
    await post(`/api/clips/${clip.id}/comments`, { version: currentVersion, t, text, author: 'director' });
    composerTa.value = '';
    composerCaptured = null;
    composerWhole = false;
    updateComposerChip();
    await loadClip();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function deleteDraft(comment) {
  try {
    await del(`/api/clips/${clip.id}/comments/${comment.id}`);
    await loadClip();
  } catch (e) {
    toast(e.message, 'err');
  }
}
async function resolveComment(comment) {
  try {
    await patch(`/api/clips/${clip.id}/comments/${comment.id}`, { status: 'resolved' });
    await loadClip();
  } catch (e) {
    toast(e.message, 'err');
  }
}
async function reopenComment(comment) {
  try {
    await patch(`/api/clips/${clip.id}/comments/${comment.id}`, { status: 'draft' });
    await loadClip();
  } catch (e) {
    toast(e.message, 'err');
  }
}
function editDraft(comment) {
  if (!shellRefs) return;
  const row = shellRefs.notesGroupsEl.querySelector(`[data-note-id="${comment.id}"] .note-text`);
  if (!row) return;
  const ta = h('textarea', { class: 'textarea' }, comment.text);
  row.replaceWith(ta);
  ta.focus();
  ta.addEventListener('blur', async () => {
    const text = ta.value.trim();
    if (text && text !== comment.text) {
      try {
        await patch(`/api/clips/${clip.id}/comments/${comment.id}`, { text });
        await loadClip();
      } catch (e) {
        toast(e.message, 'err');
      }
    } else {
      const back = h('div', { class: 'note-text' });
      back.innerHTML = md(comment.text);
      ta.replaceWith(back);
    }
  });
}

// ---- version / compare -----------------------------------------------------

function switchVersion(n) {
  const vObj = clip.versions.find((v) => v.n === n);
  if (!vObj) return;
  currentVersion = n;
  player.setSrc(vObj.media_url, false);
  updateTimeline();
  updateVersionTabs();
  updateHeader();
  updateActionBar();
  if (compareVersion != null) {
    if (comparePlayer) comparePlayer.seek(0);
  }
  markSeen(n);
}
function prevVersion() {
  const vs = versionsSorted();
  const idx = vs.findIndex((v) => v.n === currentVersion);
  if (idx > 0) switchVersion(vs[idx - 1].n);
}
function nextVersion() {
  const vs = versionsSorted();
  const idx = vs.findIndex((v) => v.n === currentVersion);
  if (idx >= 0 && idx < vs.length - 1) switchVersion(vs[idx + 1].n);
}

function toggleCompare(on) {
  if (on) {
    if (compareVersion == null) {
      const vs = versionsSorted().filter((v) => v.n !== currentVersion);
      compareVersion = vs.length ? vs[vs.length - 1].n : null;
    }
  } else {
    compareVersion = null;
  }
  renderCompareRow();
  updateVersionTabs();
}
function setCompareVersion(n) {
  compareVersion = n;
  const vObj = clip.versions.find((v) => v.n === n);
  if (comparePlayer) comparePlayer.setSrc(vObj ? vObj.media_url : '', false);
}
function renderCompareRow() {
  if (!shellRefs) return;
  const row = shellRefs.compareRow;
  row.innerHTML = '';
  if (compareVersion == null) {
    row.classList.add('hidden');
    if (comparePlayer) {
      comparePlayer.destroy();
      comparePlayer = null;
    }
    return;
  }
  row.classList.remove('hidden');
  const select = h('select', { class: 'select' }, versionsSorted().map((v) => h('option', {
    value: String(v.n), selected: v.n === compareVersion,
  }, v.n === 0 ? 'v0 · original' : `v${v.n}`)));
  select.addEventListener('change', () => setCompareVersion(parseInt(select.value, 10)));
  const mount = h('div', { class: 'phone-frame phone-frame-small' });
  row.append(h('div', { class: 'compare-head' }, h('span', { class: 'muted small' }, 'Compare with'), select), mount);
  const vObj = clip.versions.find((v) => v.n === compareVersion);
  comparePlayer = createPlayer(mount, { src: vObj ? vObj.media_url : '', aspect: '9/16' });
  comparePlayer.seek(player.time());
}

// ---- timeline -----------------------------------------------------------

function timelineMarkers(duration) {
  if (!duration) return [];
  return (clip.comments || [])
    .filter((c) => c.version === currentVersion && c.parent == null && c.t != null)
    .map((c) => h('button', {
      type: 'button',
      class: `timeline-marker marker-${c.status}`,
      style: { left: `${Math.min(100, Math.max(0, (c.t / duration) * 100))}%` },
      title: `${fmtTime(c.t)} · ${c.text}`,
      'aria-label': `Note at ${fmtTime(c.t)}`,
      onclick: (e) => { e.stopPropagation(); seekToComment(c); },
    }));
}

function buildTimeline() {
  const wrap = h('div', { class: 'timeline' });
  const filmstripEl = h('div', { class: 'timeline-filmstrip' });
  const waveformEl = h('div', { class: 'timeline-waveform' });
  const markersEl = h('div', { class: 'timeline-markers' });
  const playheadEl = h('div', { class: 'timeline-playhead' });
  const tooltipTimeEl = h('div', { class: 'timeline-tooltip-time' });
  const tooltipEl = h('div', { class: 'timeline-tooltip hidden' }, tooltipTimeEl);
  wrap.append(filmstripEl, waveformEl, markersEl, playheadEl, tooltipEl);

  function fracFromEvent(e) {
    const rect = wrap.getBoundingClientRect();
    return Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  }
  function seekFromEvent(e) {
    const duration = player.duration() || currentVersionObj()?.duration || 0;
    if (!duration) return;
    seekTo(fracFromEvent(e) * duration);
  }
  let dragging = false;
  wrap.addEventListener('mousedown', (e) => { dragging = true; seekFromEvent(e); });
  const onMove = (e) => { if (dragging) seekFromEvent(e); };
  const onUp = () => { dragging = false; };
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
  timelineCleanup = () => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
  };

  wrap.addEventListener('mousemove', (e) => {
    const duration = player.duration() || currentVersionObj()?.duration || 0;
    if (!duration) return;
    const frac = fracFromEvent(e);
    const t = frac * duration;
    const tileIndex = Math.min(59, Math.max(0, Math.floor(frac * 60)));
    const vObj = currentVersionObj();
    tooltipEl.style.left = `${frac * 100}%`;
    tooltipEl.style.backgroundImage = vObj?.filmstrip_url ? `url(${vObj.filmstrip_url})` : '';
    tooltipEl.style.backgroundPositionX = `-${tileIndex * 72}px`;
    tooltipTimeEl.textContent = fmtTime(t);
    tooltipEl.classList.remove('hidden');
  });
  wrap.addEventListener('mouseleave', () => tooltipEl.classList.add('hidden'));

  timelineRefs = {
    wrap, filmstripEl, waveformEl, markersEl, playheadEl, tooltipEl, tooltipTimeEl,
  };
  return wrap;
}

function updateTimeline() {
  if (!timelineRefs) return;
  const vObj = currentVersionObj();
  const duration = (player && player.duration()) || vObj?.duration || 0;
  timelineRefs.filmstripEl.style.backgroundImage = vObj?.filmstrip_url ? `url(${vObj.filmstrip_url})` : '';
  timelineRefs.waveformEl.style.backgroundImage = vObj?.waveform_url ? `url(${vObj.waveform_url})` : '';
  timelineRefs.markersEl.innerHTML = '';
  timelineRefs.markersEl.append(...timelineMarkers(duration));
  updatePlayheadPosition();
}
function updatePlayheadPosition() {
  if (!timelineRefs || !player) return;
  const duration = player.duration() || currentVersionObj()?.duration || 0;
  const frac = duration ? player.time() / duration : 0;
  timelineRefs.playheadEl.style.left = `${Math.min(100, Math.max(0, frac * 100))}%`;
}
function seekTo(t) {
  player.seek(t);
  if (comparePlayer) comparePlayer.seek(t);
  updatePlayheadPosition();
}
function seekToComment(comment) {
  if (comment.version !== currentVersion) switchVersion(comment.version);
  if (comment.t != null) seekTo(comment.t);
  setActiveTab('notes');
  highlightNote(comment.id);
}
function highlightNote(id) {
  requestAnimationFrame(() => {
    const el = shellRefs?.notesGroupsEl?.querySelector(`[data-note-id="${id}"]`);
    if (el) {
      el.classList.add('highlight');
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      setTimeout(() => el.classList.remove('highlight'), 1500);
    }
  });
}

function onPlayerTime() {
  updatePlayheadPosition();
  if (composerCaptured == null && !composerWhole) updateComposerChip();
  if (comparePlayer && comparePlayer.video && player.video
      && comparePlayer.video.playbackRate !== player.video.playbackRate) {
    comparePlayer.video.playbackRate = player.video.playbackRate;
  }
}

// ---- composer -------------------------------------------------------------

function updateComposerChip() {
  if (!composerChipEl) return;
  if (composerWhole) {
    composerChipEl.textContent = 'Whole video';
  } else {
    const t = composerCaptured != null ? composerCaptured : (player ? player.time() : 0);
    composerChipEl.textContent = `at ${fmtTime(t)} · v${currentVersion}`;
  }
}
function toggleComposerWhole() {
  if (composerWhole) {
    composerWhole = false;
    composerCaptured = player.time();
  } else {
    composerWhole = true;
  }
  updateComposerChip();
}
function focusComposerAtPlayhead() {
  if (!composerTa) return;
  composerCaptured = player.time();
  composerWhole = false;
  updateComposerChip();
  composerTa.focus();
}

// ---- notes tab --------------------------------------------------------------

function noteItem(comment, all) {
  const replies = all.filter((c) => c.parent === comment.id);
  const chip = h('button', { type: 'button', class: 'chip chip-time', onclick: () => seekToComment(comment) },
    comment.t != null ? `v${comment.version} · ${fmtTime(comment.t)}` : `v${comment.version} · whole`);

  const actions = [];
  if (comment.status === 'draft') {
    actions.push(h('button', { class: 'btn-icon', 'aria-label': 'Edit note', onclick: () => editDraft(comment) }, '✎'));
    actions.push(h('button', { class: 'btn-icon', 'aria-label': 'Delete note', onclick: () => deleteDraft(comment) }, '✕'));
  } else if (comment.status === 'addressed') {
    actions.push(h('button', { class: 'btn btn-sm btn-primary', onclick: () => resolveComment(comment) }, '✓ Resolve'));
    actions.push(h('button', { class: 'btn btn-sm btn-ghost', onclick: () => reopenComment(comment) }, '↺ Reopen'));
  }

  const textEl = h('div', { class: 'note-text' });
  textEl.innerHTML = md(comment.text);

  const avatarChar = comment.author === 'editor' ? editorInitial() : directorInitial();

  return h('div', { class: `note-item note-${comment.status}`, dataset: { noteId: comment.id } },
    h('div', { class: `avatar avatar-${comment.author}` }, avatarChar),
    h('div', { class: 'note-body' },
      chip,
      textEl,
      actions.length ? h('div', { class: 'note-actions' }, actions) : null,
      replies.length ? h('div', { class: 'note-replies' }, replies.map((r) => replyItem(r))) : null));
}
function replyItem(reply) {
  const textEl = h('div', { class: 'note-text' });
  textEl.innerHTML = md(reply.text);
  return h('div', { class: 'reply-item' },
    h('div', { class: 'avatar avatar-editor' }, editorInitial()),
    h('div', { class: 'reply-body' }, textEl));
}
function notesSection(title, items, all, collapsed = false) {
  return h('details', { class: 'notes-section', open: !collapsed && !!items.length },
    h('summary', {}, `${title} (${items.length})`),
    h('div', { class: 'notes-list' },
      items.length ? items.map((c) => noteItem(c, all)) : h('div', { class: 'empty-state small' }, 'None')));
}
function renderNotesGroups() {
  const all = clip.comments || [];
  const topLevel = all.filter((c) => c.parent == null);
  const drafts = topLevel.filter((c) => c.status === 'draft');
  const sent = topLevel.filter((c) => c.status === 'sent');
  const addressed = topLevel.filter((c) => c.status === 'addressed');
  const resolved = topLevel.filter((c) => c.status === 'resolved' || c.status === 'wontfix');
  const sortFn = (a, b) => (b.version - a.version) || ((a.t ?? -1) - (b.t ?? -1));
  [drafts, sent, addressed, resolved].forEach((g) => g.sort(sortFn));

  const frag = document.createDocumentFragment();
  // Review starts from "what changed": the editor's changelog for the version on screen, and the notes it
  // says it handled (confirm them below).
  const v = (clip.versions || []).find((x) => x.n === currentVersion);
  if (v && v.notes) {
    const body = h('div', { class: 'change-notes' });
    body.innerHTML = md(v.notes);
    const handled = all.filter((c) => (v.addresses || []).includes(c.id));
    frag.append(h('details', { class: 'notes-section what-changed', open: true },
      h('summary', {}, `What changed in ${v.n === 0 ? 'the original' : `v${v.n}`}${handled.length ? ` · handles ${handled.length} note${handled.length > 1 ? 's' : ''}` : ''}`),
      body));
  }
  frag.append(
    notesSection('Drafts', drafts, all),
    notesSection('Sent to editor', sent, all),
    notesSection('Addressed — confirm', addressed, all),
    notesSection("Resolved / Won't fix", resolved, all, true));
  return frag;
}

// ---- changes / brief / log tabs --------------------------------------------

function renderChanges() {
  const versions = versionsSorted().slice().reverse();
  if (!versions.length) return h('div', { class: 'empty-state small' }, 'No versions yet.');
  return h('div', { class: 'changes-list' }, versions.map((v) => {
    const addressed = (clip.comments || []).filter((c) => (v.addresses || []).includes(c.id));
    const notesEl = h('div', { class: 'change-notes' });
    notesEl.innerHTML = md(v.notes || '_No changelog._');
    return h('div', { class: 'change-item' },
      h('div', { class: 'change-head' }, `${v.n === 0 ? 'v0 · original' : `v${v.n}`} · ${relTime(v.created)} · ${fmtDur(v.duration)}`),
      notesEl,
      addressed.length ? h('div', { class: 'change-addressed' }, addressed.map((c) => h('button', {
        type: 'button', class: 'chip', onclick: () => seekToComment(c),
      }, c.text.length > 60 ? `${c.text.slice(0, 60)}…` : c.text))) : null);
  }));
}

function renderBrief() {
  const briefTa = h('textarea', { class: 'textarea', rows: 8 }, clip.brief || '');
  briefTa.addEventListener('blur', async () => {
    try {
      await patch(`/api/clips/${clip.id}`, { brief: briefTa.value });
      toast('Brief saved');
    } catch (e) {
      toast(e.message, 'err');
    }
  });
  return h('div', { class: 'brief-panel stack' },
    h('div', { class: 'field' }, h('label', {}, 'Brief'), briefTa),
    h('div', { class: 'field' }, h('label', {}, 'Source'), h('div', { class: 'muted' }, clip.source || '—')),
    h('div', { class: 'field' }, h('label', {}, 'Workdir'),
      h('div', { class: 'row' },
        h('code', {}, clip.workdir || '—'),
        clip.workdir ? h('button', { class: 'btn-icon', 'aria-label': 'Copy workdir', onclick: () => copy(clip.workdir) }, '⍧') : null)),
    h('div', { class: 'field' }, h('label', {}, 'Version files'),
      h('div', { class: 'stack' }, versionsSorted().map((v) => h('div', { class: 'row' },
        h('code', {}, `v${v.n}: ${v.file}`),
        h('button', { class: 'btn-icon', 'aria-label': `Copy v${v.n} path`, onclick: () => copy(v.file) }, '⍧'))))));
}

async function loadLog() {
  if (!clip) return;
  try {
    const data = await get(`/api/clips/${clip.id}/log?lines=200`);
    logText = data.text || '';
    if (shellRefs) {
      shellRefs.logTab.innerHTML = '';
      shellRefs.logTab.appendChild(h('pre', { class: 'log-view' }, logText || 'No log yet.'));
    }
    clearTimeout(logTimer);
    if (data.running) logTimer = setTimeout(loadLog, 2000);
  } catch (e) {
    /* ignore */
  }
}

// ---- header / tabs / version tabs / action bar ------------------------------

let showEditExplainer = false;

function clipCameFromIdea(c) {
  // Best-effort: clips created from an approved recording proposal get `source` filled in
  // automatically ("<file> ranges ..."); clips added directly via the CLI usually don't set it.
  return !!(c && c.source && c.source.trim());
}

function modeSwitchNode() {
  return h('div', { class: 'seg review-mode-switch' },
    h('span', { class: 'seg-btn active' }, 'Review'),
    h('button', {
      type: 'button', class: 'seg-btn',
      onclick: () => {
        if (clip.has_recipe) { navigate(`#/edit/${clip.id}`); return; }
        showEditExplainer = !showEditExplainer;
        updateHeader();
      },
    }, 'Edit'));
}

function editExplainerNode() {
  if (!showEditExplainer || clip.has_recipe) return null;
  const cameFromIdea = clipCameFromIdea(clip);
  return h('div', { class: 'review-edit-explainer' },
    h('div', {}, 'This clip was made before recipes.'),
    cameFromIdea
      ? h('div', { class: 'row' },
        h('span', { class: 'muted' }, 'It came from an idea — a rough-cut recipe can be built from its source ranges.'),
        h('button', {
          class: 'btn btn-sm btn-primary',
          onclick: async () => {
            try {
              await post(`/api/clips/${clip.id}/edit/rough-cut`, {});
              toast('Recipe created');
              navigate(`#/edit/${clip.id}`);
            } catch (e) {
              toast(e.message, 'err');
            }
          },
        }, 'Build rough-cut recipe'))
      : h('span', { class: 'muted' }, "It wasn't made from an idea's source ranges, so there's nothing to build a recipe from automatically."));
}

function buildHeaderContent() {
  const settings = getState()?.settings || {};
  const agent = clip.agent || {};
  let agentLine = null;
  if (agent.state === 'working') {
    agentLine = h('div', { class: 'agent-line agent-working' }, `${settings.editor_name || 'Editor'} is editing · started ${relTime(agent.started)}`);
  } else if (agent.state === 'queued') {
    agentLine = h('div', { class: 'agent-line agent-queued' }, `Queued for ${settings.editor_name || 'Editor'}`);
  } else if (agent.state === 'error') {
    agentLine = h('div', { class: 'agent-line agent-error' },
      agent.message || 'Error', ' ',
      h('button', { class: 'btn btn-sm', onclick: () => dispatchClip() }, 'Retry'));
  }
  return h('div', {},
    h('div', { class: 'review-header-top' },
      h('h2', {}, clip.title),
      h('div', { class: 'row' }, h('span', { class: `pill pill-${clip.status}` }, clip.status), modeSwitchNode())),
    h('div', { class: 'muted small' }, clip.batch || ''),
    agentLine,
    editExplainerNode());
}
function updateHeader() {
  if (!shellRefs) return;
  shellRefs.headerEl.innerHTML = '';
  shellRefs.headerEl.appendChild(buildHeaderContent());
}

function buildVersionTabsContent() {
  const vs = versionsSorted();
  const tabs = vs.map((v) => h('button', {
    type: 'button',
    class: `tab${v.n === currentVersion ? ' active' : ''}`,
    onclick: () => switchVersion(v.n),
  }, v.n === 0 ? 'v0 · original' : `v${v.n}`,
  v.n > (clip.director_seen_version ?? -1) ? h('span', { class: 'new-dot', 'aria-label': 'New version' }) : null));
  const compareToggle = h('label', { class: 'checkbox compare-toggle' },
    h('input', { type: 'checkbox', checked: compareVersion != null, onchange: (e) => toggleCompare(e.target.checked) }),
    h('span', {}, 'Compare'));
  return h('div', { class: 'row version-tabs' }, tabs, compareToggle);
}
function updateVersionTabs() {
  if (!shellRefs) return;
  shellRefs.versionTabsEl.innerHTML = '';
  shellRefs.versionTabsEl.appendChild(buildVersionTabsContent());
}

function buildActionBarContent() {
  const draftCount = (clip.comments || []).filter((c) => c.status === 'draft' && c.author === 'director').length;
  const sendBtn = h('button', {
    class: 'btn btn-primary', disabled: draftCount === 0, onclick: () => sendNotes(),
  }, `Send ${draftCount} note${draftCount === 1 ? '' : 's'} to editor`);

  let approveBtn;
  if (clip.approved_version === currentVersion) {
    approveBtn = h('div', { class: 'row' },
      h('span', { class: 'pill pill-approved' }, `Approved v${currentVersion}`),
      h('button', { class: 'btn btn-ghost', onclick: () => unapprove() }, 'Unapprove'));
  } else {
    approveBtn = h('button', { class: 'btn', onclick: () => approveCurrent() }, `Approve v${currentVersion}`);
  }

  const nextBtn = h('button', { class: 'btn btn-ghost', onclick: () => nextClip() }, 'Next clip →');
  return h('div', { class: 'actionbar-inner' }, sendBtn, approveBtn, nextBtn);
}
function updateActionBar() {
  if (!shellRefs) return;
  shellRefs.actionBar.innerHTML = '';
  shellRefs.actionBar.appendChild(buildActionBarContent());
}

function updateBanner() {
  if (!shellRefs) return;
  const b = shellRefs.bannerEl;
  b.innerHTML = '';
  if (newVersionBanner == null) {
    b.classList.add('hidden');
    return;
  }
  b.classList.remove('hidden');
  b.append(`v${newVersionBanner} is ready — `, h('button', {
    class: 'btn-link', onclick: () => { switchVersion(newVersionBanner); newVersionBanner = null; updateBanner(); },
  }, 'open'));
}

function setActiveTab(tab) {
  activeTab = tab;
  if (!shellRefs) return;
  const order = ['notes', 'changes', 'brief', 'log'];
  Array.from(shellRefs.tabsEl.children).forEach((btn, i) => btn.classList.toggle('active', order[i] === tab));
  shellRefs.notesTab.classList.toggle('hidden', tab !== 'notes');
  shellRefs.changesTab.classList.toggle('hidden', tab !== 'changes');
  shellRefs.briefTab.classList.toggle('hidden', tab !== 'brief');
  shellRefs.logTab.classList.toggle('hidden', tab !== 'log');
  if (tab === 'log') loadLog();
}

// ---- shell build / full refresh --------------------------------------------

function buildShell() {
  root.innerHTML = '';
  briefBuilt = false;

  const bannerEl = h('div', { class: 'version-banner hidden' });

  const playerMount = h('div', { class: 'phone-frame' });
  const left = h('div', { class: 'review-left' }, bannerEl, playerMount);

  player = createPlayer(playerMount, {
    src: currentVersionObj()?.media_url || '',
    aspect: '9/16',
    onTime: () => onPlayerTime(),
    onPlayState: (playing) => {
      if (comparePlayer) {
        if (playing) comparePlayer.play(); else comparePlayer.pause();
      }
    },
  });

  const timelineWrap = buildTimeline();
  const versionTabsEl = h('div', { class: 'version-tabs-row' });
  const compareRow = h('div', { class: 'compare-row hidden' });
  left.append(timelineWrap, versionTabsEl, compareRow);

  const headerEl = h('div', { class: 'review-header' });
  const tabsEl = h('div', { class: 'tabs' },
    ['notes', 'changes', 'brief', 'log'].map((t) => h('button', {
      type: 'button',
      class: `tab${activeTab === t ? ' active' : ''}`,
      onclick: () => setActiveTab(t),
    }, t[0].toUpperCase() + t.slice(1))));

  const chip = h('button', { type: 'button', class: 'chip composer-chip', onclick: () => toggleComposerWhole() }, 'at 0:00.0');
  composerChipEl = chip;
  composerTa = h('textarea', {
    class: 'textarea composer-input', rows: 2,
    placeholder: 'Add a note… (Enter to add, Shift+Enter for newline, N to capture the playhead)',
  });
  composerTa.addEventListener('focus', () => {
    if (composerCaptured == null && !composerWhole) composerCaptured = player.time();
    player.pause();
    updateComposerChip();
  });
  composerTa.addEventListener('input', () => player.pause());
  composerTa.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitDraftNote();
    }
  });
  const composer = h('div', { class: 'composer' }, chip, composerTa);
  const notesGroupsEl = h('div', { class: 'notes-groups' });
  const notesTab = h('div', { class: 'tab-panel notes-panel' }, composer, notesGroupsEl);
  const changesTab = h('div', { class: 'tab-panel changes-panel hidden' });
  const briefTab = h('div', { class: 'tab-panel brief-panel hidden' });
  const logTab = h('div', { class: 'tab-panel log-panel hidden' });

  const right = h('div', { class: 'review-right panel' }, headerEl, tabsEl,
    h('div', { class: 'tab-content' }, notesTab, changesTab, briefTab, logTab));

  const actionBar = h('div', { class: 'review-actionbar' });

  root.append(h('div', { class: 'review-layout split' }, left, right), actionBar);

  shellRefs = {
    headerEl, tabsEl, notesTab, changesTab, briefTab, logTab, notesGroupsEl, versionTabsEl, compareRow, bannerEl, actionBar,
  };

  updateAll();
  loadLog();
}

function updateAll() {
  updateHeader();
  updateVersionTabs();
  updateTimeline();
  updateActionBar();
  updateBanner();
  updateComposerChip();
  if (!shellRefs) return;
  // Don't blow away an in-progress inline edit (a <textarea> swapped into a note) on a
  // background poll refresh — only rebuild the notes list when nothing there is being edited.
  const editingNote = shellRefs.notesGroupsEl.contains(document.activeElement)
    && document.activeElement.tagName === 'TEXTAREA';
  if (!editingNote) {
    shellRefs.notesGroupsEl.innerHTML = '';
    shellRefs.notesGroupsEl.appendChild(renderNotesGroups());
  }
  shellRefs.changesTab.innerHTML = '';
  shellRefs.changesTab.appendChild(renderChanges());
  if (!briefBuilt) {
    shellRefs.briefTab.appendChild(renderBrief());
    briefBuilt = true;
  }
}

// ---- keyboard ---------------------------------------------------------------

function isTyping(e) {
  const t = e.target;
  return !!(t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable));
}
function blurActive() {
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
}
const HELP_KEYS = [
  ['Space', 'Play / pause'], ['K', 'Pause'], ['J / L', '-5s / +5s'], ['← / →', '-1s / +1s'],
  [', / .', 'Prev / next frame'], ['N', 'Note at playhead'], ['[ / ]', 'Prev / next version'],
  ['G', 'Toggle compare'], ['Shift+A', 'Approve current version'], ['⌘/Ctrl+Enter', 'Send notes'],
  ['Shift+N', 'Next clip'], ['Esc', 'Blur / close overlays'], ['?', 'This help'],
];
function toggleHelp() {
  helpVisible = !helpVisible;
  const overlayRoot = document.getElementById('overlay-root');
  if (!overlayRoot) return;
  overlayRoot.innerHTML = '';
  if (!helpVisible) return;
  overlayRoot.appendChild(h('div', { class: 'overlay-backdrop', onclick: () => { helpVisible = false; overlayRoot.innerHTML = ''; } },
    h('div', { class: 'help-card', onclick: (e) => e.stopPropagation() },
      h('h3', {}, 'Review shortcuts'),
      h('div', { class: 'help-grid' }, HELP_KEYS.flatMap(([k, d]) => [h('span', { class: 'kbd' }, k), h('span', {}, d)])))));
}
function closeHelp() {
  if (!helpVisible) return;
  helpVisible = false;
  const overlayRoot = document.getElementById('overlay-root');
  if (overlayRoot) overlayRoot.innerHTML = '';
}

function handleKeydown(e) {
  const typing = isTyping(e);
  const cmdEnter = (e.metaKey || e.ctrlKey) && e.key === 'Enter';
  if (typing && e.key !== 'Escape' && !cmdEnter) return;
  if (e.key === 'Escape') { blurActive(); closeHelp(); return; }
  if (cmdEnter) { e.preventDefault(); sendNotes(); return; }
  if (!player) return;
  switch (e.key) {
    case ' ': e.preventDefault(); player.toggle(); break;
    case 'k': case 'K': player.pause(); break;
    case 'j': case 'J': seekTo(player.time() - 5); break;
    case 'l': case 'L': seekTo(player.time() + 5); break;
    case 'ArrowLeft': seekTo(player.time() - 1); break;
    case 'ArrowRight': seekTo(player.time() + 1); break;
    case ',': player.step(-1); break;
    case '.': player.step(1); break;
    case 'n': focusComposerAtPlayhead(); break;
    case 'N': nextClip(); break;
    case '[': prevVersion(); break;
    case ']': nextVersion(); break;
    case 'g': case 'G': toggleCompare(compareVersion == null); break;
    case 'A': if (e.shiftKey) approveCurrent(); break;
    case '?': toggleHelp(); break;
    default: break;
  }
}

// ---- polling ------------------------------------------------------------

function schedulePoll() {
  clearTimeout(pollTimer);
  const busy = clip?.agent?.state === 'queued' || clip?.agent?.state === 'working';
  pollTimer = setTimeout(async () => {
    if (!clip) return;
    await loadClip();
    schedulePoll();
  }, busy ? 2000 : 6000);
}

// ---- empty / loading states -------------------------------------------------

function renderEmpty() {
  root.innerHTML = '';
  root.appendChild(h('div', { class: 'empty-state large' },
    h('div', { class: 'empty-icon' }, '🎉'),
    h('div', {}, 'All caught up.'),
    h('div', { class: 'muted' }, 'Nothing needs your review right now.'),
    h('button', { class: 'btn', onclick: () => navigate('#/') }, 'Back to board')));
}
function renderLoading() {
  root.innerHTML = '';
  root.appendChild(h('div', { class: 'empty-state' }, 'Loading…'));
}

// ---- view lifecycle ------------------------------------------------------

async function mountReview(el, params) {
  root = el;
  root.className = 'view-review';
  activeTab = 'notes';
  compareVersion = null;
  composerCaptured = null;
  composerWhole = false;
  newVersionBanner = null;
  shellRefs = null;
  timelineRefs = null;
  briefBuilt = false;
  showEditExplainer = false;
  clip = null;

  if (!params || !params.id) {
    const state = getState();
    const queue = reviewQueueFromState(state);
    if (queue.length) {
      navigate(`#/clip/${queue[0].id}`);
      return;
    }
    renderEmpty();
    return;
  }
  clipId = params.id;
  renderLoading();
  document.addEventListener('keydown', handleKeydown);
  await loadClip();
  schedulePoll();
}

function unmountReview() {
  document.removeEventListener('keydown', handleKeydown);
  clearTimeout(pollTimer);
  clearTimeout(logTimer);
  if (timelineCleanup) { timelineCleanup(); timelineCleanup = null; }
  if (player) { player.destroy(); player = null; }
  if (comparePlayer) { comparePlayer.destroy(); comparePlayer = null; }
  closeHelp();
  root = null;
  clip = null;
  shellRefs = null;
  timelineRefs = null;
}

registerView('review', {
  mount: mountReview,
  unmount: unmountReview,
  onState() {
    if (shellRefs) {
      updateHeader();
      updateActionBar();
    }
  },
});
