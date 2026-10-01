// ideas.js — the watch-and-decide feed (#/ideas/<rec_id>): watch each clip-bank proposal
// as a plain "cheap cut" and approve/reject fast. There is no separate rendered file for
// this -- the player just plays the recording's own media (`/media/rec/<rec_id>`, already
// Range-served) and jumps through the proposal's stored source ranges back to back via
// player.playRanges(), exactly like recording.js's existing "▶ Preview cut". A custom
// progress bar shows the *idea's* own clock (0 .. sum of its ranges), not the 1h45m
// source position. The detailed range editor (recording.js) stays reachable via
// "Adjust cut / transcript" links -- this view is only for triage-by-watching.
import { get, post, patch } from './api.js';
import { h, fmtTime, fmtDur, toast } from './util.js';
import { createPlayer } from './player.js';
import { registerView, refresh } from './app.js';

// ---- module state (one ideas view is ever mounted at a time) --------------

let root = null;
let recId = null;
let rec = null;               // full Recording (media_url + proposals[])
let player = null;
let selectedPid = null;
let filterTab = 'undecided';  // undecided | clip | skipped | all
let summaryExpanded = false;
let lastDecision = null;      // { pid, action: 'approve' | 'reject' } — for Undo (U)
let countdownTimer = null;
let countdownRemaining = 0;
let countdownCancel = null;
let onKeydownRef = null;

let headerEl = null;
let bodyEl = null;
let actionsEl = null;
let playerOuterEl = null;
let countdownEl = null;
let playPauseBtn = null;
let clockFillEl = null;
let clockHeadEl = null;
let clockTimeEl = null;
let progressEl = null;
let tabsWrapEl = null;
let listEl = null;

// ---- small pure helpers -----------------------------------------------

function proposals() {
  return (rec && rec.proposals) || [];
}

function proposalDuration(p) {
  return (p.ranges || []).reduce((sum, r) => sum + Math.max(0, r[1] - r[0]), 0);
}

function statusOf(p) {
  if (p.status === 'approved') return 'clip';
  if (p.status === 'rejected') return 'skipped';
  return 'undecided'; // proposed | needs_changes
}

function statusChipLabel(st) {
  return { undecided: 'Undecided', clip: 'Clip ✓', skipped: 'Skipped' }[st] || st;
}

function firstSentence(text) {
  if (!text) return '';
  const m = text.match(/^(.*?[.!?])(\s|$)/);
  return m ? m[1] : text;
}

function selectedProposal() {
  return proposals().find((p) => p.id === selectedPid) || null;
}

function currentList() {
  const list = proposals();
  if (filterTab === 'all') return list;
  return list.filter((p) => statusOf(p) === filterTab);
}

function nextUndecidedAfter(pid) {
  const list = proposals();
  const idx = list.findIndex((p) => p.id === pid);
  const start = idx === -1 ? 0 : idx;
  for (let i = 1; i <= list.length; i++) {
    const cand = list[(start + i) % list.length];
    if (cand.id !== pid && statusOf(cand) === 'undecided') return cand;
  }
  return null;
}

// ---- idea-clock <-> source-time mapping -----------------------------------
// The player always plays the whole recording; a proposal is just a list of
// [start, end] source-second ranges played back to back. These helpers convert
// between "seconds into this idea" (what the director should see and scrub)
// and "seconds into the 1h45m source file" (what the <video> element uses).

function rangeStarts(ranges) {
  let acc = 0;
  return ranges.map((r) => { const start = acc; acc += Math.max(0, r[1] - r[0]); return start; });
}

function rangeIndexAtSourceTime(ranges, t) {
  for (let i = 0; i < ranges.length; i++) {
    if (t >= ranges[i][0] - 0.05 && t <= ranges[i][1] + 0.05) return i;
  }
  let best = 0;
  let bestDist = Infinity;
  ranges.forEach((r, i) => {
    const d = Math.min(Math.abs(r[0] - t), Math.abs(r[1] - t));
    if (d < bestDist) { bestDist = d; best = i; }
  });
  return best;
}

function sourceToIdeaTime(ranges, t) {
  const starts = rangeStarts(ranges);
  const idx = rangeIndexAtSourceTime(ranges, t);
  const within = Math.min(Math.max(t - ranges[idx][0], 0), Math.max(0, ranges[idx][1] - ranges[idx][0]));
  return starts[idx] + within;
}

/** {sourceTime, idx} for the range containing idea-time ideaT (clamped to [0, total]). */
function ideaTimeToSource(ranges, ideaT) {
  const starts = rangeStarts(ranges);
  const total = proposalDuration({ ranges });
  const clamped = Math.min(Math.max(ideaT, 0), total);
  let idx = ranges.length - 1;
  for (let i = 0; i < ranges.length; i++) {
    const len = Math.max(0, ranges[i][1] - ranges[i][0]);
    if (clamped < starts[i] + len || i === ranges.length - 1) { idx = i; break; }
  }
  return { sourceTime: ranges[idx][0] + (clamped - starts[idx]), idx };
}

/** The remaining [start,end] legs to hand to player.playRanges() to continue
 * playback of `ranges` starting from source time `t`. */
function remainingRangesFrom(ranges, t) {
  const idx = rangeIndexAtSourceTime(ranges, t);
  const clampedStart = Math.max(t, ranges[idx][0]);
  return [[clampedStart, ranges[idx][1]], ...ranges.slice(idx + 1)];
}

// ---- custom idea-clock UI (progress bar + play/pause; player.js's own time
// label shows the raw 1h45m source position, which isn't useful here) --------

function updateClock(elapsed, total) {
  if (!clockFillEl) return;
  const pct = total > 0 ? Math.min(100, Math.max(0, (elapsed / total) * 100)) : 0;
  clockFillEl.style.width = `${pct}%`;
  clockHeadEl.style.left = `${pct}%`;
  clockTimeEl.textContent = `${fmtTime(elapsed)} / ${fmtTime(total)}`;
}

function onPlayerTime(t) {
  const p = selectedProposal();
  if (!p) return;
  updateClock(sourceToIdeaTime(p.ranges, t), proposalDuration(p));
}

function onPlayerPlayState(isPlaying) {
  if (playPauseBtn) playPauseBtn.textContent = isPlaying ? '⏸' : '▶';
  if (isPlaying) return;
  const p = selectedProposal();
  if (!p) return;
  const lastEnd = p.ranges[p.ranges.length - 1][1];
  // playRanges() itself pauses when the last range finishes; any other pause
  // (spacebar, the button, a manual seek) lands well short of the last range's end.
  if (player.time() >= lastEnd - 0.15) startCountdown();
}

function togglePlay() {
  const p = selectedProposal();
  if (!p) return;
  if (player.video.paused) {
    player.playRanges(remainingRangesFrom(p.ranges, player.time()));
  } else {
    player.pause();
  }
}

function onClockTrackClick(e) {
  const p = selectedProposal();
  if (!p) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  const total = proposalDuration(p);
  const wasPlaying = !player.video.paused;
  const { sourceTime, idx } = ideaTimeToSource(p.ranges, frac * total);
  if (wasPlaying) {
    player.playRanges([[sourceTime, p.ranges[idx][1]], ...p.ranges.slice(idx + 1)]);
  } else {
    player.seek(sourceTime);
  }
  updateClock(frac * total, total);
}

// ---- countdown (auto-advance after a cut finishes playing) -------------

function clearCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  if (countdownCancel) {
    window.removeEventListener('keydown', countdownCancel);
    window.removeEventListener('click', countdownCancel);
    countdownCancel = null;
  }
  if (countdownEl) countdownEl.style.display = 'none';
}

function renderCountdownText() {
  const textEl = countdownEl.querySelector('.idf-countdown-text');
  if (textEl) textEl.textContent = `Next idea in ${countdownRemaining}s`;
}

function startCountdown() {
  const next = nextUndecidedAfter(selectedPid);
  if (!next || !countdownEl) return;
  countdownRemaining = 3;
  countdownEl.style.display = 'flex';
  renderCountdownText();
  countdownCancel = () => clearCountdown();
  window.addEventListener('keydown', countdownCancel);
  window.addEventListener('click', countdownCancel);
  countdownTimer = setInterval(() => {
    countdownRemaining -= 1;
    if (countdownRemaining <= 0) {
      clearCountdown();
      selectProposal(next.id, true);
      return;
    }
    renderCountdownText();
  }, 1000);
}

// ---- right panel: progress / tabs / list --------------------------------

function progressLine() {
  const counts = { undecided: 0, clip: 0, skipped: 0 };
  proposals().forEach((p) => { counts[statusOf(p)] += 1; });
  return `${counts.undecided} undecided · ${counts.clip} clip${counts.clip === 1 ? '' : 's'} · `
    + `${counts.skipped} skipped`;
}

function tabsBar() {
  const counts = { undecided: 0, clip: 0, skipped: 0 };
  proposals().forEach((p) => { counts[statusOf(p)] += 1; });
  const tabs = [
    ['undecided', 'Undecided', counts.undecided],
    ['clip', 'Made into clips', counts.clip],
    ['skipped', 'Skipped', counts.skipped],
    ['all', 'All', proposals().length],
  ];
  return h('div', { class: 'row idf-tabs' }, tabs.map(([key, label, n]) => h('button', {
    class: `chip idf-tab${filterTab === key ? ' idf-tab-active' : ''}`,
    onclick: () => { filterTab = key; onFilterChange(); },
  }, `${label} (${n})`)));
}

function onFilterChange() {
  renderList();
  const list = currentList();
  if (list.length && !list.some((p) => p.id === selectedPid)) {
    selectProposal(list[0].id, true);
  }
}

function ideaRow(p) {
  const st = statusOf(p);
  const firstStart = (p.ranges && p.ranges[0] && p.ranges[0][0]) || 0;
  const thumbUrl = `/thumb/rec/${recId}.jpg?t=${(firstStart + 1).toFixed(2)}`;
  return h('div', {
    class: `idf-row${p.id === selectedPid ? ' idf-row-selected' : ''}`,
    onclick: () => selectProposal(p.id, true),
  },
    h('div', { class: 'idf-row-thumb', style: `background-image:url(${thumbUrl})` }),
    h('div', { class: 'idf-row-body' },
      h('div', { class: 'idf-row-title' }, p.title),
      h('div', { class: 'muted idf-row-meta' }, fmtDur(proposalDuration(p)))),
    h('span', { class: `idf-chip idf-chip-${st}` }, statusChipLabel(st)));
}

function renderList() {
  if (!progressEl) return;
  progressEl.textContent = progressLine();
  tabsWrapEl.innerHTML = '';
  tabsWrapEl.appendChild(tabsBar());
  listEl.innerHTML = '';
  const list = currentList();
  if (!list.length) {
    listEl.appendChild(h('div', { class: 'muted idf-empty-list' }, 'Nothing here.'));
    return;
  }
  list.forEach((p) => listEl.appendChild(ideaRow(p)));
}

// ---- left panel: header / hook / why / actions --------------------------

function metaLine(p, idx, total) {
  const dur = fmtDur(proposalDuration(p));
  const score = p.score != null ? p.score.toFixed(1) : '—';
  return `${dur} · score ${score} · #${idx + 1} of ${total}`;
}

function whyThisWorks(p) {
  const full = p.summary || '';
  const first = firstSentence(full);
  const hasMore = full.length > first.length;
  return h('div', { class: 'idf-why' },
    h('span', { class: 'muted' }, 'Why this works — '),
    h('span', { class: 'idf-why-text' }, (summaryExpanded ? full : first) || '—'),
    hasMore ? h('button', {
      class: 'btn-link idf-why-toggle',
      onclick: () => { summaryExpanded = !summaryExpanded; renderBody(); },
    }, summaryExpanded ? ' less' : ' more') : null);
}

function renderHeader() {
  if (!headerEl) return;
  headerEl.innerHTML = '';
  const p = selectedProposal();
  if (!p) return;
  const idx = proposals().findIndex((x) => x.id === p.id);
  headerEl.append(
    h('h1', { class: 'idf-title' }, p.title),
    h('div', { class: 'muted idf-meta' }, metaLine(p, idx, proposals().length)),
    h('a', { class: 'btn-link idf-adjust-link', href: `#/rec/${recId}?p=${p.id}` }, 'Adjust cut / transcript'));
}

function renderBody() {
  if (!bodyEl) return;
  bodyEl.innerHTML = '';
  const p = selectedProposal();
  if (!p) return;
  bodyEl.append(
    p.hook ? h('div', { class: 'idf-hook' }, `“${p.hook}”`) : null,
    whyThisWorks(p));
}

function renderActions() {
  if (!actionsEl) return;
  actionsEl.innerHTML = '';
  const p = selectedProposal();
  if (!p) return;
  const st = statusOf(p);
  const approveBtn = h('button', {
    class: 'btn btn-primary idf-big',
    disabled: st === 'clip',
    onclick: () => approveIdea(p.id),
  }, st === 'clip' ? '✓ Made into a clip' : '✓ Make this a clip');
  const skipBtn = h('button', {
    class: 'btn btn-ghost idf-big',
    disabled: st === 'skipped',
    onclick: () => skipIdea(p.id),
  }, st === 'skipped' ? '✗ Skipped' : '✗ Skip');
  const nextBtn = h('button', { class: 'btn btn-ghost idf-big', onclick: () => stepNext(1) }, 'Next →');
  actionsEl.append(approveBtn, skipBtn, nextBtn);
  if (st === 'clip' && p.clip_id) {
    actionsEl.append(h('a', { class: 'btn-link idf-clip-link', href: `#/clip/${p.clip_id}` }, 'Open the clip →'));
  }
}

function renderMain() {
  renderHeader();
  renderBody();
  renderActions();
}

// ---- selection / navigation ----------------------------------------------

function selectProposal(pid, autoplay) {
  clearCountdown();
  selectedPid = pid;
  summaryExpanded = false;
  renderMain();
  renderList();
  const p = selectedProposal();
  if (!p) return;
  updateClock(0, proposalDuration(p));
  if (autoplay) {
    // Seeks to the first range's start and starts playing immediately (playRanges
    // does the seek synchronously), so there's no separate "preload" step needed.
    player.playRanges(p.ranges);
  } else {
    player.seek(p.ranges[0][0]);
  }
}

function stepNext(dir) {
  clearCountdown();
  const list = currentList();
  if (!list.length) return;
  const idx = list.findIndex((p) => p.id === selectedPid);
  const next = idx === -1 ? list[0] : list[(idx + dir + list.length) % list.length];
  selectProposal(next.id, true);
}

// ---- decisions -------------------------------------------------------

async function refetchRecording() {
  try {
    rec = await get(`/api/recordings/${recId}`);
  } catch (e) {
    toast('Could not refresh', 'err');
  }
}

async function afterDecision(decidedPid) {
  await refetchRecording();
  const next = nextUndecidedAfter(decidedPid);
  if (next) {
    selectProposal(next.id, true);
  } else {
    selectedPid = decidedPid;
    renderMain();
    renderList();
    toast('No more undecided ideas here');
  }
}

async function approveIdea(pid) {
  clearCountdown();
  try {
    const res = await post(`/api/recordings/${recId}/proposals/${pid}/approve`);
    toast(res.clip ? `Made into a clip — ${res.clip.id}` : 'Approved');
    lastDecision = { pid, action: 'approve' };
    await afterDecision(pid);
    refresh();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function skipIdea(pid) {
  clearCountdown();
  try {
    await post(`/api/recordings/${recId}/proposals/${pid}/reject`);
    toast('Skipped');
    lastDecision = { pid, action: 'reject' };
    await afterDecision(pid);
    refresh();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function undoLast() {
  if (!lastDecision) {
    toast('Nothing to undo');
    return;
  }
  if (lastDecision.action !== 'reject') {
    toast("Approved ideas can't be undone here — open the clip from the Clips board.", 'err');
    return;
  }
  const { pid } = lastDecision;
  try {
    await patch(`/api/recordings/${recId}/proposals/${pid}`, { status: 'proposed' });
    lastDecision = null;
    toast('Undone');
    await refetchRecording();
    selectProposal(pid, true);
    refresh();
  } catch (e) {
    toast(e.message, 'err');
  }
}

// ---- keyboard --------------------------------------------------------

function isTyping(e) {
  const t = e.target;
  return !!(t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable));
}

function onKeydown(e) {
  if (isTyping(e)) return;
  switch (e.key) {
    case ' ':
      e.preventDefault();
      togglePlay();
      break;
    case 'a': case 'A':
      if (selectedPid) approveIdea(selectedPid);
      break;
    case 'r': case 'R':
      if (selectedPid) skipIdea(selectedPid);
      break;
    case 'j': case 'J': case 'ArrowRight':
      stepNext(1);
      break;
    case 'k': case 'K': case 'ArrowLeft':
      stepNext(-1);
      break;
    case 'u': case 'U':
      undoLast();
      break;
    default:
      return;
  }
}

// ---- skeleton / mount --------------------------------------------------

function buildSkeleton() {
  root.innerHTML = '';
  const left = h('div', { class: 'idf-left' });
  const right = h('div', { class: 'idf-right' });
  root.appendChild(h('div', { class: 'split idf-split' }, left, right));

  headerEl = h('div', { class: 'idf-header' });
  playerOuterEl = h('div', { class: 'idf-player-outer' });
  bodyEl = h('div', { class: 'idf-body' });
  actionsEl = h('div', { class: 'row idf-actions' });

  player = createPlayer(playerOuterEl, {
    src: rec.media_url,
    aspect: '16/9',
    onTime: onPlayerTime,
    onPlayState: onPlayerPlayState,
  });
  player.video.preload = 'auto'; // this whole feed is watching -- prefetch aggressively

  playPauseBtn = h('button', { class: 'btn-icon idf-clock-play', onclick: togglePlay }, '▶');
  clockFillEl = h('div', { class: 'idf-clock-fill' });
  clockHeadEl = h('div', { class: 'idf-clock-head' });
  clockTimeEl = h('span', { class: 'idf-clock-time' }, '0:00 / 0:00');
  const clockTrack = h('div', { class: 'idf-clock-track', onclick: onClockTrackClick }, clockFillEl, clockHeadEl);
  const clockBar = h('div', { class: 'row idf-clock' }, playPauseBtn, clockTrack, clockTimeEl);

  left.append(headerEl, playerOuterEl, clockBar, bodyEl, actionsEl);

  countdownEl = h('div', { class: 'idf-countdown' },
    h('span', { class: 'idf-countdown-text' }, ''),
    h('button', { class: 'btn btn-ghost idf-mini', onclick: clearCountdown }, 'Cancel'));
  countdownEl.style.display = 'none';
  playerOuterEl.appendChild(countdownEl);

  progressEl = h('div', { class: 'muted idf-progress' });
  tabsWrapEl = h('div', { class: 'idf-tabs-wrap' });
  listEl = h('div', { class: 'idf-list' });
  right.append(progressEl, tabsWrapEl, listEl);
}

async function loadAll(id) {
  recId = id;
  rec = await get(`/api/recordings/${id}`);
  if (!proposals().length) {
    root.innerHTML = '';
    root.appendChild(h('div', { class: 'panel idf-empty-recording' },
      h('h3', {}, 'No ideas yet'),
      h('p', { class: 'muted' }, 'This recording has no clip-idea proposals yet.'),
      h('a', { class: 'btn btn-primary', href: `#/rec/${id}` }, 'Open the recording')));
    return;
  }
  buildSkeleton();
  const firstUndecided = proposals().find((p) => statusOf(p) === 'undecided');
  selectedPid = (firstUndecided || proposals()[0]).id;
  renderMain();
  renderList();
  updateClock(0, proposalDuration(selectedProposal()));
  player.playRanges(selectedProposal().ranges);
}

const view = {
  async mount(el, params) {
    root = el;
    root.classList.add('idf-view');
    root.appendChild(h('div', { class: 'muted idf-loading' }, 'Loading ideas…'));
    onKeydownRef = onKeydown;
    window.addEventListener('keydown', onKeydownRef);
    try {
      await loadAll(params.id);
    } catch (e) {
      root.innerHTML = '';
      root.appendChild(h('div', { class: 'panel idf-error-panel' }, `Failed to load ideas: ${e.message}`));
    }
  },
  unmount() {
    if (onKeydownRef) window.removeEventListener('keydown', onKeydownRef);
    onKeydownRef = null;
    clearCountdown();
    if (player) { player.destroy(); player = null; }
    root = null; rec = null; recId = null; selectedPid = null;
    lastDecision = null; filterTab = 'undecided'; summaryExpanded = false;
    headerEl = null; bodyEl = null; actionsEl = null; playerOuterEl = null;
    countdownEl = null; playPauseBtn = null; clockFillEl = null; clockHeadEl = null; clockTimeEl = null;
    progressEl = null; tabsWrapEl = null; listEl = null;
  },
};

registerView('ideas', view);
