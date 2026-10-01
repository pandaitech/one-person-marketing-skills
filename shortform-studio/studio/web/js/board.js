// board.js — batch overview: Columns (Your review / Queued / Editing / Approved / Published) or Wall.

import { registerView, navigate, getState } from './app.js';
import { h, fmtDur, relTime, statusPill, debounce } from './util.js';

let root = null;
let mode = 'columns';
let batchFilter = '';
let search = '';
let showArchived = false;

function loadMode() {
  try {
    const saved = localStorage.getItem('studio.board.mode');
    if (saved === 'wall' || saved === 'columns') mode = saved;
  } catch (e) {
    /* localStorage unavailable */
  }
}
function saveMode() {
  try {
    localStorage.setItem('studio.board.mode', mode);
  } catch (e) {
    /* ignore */
  }
}

function isYourReview(clip) {
  return clip.status === 'review' || (clip.open && clip.open.draft > 0);
}
function isRendering(clip) {
  return clip.render?.state === 'running';
}
function isEditing(clip) {
  return clip.status === 'working' || clip.agent?.state === 'working' || isRendering(clip);
}
function isQueuedCol(clip) {
  return clip.status === 'queued' || clip.status === 'drafting' || clip.agent?.state === 'queued';
}

function matchesFilters(clip) {
  if (!showArchived && clip.status === 'archived') return false;
  if (batchFilter && clip.batch !== batchFilter) return false;
  if (search) {
    const q = search.toLowerCase();
    if (!clip.title?.toLowerCase().includes(q) && !clip.id.toLowerCase().includes(q)) return false;
  }
  return true;
}

function sortReview(list) {
  return list.slice().sort((a, b) => {
    if (!!a.new_version !== !!b.new_version) return a.new_version ? -1 : 1;
    return new Date(b.updated || 0) - new Date(a.updated || 0);
  });
}

function badge(text, kind) {
  return h('span', { class: `badge badge-${kind}` }, text);
}

function card(clip) {
  const badges = [];
  if (isRendering(clip)) badges.push(badge('Rendering…', 'rendering'));
  if (clip.new_version) badges.push(badge('NEW', 'new'));
  if (clip.open?.draft) badges.push(badge(`${clip.open.draft} draft${clip.open.draft > 1 ? 's' : ''}`, 'draft'));
  if (clip.open?.addressed) badges.push(badge(`${clip.open.addressed} to confirm`, 'addressed'));
  if (clip.agent?.state === 'error') badges.push(badge('error', 'error'));
  if (clip.has_recipe) badges.push(badge('Recipe', 'recipe'));

  const noCut = clip.latest_version == null;
  const waiting = clip.agent?.state === 'working' ? 'Claude is cutting v1…' : 'Waiting for the first cut';
  const poster = h('div', { class: 'card-poster' },
    clip.poster_url && !noCut
      ? h('img', { src: clip.poster_url, loading: 'lazy', alt: '' })
      : h('div', { class: 'poster-empty' }, noCut ? h('span', { class: 'poster-empty-text' }, waiting) : null),
    clip.dirty ? h('span', { class: 'dirty-dot', title: 'Edited, not rendered yet' }) : null);

  const meta = [noCut ? 'no version yet' : `v${clip.latest_version}`];
  if (clip.duration != null) meta.push(fmtDur(clip.duration));

  return h('div', {
    class: 'card',
    tabindex: '0',
    role: 'button',
    'aria-label': `Open ${clip.title}`,
    onclick: () => navigate(`#/clip/${clip.id}`),
    onkeydown: (e) => { if (e.key === 'Enter') navigate(`#/clip/${clip.id}`); },
  },
  poster,
  badges.length ? h('div', { class: 'card-badges' }, badges) : null,
  h('div', { class: 'card-body' },
    h('div', { class: 'card-title' }, clip.title),
    h('div', { class: 'card-meta muted' }, meta.join(' · ')),
    h('div', { class: 'card-time muted' }, relTime(clip.updated))));
}

function column(title, clips) {
  return h('div', { class: 'board-col' },
    h('div', { class: 'board-col-head' },
      h('span', { class: 'board-col-title' }, title),
      h('span', { class: 'board-col-count' }, String(clips.length))),
    h('div', { class: 'board-col-body' },
      clips.length ? clips.map(card) : h('div', { class: 'empty-state small' }, 'Nothing here')));
}

function renderColumns(clips) {
  const yourReview = sortReview(clips.filter(isYourReview));
  const queued = clips.filter((c) => isQueuedCol(c) && !isEditing(c) && !isYourReview(c));
  const editing = clips.filter((c) => isEditing(c) && !isYourReview(c));
  const approved = clips.filter((c) => c.status === 'approved');
  const published = clips.filter((c) => c.status === 'published');
  return h('div', { class: 'board-columns' },
    column('Needs you', yourReview),
    column('Waiting for Claude', queued),
    column('Claude is editing', editing),
    column('Approved', approved),
    column('Published', published));
}

function wallCard(clip) {
  const posterEl = h('div', { class: 'wall-poster' },
    clip.poster_url && clip.latest_version != null
      ? h('img', { src: clip.poster_url, loading: 'lazy', alt: '' })
      : h('div', { class: 'poster-empty' }, h('span', { class: 'poster-empty-text' }, 'Waiting for the first cut')));

  const el = h('div', {
    class: 'wall-card',
    tabindex: '0',
    role: 'button',
    'aria-label': `Open ${clip.title}`,
    onclick: () => navigate(`#/clip/${clip.id}`),
    onkeydown: (e) => { if (e.key === 'Enter') navigate(`#/clip/${clip.id}`); },
  },
  posterEl,
  h('div', { class: 'wall-chip' }, statusPill(clip.status)),
  h('div', { class: 'wall-title' }, clip.title));

  el.addEventListener('mouseenter', () => {
    if (clip.latest_version == null) return;
    const video = document.createElement('video');
    video.className = 'wall-preview';
    video.src = `/media/${clip.id}/${clip.latest_version}`;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.autoplay = true;
    posterEl.appendChild(video);
  });
  el.addEventListener('mouseleave', () => {
    const v = posterEl.querySelector('.wall-preview');
    if (v) v.remove();
  });
  return el;
}

function renderWall(clips) {
  if (!clips.length) return h('div', { class: 'empty-state' }, 'No clips match.');
  return h('div', { class: 'wall-grid' }, clips.map(wallCard));
}

let lastSig = null;
let lastRender = 0;

function render() {
  if (!root) return;
  lastRender = Date.now();
  const state = getState();
  const allClips = state?.clips || [];
  const clips = allClips.filter(matchesFilters);
  root.innerHTML = '';

  const batches = state?.batches || [];
  const batchSelect = h('select', {
    class: 'select',
    onchange: (e) => { batchFilter = e.target.value; render(); },
  },
  h('option', { value: '' }, 'All batches'),
  batches.map((b) => h('option', { value: b.id, selected: b.id === batchFilter }, b.name || b.id)));

  const searchInput = h('input', {
    class: 'input', type: 'search', placeholder: 'Search clips…', value: search,
    oninput: debounce((e) => { search = e.target.value; render(); }, 150),
  });

  const seg = h('div', { class: 'seg' },
    h('button', { class: `seg-btn${mode === 'columns' ? ' active' : ''}`, onclick: () => { mode = 'columns'; saveMode(); render(); } }, 'Columns'),
    h('button', { class: `seg-btn${mode === 'wall' ? ' active' : ''}`, onclick: () => { mode = 'wall'; saveMode(); render(); } }, 'Wall'));

  const archiveToggle = h('label', { class: 'checkbox' },
    h('input', { type: 'checkbox', checked: showArchived, onchange: (e) => { showArchived = e.target.checked; render(); } }),
    h('span', {}, 'Show archived'));

  const reviewCount = state?.counts?.review ?? 0;
  const startBtn = h('button', { class: 'btn btn-primary', onclick: () => navigate('#/review') }, `Start review (${reviewCount})`);

  const toolbar = h('div', { class: 'board-toolbar' },
    h('div', { class: 'row' }, batchSelect, searchInput, archiveToggle),
    h('div', { class: 'row' }, seg, startBtn));

  if (!allClips.length) {
    root.append(toolbar, h('div', { class: 'empty-state large' },
      h('div', { class: 'empty-icon' }, '🎬'),
      h('div', {}, 'No clips yet.'),
      h('div', { class: 'muted' }, 'Add a clip from the CLI, or approve a proposal on the Recordings tab.')));
    return;
  }

  root.append(toolbar, mode === 'columns' ? renderColumns(clips) : renderWall(clips));
}

registerView('board', {
  mount(el) {
    root = el;
    root.className = 'view-board';
    loadMode();
    render();
  },
  unmount() {
    root = null;
    lastSig = null;
  },
  onState() {
    // Only redraw when the data changed (or once a minute for relative times). A blind redraw every poll
    // would eat clicks, reset hover previews and steal focus from the search box.
    const s = getState() || {};
    const sig = JSON.stringify([s.clips, s.batches, s.counts]);
    const stale = Date.now() - lastRender > 60000;
    if (sig === lastSig && !stale) return;
    const active = document.activeElement;
    if (root && active && root.contains(active) && active.matches('input, select, textarea')) return;
    if (root && root.querySelector('.wall-preview')) return; // a hover preview is playing
    lastSig = sig;
    render();
  },
});
