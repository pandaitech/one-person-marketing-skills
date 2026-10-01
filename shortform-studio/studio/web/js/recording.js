// Recording view (#/rec/<id>?p=<pid>) — player + full-class timeline + transcript on the
// left, the clip-bank triage (AI-proposed candidate clips) on the right.
import { get, post, patch } from './api.js';
import {
  h, fmtTime, fmtDur, parseTime, relTime, md, statusPill, toast, debounce, escapeHtml,
} from './util.js';
import { createPlayer } from './player.js';
import { registerView, refresh } from './app.js';

// ---- module state (one recording view is ever mounted at a time) --------

let root = null;
let recId = null;
let rec = null;                  // full Recording object from the API
let transcript = null;           // {segments:[[s,e,text]], words:[[w,s,e]]}
let player = null;
let selectedPid = null;
let zoomMode = 'full';           // 'full' | 'zoom'
let filterStatus = 'proposed';   // proposed | approved | rejected | needs_changes | all
let sortMode = 'score';          // score | time
let curTime = 0;
let followOn = true;
let searchQuery = '';
let searchMatches = [];          // segment indices
let searchIndex = -1;
let editingLocked = false;       // an input/textarea in the right panel has focus
let pendingRender = false;
let fastTimer = null;
let generalNotesOpen = false;
let hoveredBandText = null;
let pendingSelection = null;     // {start, end, text} from a transcript text selection

let segmentEls = [];             // DOM rows, index-aligned with transcript.segments
let taggedSegments = new Set();  // segment indices currently rendered as word-spans
let lastActiveSegment = -1;

let timelineEl = null;
let transcriptEl = null;
let rightScrollEl = null;
let tipEl = null;
let toolbarEl = null;
let onSelectionChangeRef = null;
let onKeydownRef = null;

// ---- small pure helpers ---------------------------------------------------

function rangesTotal(ranges) {
  return (ranges || []).reduce((sum, r) => sum + Math.max(0, r[1] - r[0]), 0);
}

function proposalById(pid) {
  return (rec.proposals || []).find((p) => p.id === pid) || null;
}

function segmentIndexAt(t) {
  const segs = transcript.segments;
  if (!segs || !segs.length) return -1;
  for (let i = 0; i < segs.length; i++) {
    if (t >= segs[i][0] && t < segs[i][1]) return i;
  }
  for (let i = segs.length - 1; i >= 0; i--) {
    if (segs[i][0] <= t) return i;
  }
  return 0;
}

function wordsInRange(words, start, end) {
  return (words || []).filter((w) => w[1] >= start - 0.001 && w[2] <= end + 0.001);
}

function keptTranscript(proposal) {
  if (!transcript) return '';
  return (proposal.ranges || [])
    .map((r) => wordsInRange(transcript.words, r[0], r[1]).map((w) => w[0]).join(' '))
    .filter(Boolean)
    .join(' … ');
}

function segmentsNear(ranges) {
  const segs = transcript.segments;
  const hit = new Set();
  ranges.forEach(([s, e]) => {
    segs.forEach((seg, i) => {
      if (seg[0] < e && seg[1] > s) {
        hit.add(i - 1); hit.add(i); hit.add(i + 1);
      }
    });
  });
  return hit;
}

function selectedRangeSpan(proposal) {
  const starts = proposal.ranges.map((r) => r[0]);
  const ends = proposal.ranges.map((r) => r[1]);
  return [Math.max(0, Math.min(...starts) - 20), Math.min(rec.duration || Infinity, Math.max(...ends) + 20)];
}

// ---- player / seeking -----------------------------------------------------

function seekTo(t) {
  player.seek(t);
  curTime = t;
  onPlayerTime(t);
}

function onPlayerTime(t) {
  curTime = t;
  updatePlayhead();
  const idx = segmentIndexAt(t);
  if (idx !== lastActiveSegment) {
    if (lastActiveSegment >= 0 && segmentEls[lastActiveSegment]) {
      segmentEls[lastActiveSegment].classList.remove('rec-seg-active');
    }
    if (idx >= 0 && segmentEls[idx]) {
      segmentEls[idx].classList.add('rec-seg-active');
      if (followOn) segmentEls[idx].scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
    lastActiveSegment = idx;
  }
}

function updatePlayhead() {
  const head = timelineEl && timelineEl.querySelector('.rec-playhead');
  if (!head) return;
  const start = parseFloat(timelineEl.dataset.start || '0');
  const end = parseFloat(timelineEl.dataset.end || String(rec.duration || 0));
  const span = Math.max(0.001, end - start);
  head.style.left = `${Math.min(100, Math.max(0, ((curTime - start) / span) * 100))}%`;
}

// ---- timeline ---------------------------------------------------------

function xToTime(e) {
  const rect = timelineEl.getBoundingClientRect();
  const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  const start = parseFloat(timelineEl.dataset.start || '0');
  const end = parseFloat(timelineEl.dataset.end || String(rec.duration || 0));
  return start + frac * (end - start);
}

function setZoom(mode) {
  zoomMode = mode;
  renderTimeline();
}

function addRangeHandles(bandEl, proposal, rangeIdx) {
  ['start', 'end'].forEach((edge) => {
    const handle = h('div', { class: `rec-handle rec-handle-${edge}` });
    handle.addEventListener('mousedown', (e) => {
      e.stopPropagation();
      e.preventDefault();
      const onMove = (ev) => {
        const t = xToTime(ev);
        const ranges = proposal.ranges.map((r) => r.slice());
        if (edge === 'start') ranges[rangeIdx][0] = Math.min(t, ranges[rangeIdx][1] - 0.1);
        else ranges[rangeIdx][1] = Math.max(t, ranges[rangeIdx][0] + 0.1);
        proposal.ranges = ranges;
        renderTimeline();
        updateRangeEditorInputs(proposal);
      };
      const onUp = async () => {
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
        try {
          const updated = await patch(`/api/recordings/${recId}/proposals/${proposal.id}`, { ranges: proposal.ranges });
          Object.assign(proposal, updated);
          renderTimeline();
          updateRangeEditorInputs(proposal);
        } catch (err) {
          toast(err.message, 'err');
        }
      };
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    });
    bandEl.appendChild(handle);
  });
}

function renderTimeline() {
  if (!timelineEl) return;
  timelineEl.innerHTML = '';
  timelineEl.style.backgroundImage = rec.waveform_url ? `url(${rec.waveform_url})` : 'none';
  const selected = selectedPid && proposalById(selectedPid);
  const zoomed = zoomMode === 'zoom' && selected;
  const [spanStart, spanEnd] = zoomed ? selectedRangeSpan(selected) : [0, rec.duration || 0];
  timelineEl.dataset.start = String(spanStart);
  timelineEl.dataset.end = String(spanEnd);
  const span = Math.max(0.001, spanEnd - spanStart);
  const leftPct = (t) => Math.min(100, Math.max(0, ((t - spanStart) / span) * 100));

  (rec.proposals || []).forEach((p) => {
    (p.ranges || []).forEach((r, ri) => {
      if (r[1] < spanStart || r[0] > spanEnd) return;
      const l = leftPct(r[0]);
      const w = Math.max(0.15, leftPct(r[1]) - l);
      const band = h('div', {
        class: `rec-band rec-band-${p.status}${p.id === selectedPid ? ' rec-band-selected' : ''}`,
        style: `left:${l}%;width:${w}%`,
        onclick: (e) => { e.stopPropagation(); selectProposal(p.id); seekTo(r[0]); },
        onmouseenter: () => { hoveredBandText = p.title; },
        onmouseleave: () => { hoveredBandText = null; },
      });
      timelineEl.appendChild(band);
      if (zoomed && p.id === selectedPid) addRangeHandles(band, p, ri);
    });
  });

  (rec.comments || []).forEach((c) => {
    if (c.t == null || c.t < spanStart || c.t > spanEnd) return;
    timelineEl.appendChild(h('div', { class: 'rec-note-marker', style: `left:${leftPct(c.t)}%`, title: c.text }));
  });

  timelineEl.appendChild(h('div', { class: 'rec-playhead', style: `left:${leftPct(curTime)}%` }));
}

// ---- transcript -------------------------------------------------------

function segTextWords(seg, tintRanges) {
  const words = wordsInRange(transcript.words, seg[0] - 0.01, seg[1] + 0.01);
  const frag = document.createDocumentFragment();
  if (!words.length) {
    frag.appendChild(document.createTextNode(seg[2]));
    return frag;
  }
  words.forEach((w) => {
    const inRange = tintRanges.some((r) => w[1] >= r[0] - 0.05 && w[2] <= r[1] + 0.05);
    frag.appendChild(h('span', {
      class: inRange ? 'rec-word rec-word-kept' : 'rec-word',
      dataset: { s: String(w[1]), e: String(w[2]) },
    }, w[0]));
    frag.appendChild(document.createTextNode(' '));
  });
  return frag;
}

function buildTranscript() {
  transcriptEl.innerHTML = '';
  segmentEls = transcript.segments.map((seg, i) => {
    const row = h('div', {
      class: 'rec-seg',
      dataset: { i: String(i) },
      onclick: () => {
        if (window.getSelection().toString()) return; // don't seek away from an in-progress selection
        seekTo(seg[0]);
      },
    },
      h('span', { class: 'rec-seg-time' }, fmtTime(seg[0])),
      h('span', { class: 'rec-seg-text' }, seg[2]));
    transcriptEl.appendChild(row);
    return row;
  });
  taggedSegments = new Set();
  refreshSelectionTint();
}

function refreshSelectionTint() {
  const prev = taggedSegments;
  const selected = selectedPid && proposalById(selectedPid);
  const next = selected ? segmentsNear(selected.ranges) : new Set();
  const touch = new Set([...prev, ...next]);
  touch.forEach((i) => {
    if (i < 0 || i >= transcript.segments.length) return;
    const row = segmentEls[i];
    if (!row) return;
    const textEl = row.querySelector('.rec-seg-text');
    textEl.innerHTML = '';
    if (next.has(i)) {
      textEl.appendChild(segTextWords(transcript.segments[i], selected.ranges));
    } else {
      textEl.textContent = transcript.segments[i][2];
    }
  });
  taggedSegments = next;
  applySearchHighlight();
}

function highlightText(text, q) {
  const esc = escapeHtml(text);
  const qEsc = escapeHtml(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  if (!qEsc) return esc;
  const re = new RegExp(qEsc, 'ig');
  return esc.replace(re, (m) => `<mark class="rec-mark">${m}</mark>`);
}

function clearSearchHighlight() {
  segmentEls.forEach((row, i) => {
    const textEl = row.querySelector('.rec-seg-text');
    if (taggedSegments.has(i)) {
      textEl.querySelectorAll('.rec-word-match').forEach((s) => s.classList.remove('rec-word-match'));
    } else if (textEl.querySelector('mark')) {
      textEl.textContent = transcript.segments[i][2];
    }
  });
}

function applySearchHighlight() {
  clearSearchHighlight();
  searchMatches = [];
  if (!searchQuery) { updateSearchCount(); return; }
  const q = searchQuery.toLowerCase();
  transcript.segments.forEach((seg, i) => {
    if (seg[2].toLowerCase().includes(q)) searchMatches.push(i);
  });
  searchMatches.forEach((i) => {
    const textEl = segmentEls[i].querySelector('.rec-seg-text');
    if (taggedSegments.has(i)) {
      textEl.querySelectorAll('.rec-word').forEach((span) => {
        if (span.textContent.toLowerCase().includes(q)) span.classList.add('rec-word-match');
      });
    } else {
      textEl.innerHTML = highlightText(transcript.segments[i][2], searchQuery);
    }
  });
  updateSearchCount();
}

function updateSearchCount() {
  const countEl = root.querySelector('.rec-search-count');
  if (!countEl) return;
  if (!searchQuery) { countEl.textContent = ''; return; }
  countEl.textContent = searchMatches.length ? `${searchIndex + 1}/${searchMatches.length}` : '0/0';
}

function jumpSearch(dir) {
  if (!searchMatches.length) return;
  searchIndex = (searchIndex + dir + searchMatches.length) % searchMatches.length;
  const segIdx = searchMatches[searchIndex];
  seekTo(transcript.segments[segIdx][0]);
  segmentEls[segIdx].scrollIntoView({ block: 'center', behavior: 'smooth' });
  updateSearchCount();
}

// ---- text-selection → new clip / note toolbar --------------------------

function closestWithClass(node, cls) {
  const el = node.nodeType === 3 ? node.parentElement : node;
  return el && el.closest ? el.closest(cls) : null;
}

function selectionTimes(range) {
  const startRow = closestWithClass(range.startContainer, '.rec-seg');
  const endRow = closestWithClass(range.endContainer, '.rec-seg');
  if (!startRow || !endRow) return null;
  const startIdx = Number(startRow.dataset.i);
  const endIdx = Number(endRow.dataset.i);
  const startWord = closestWithClass(range.startContainer, '.rec-word');
  const endWord = closestWithClass(range.endContainer, '.rec-word');
  const start = startWord ? Number(startWord.dataset.s) : transcript.segments[startIdx][0];
  const end = endWord ? Number(endWord.dataset.e) : transcript.segments[endIdx][1];
  return { start, end };
}

function onSelectionChange() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !transcriptEl || !transcriptEl.contains(sel.anchorNode)) {
    toolbarEl.style.display = 'none';
    pendingSelection = null;
    return;
  }
  const range = sel.getRangeAt(0);
  const times = selectionTimes(range);
  if (!times || times.end <= times.start) {
    toolbarEl.style.display = 'none';
    pendingSelection = null;
    return;
  }
  pendingSelection = { ...times, text: sel.toString().trim().slice(0, 300) };
  const rect = range.getBoundingClientRect();
  toolbarEl.style.left = `${rect.left + rect.width / 2}px`;
  toolbarEl.style.top = `${window.scrollY + rect.top - 40}px`;
  toolbarEl.style.display = 'flex';
}

async function onNewClipFromSelection() {
  if (!pendingSelection) return;
  const { start, end, text } = pendingSelection;
  const title = text.split(/\s+/).slice(0, 6).join(' ') || 'New clip';
  try {
    const p = await post(`/api/recordings/${recId}/proposals`, { title, ranges: [[start, end]], author: 'director' });
    rec.proposals = rec.proposals || [];
    rec.proposals.push(p);
    toolbarEl.style.display = 'none';
    window.getSelection().removeAllRanges();
    selectProposal(p.id);
    renderRight();
    toast('Proposal created');
  } catch (e) {
    toast(e.message, 'err');
  }
}

function onNoteFromSelection() {
  if (!pendingSelection) return;
  player.pause();
  curTime = pendingSelection.start;
  toolbarEl.style.display = 'none';
  window.getSelection().removeAllRanges();
  focusComposer(selectedPid);
}

function focusComposer(pid) {
  if (pid) {
    const ta = root.querySelector(`.rec-proposal-editor[data-id="${pid}"] .rec-composer-input`);
    if (ta) { ta.focus(); return; }
  }
  generalNotesOpen = true;
  renderRight();
  const ta2 = rightScrollEl.querySelector('.rec-general-notes .rec-composer-input');
  if (ta2) ta2.focus();
}

// ---- right panel: header / filters -------------------------------------

function agentLine() {
  const a = rec.agent || {};
  const parts = [statusPill(rec.status)];
  if (a.state === 'working') parts.push(h('span', { class: 'muted' }, 'Claude is finding clips…'));
  else if (a.state === 'queued') parts.push(h('span', { class: 'muted' }, 'Queued for Claude'));
  else if (a.state === 'error') {
    parts.push(h('span', { class: 'muted rec-error' }, a.message || 'Error'));
    parts.push(h('button', { class: 'btn btn-ghost rec-mini', onclick: retryDispatch }, 'Retry'));
  }
  return parts;
}

async function retryDispatch() {
  try {
    await post(`/api/recordings/${recId}/dispatch`);
    toast('Dispatched');
    refetchRecording();
  } catch (e) {
    toast(e.message, 'err');
  }
}

function renderHeader() {
  const el = root.querySelector('.rec-right-header');
  if (!el) return;
  el.innerHTML = '';
  el.append(
    h('h2', { class: 'rec-right-title' }, rec.title),
    h('div', { class: 'muted rec-right-meta' }, rec.date || '', rec.date ? ' · ' : '', fmtDur(rec.duration || 0)),
    h('div', { class: 'row rec-agent-line' }, agentLine()));
}

function proposalCounts() {
  const counts = { proposed: 0, approved: 0, rejected: 0, needs_changes: 0 };
  (rec.proposals || []).forEach((p) => { if (counts[p.status] != null) counts[p.status] += 1; });
  return counts;
}

function renderFilters() {
  const el = root.querySelector('.rec-filters');
  if (!el) return;
  el.innerHTML = '';
  const counts = proposalCounts();
  const total = (rec.proposals || []).length;
  const options = [
    ['proposed', 'Proposed', counts.proposed],
    ['approved', 'Approved', counts.approved],
    ['rejected', 'Rejected', counts.rejected],
    ['needs_changes', 'Needs changes', counts.needs_changes],
    ['all', 'All', total],
  ];
  options.forEach(([key, label, n]) => {
    el.appendChild(h('button', {
      class: `chip rec-filter-chip${filterStatus === key ? ' rec-filter-active' : ''}`,
      onclick: () => { filterStatus = key; renderProposalList(); },
    }, `${label} (${n})`));
  });
  const sortSel = h('select', {
    class: 'rec-sort',
    onchange: (e) => { sortMode = e.target.value; renderProposalList(); },
  },
    h('option', { value: 'score' }, 'Score'),
    h('option', { value: 'time' }, 'Time'));
  sortSel.value = sortMode;
  el.appendChild(sortSel);
}

// ---- right panel: proposal cards + editor -------------------------------

function filteredSortedProposals() {
  let list = rec.proposals || [];
  if (filterStatus !== 'all') list = list.filter((p) => p.status === filterStatus);
  list = list.slice();
  if (sortMode === 'score') list.sort((a, b) => (b.score || 0) - (a.score || 0));
  else list.sort((a, b) => ((a.ranges[0] || [0])[0]) - ((b.ranges[0] || [0])[0]));
  return list;
}

function renderProposalList() {
  const el = root.querySelector('.rec-proposal-list');
  if (!el) return;
  el.innerHTML = '';
  const list = filteredSortedProposals();
  if (!list.length) {
    el.appendChild(h('div', { class: 'muted rec-empty-list' }, 'No proposals here yet.'));
    return;
  }
  list.forEach((p) => el.appendChild(proposalCard(p)));
}

function proposalCard(p) {
  const isSelected = p.id === selectedPid;
  const cardEl = h('div', {
    class: `card rec-proposal${isSelected ? ' rec-proposal-selected' : ''}`,
    dataset: { id: p.id },
    onclick: (e) => {
      if (e.target.closest('.rec-range-chip') || e.target.closest('a') || e.target.closest('.rec-proposal-editor')) return;
      selectProposal(p.id);
    },
  },
    h('div', { class: 'row rec-proposal-top' },
      h('span', { class: 'rec-proposal-score' }, p.score != null ? p.score.toFixed(1) : '—'),
      h('span', { class: 'rec-proposal-title' }, p.title),
      statusPill(p.status)),
    h('div', { class: 'muted rec-proposal-dur' }, fmtDur(rangesTotal(p.ranges))),
    p.hook ? h('div', { class: 'rec-proposal-hook' }, `“${p.hook}”`) : null,
    h('div', { class: 'row rec-range-chips' }, (p.ranges || []).map((r) => h('button', {
      class: 'chip rec-range-chip',
      onclick: (e) => { e.stopPropagation(); seekTo(r[0]); },
    }, `${fmtTime(r[0])}–${fmtTime(r[1])}`))),
    p.summary ? h('div', { class: `rec-proposal-summary${isSelected ? ' rec-proposal-summary-full' : ''}` }, p.summary) : null,
    (p.status === 'approved' && p.clip_id)
      ? h('a', { class: 'rec-clip-link', href: `#/clip/${p.clip_id}` }, 'clip →')
      : null);
  if (isSelected) cardEl.appendChild(proposalEditor(p));
  return cardEl;
}

function updateRangeEditorInputs(p) {
  const rowsEl = root.querySelector(`.rec-proposal-editor[data-id="${p.id}"] .rec-range-rows`);
  if (!rowsEl) return;
  p.ranges.forEach((r, i) => {
    const rowEl = rowsEl.children[i];
    if (!rowEl) return;
    const startInput = rowEl.querySelector('.rec-range-start');
    const endInput = rowEl.querySelector('.rec-range-end');
    if (startInput && document.activeElement !== startInput) startInput.value = fmtTime(r[0]);
    if (endInput && document.activeElement !== endInput) endInput.value = fmtTime(r[1]);
    const lenEl = rowEl.querySelector('.rec-range-len');
    if (lenEl) lenEl.textContent = fmtDur(r[1] - r[0]);
  });
  const totalEl = root.querySelector(`.rec-proposal-editor[data-id="${p.id}"] .rec-range-total`);
  if (totalEl) totalEl.textContent = fmtDur(rangesTotal(p.ranges));
  const keptEl = root.querySelector(`.rec-proposal-editor[data-id="${p.id}"] .rec-kept-text`);
  if (keptEl) keptEl.textContent = keptTranscript(p) || '—';
}

async function saveProposal(pid, body, editorOnly) {
  try {
    const updated = await patch(`/api/recordings/${recId}/proposals/${pid}`, body);
    Object.assign(proposalById(pid), updated);
    if (editorOnly) {
      renderTimeline();
      renderProposalList();
    } else {
      renderRight();
    }
  } catch (e) {
    toast(e.message, 'err');
  }
}

function moveRange(p, i, dir) {
  const j = i + dir;
  if (j < 0 || j >= p.ranges.length) return;
  const tmp = p.ranges[i];
  p.ranges[i] = p.ranges[j];
  p.ranges[j] = tmp;
  saveProposal(p.id, { ranges: p.ranges }, true);
}

function removeRange(p, i) {
  if (p.ranges.length <= 1) { toast('A proposal needs at least one range', 'err'); return; }
  p.ranges = p.ranges.filter((_, idx) => idx !== i);
  saveProposal(p.id, { ranges: p.ranges }, true);
}

function rangeRow(p, i) {
  const r = p.ranges[i];
  const startInput = h('input', {
    class: 'rec-range-start',
    value: fmtTime(r[0]),
    onfocus: () => { editingLocked = true; },
    onchange: (e) => {
      editingLocked = false;
      const t = parseTime(e.target.value);
      if (Number.isFinite(t) && t < p.ranges[i][1]) { p.ranges[i][0] = t; saveProposal(p.id, { ranges: p.ranges }, true); } else {
        toast('Start must be before end', 'err');
        e.target.value = fmtTime(p.ranges[i][0]);
      }
      if (pendingRender) { pendingRender = false; renderRight(); }
    },
  });
  const endInput = h('input', {
    class: 'rec-range-end',
    value: fmtTime(r[1]),
    onfocus: () => { editingLocked = true; },
    onchange: (e) => {
      editingLocked = false;
      const t = parseTime(e.target.value);
      if (Number.isFinite(t) && t > p.ranges[i][0]) { p.ranges[i][1] = t; saveProposal(p.id, { ranges: p.ranges }, true); } else {
        toast('End must be after start', 'err');
        e.target.value = fmtTime(p.ranges[i][1]);
      }
      if (pendingRender) { pendingRender = false; renderRight(); }
    },
  });
  const nudge = (edge, delta) => () => {
    const val = p.ranges[i][edge] + delta;
    if (edge === 0 && val >= p.ranges[i][1]) return;
    if (edge === 1 && val <= p.ranges[i][0]) return;
    p.ranges[i][edge] = Math.max(0, val);
    saveProposal(p.id, { ranges: p.ranges }, true);
  };
  return h('div', { class: 'row rec-range-row' },
    startInput,
    h('button', { class: 'btn btn-ghost rec-mini', title: 'start = playhead', onclick: () => { p.ranges[i][0] = curTime; saveProposal(p.id, { ranges: p.ranges }, true); } }, '⤓'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: nudge(0, -0.1) }, '−0.1'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: nudge(0, 0.1) }, '+0.1'),
    h('span', { class: 'muted' }, '–'),
    endInput,
    h('button', { class: 'btn btn-ghost rec-mini', title: 'end = playhead', onclick: () => { p.ranges[i][1] = curTime; saveProposal(p.id, { ranges: p.ranges }, true); } }, '⤒'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: nudge(1, -0.1) }, '−0.1'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: nudge(1, 0.1) }, '+0.1'),
    h('span', { class: 'muted rec-range-len' }, fmtDur(r[1] - r[0])),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: () => moveRange(p, i, -1) }, '↑'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: () => moveRange(p, i, 1) }, '↓'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: () => removeRange(p, i) }, '✕'));
}

function rangeEditor(p) {
  const rowsEl = h('div', { class: 'stack rec-range-rows' });
  p.ranges.forEach((r, i) => rowsEl.appendChild(rangeRow(p, i)));
  return h('div', { class: 'rec-range-editor' },
    rowsEl,
    h('div', { class: 'row' },
      h('button', {
        class: 'btn btn-ghost rec-mini',
        onclick: () => {
          p.ranges = p.ranges.concat([[curTime, curTime + 10]]);
          saveProposal(p.id, { ranges: p.ranges }, true);
        },
      }, '+ Add range'),
      h('span', { class: 'muted' }, 'Total:'),
      h('span', { class: 'rec-range-total' }, fmtDur(rangesTotal(p.ranges)))));
}

function commentRow(c, all) {
  const replies = all.filter((r) => r.parent === c.id);
  const textEl = h('div', { class: 'rec-comment-text' });
  textEl.innerHTML = md(c.text);
  const rowEl = h('div', { class: `rec-comment rec-comment-${c.status}` },
    h('div', { class: 'row' },
      h('span', { class: 'rec-comment-author' }, c.author),
      c.t != null
        ? h('button', { class: 'chip', onclick: () => seekTo(c.t) }, fmtTime(c.t))
        : h('span', { class: 'muted' }, 'whole proposal'),
      h('span', { class: 'muted' }, relTime(c.created)),
      statusPill(c.status)),
    textEl);
  replies.forEach((r) => {
    const replyText = h('div', { class: 'rec-comment-text' });
    replyText.innerHTML = md(r.text);
    rowEl.appendChild(h('div', { class: 'rec-comment rec-comment-reply' },
      h('div', { class: 'row' }, h('span', { class: 'rec-comment-author' }, r.author), h('span', { class: 'muted' }, relTime(r.created))),
      replyText));
  });
  return rowEl;
}

async function submitComposer(pid, textarea, wholeToggle) {
  const text = textarea.value.trim();
  if (!text) return;
  const whole = wholeToggle ? wholeToggle.querySelector('input').checked : false;
  try {
    const c = await post(`/api/recordings/${recId}/comments`, { text, proposal: pid, t: whole ? null : curTime });
    rec.comments = rec.comments || [];
    rec.comments.push(c);
    renderRight();
    toast('Note added');
  } catch (e) {
    toast(e.message, 'err');
  }
}

function composer(pid) {
  let wholeToggle = null;
  const textarea = h('textarea', {
    class: 'rec-composer-input',
    rows: 2,
    placeholder: pid ? 'Note on this proposal… (Enter to add, Shift+Enter for newline)' : 'Note on the whole recording…',
    onfocus: () => { editingLocked = true; },
    onblur: () => { editingLocked = false; if (pendingRender) { pendingRender = false; renderRight(); } },
    onkeydown: (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitComposer(pid, textarea, wholeToggle);
      }
    },
  });
  wholeToggle = pid ? h('label', { class: 'row rec-whole-toggle' },
    h('input', { type: 'checkbox' }), h('span', { class: 'muted' }, 'whole proposal')) : null;
  return h('div', { class: 'rec-composer stack' },
    textarea,
    h('div', { class: 'row' },
      wholeToggle,
      h('button', { class: 'btn btn-primary rec-mini', onclick: () => submitComposer(pid, textarea, wholeToggle) }, 'Add note')));
}

function notesThread(pid) {
  const comments = (rec.comments || []).filter((c) => (c.proposal || null) === pid);
  const wrap = h('div', { class: 'rec-notes stack' }, h('div', { class: 'muted' }, 'Notes'));
  comments.filter((c) => !c.parent).forEach((c) => wrap.appendChild(commentRow(c, comments)));
  wrap.appendChild(composer(pid));
  return wrap;
}

function proposalEditor(p) {
  const wrap = h('div', { class: 'rec-proposal-editor', dataset: { id: p.id } });
  wrap.appendChild(h('div', { class: 'row rec-editor-preview' },
    h('button', { class: 'btn btn-ghost rec-mini', onclick: () => player.playRanges(p.ranges) }, '▶ Preview cut'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: () => player.pause() }, '■ Stop')));

  const titleInput = h('input', {
    class: 'rec-title-input',
    value: p.title,
    onfocus: () => { editingLocked = true; },
    onblur: (e) => {
      editingLocked = false;
      const val = e.target.value.trim();
      if (val && val !== p.title) saveProposal(p.id, { title: val });
      else if (pendingRender) { pendingRender = false; renderRight(); }
    },
  });
  wrap.appendChild(h('label', { class: 'stack rec-field' }, h('span', { class: 'muted' }, 'Title'), titleInput));

  wrap.appendChild(rangeEditor(p));

  wrap.appendChild(h('div', { class: 'rec-kept-preview' },
    h('div', { class: 'muted' }, 'Kept transcript'),
    h('div', { class: 'rec-kept-text' }, keptTranscript(p) || '—')));

  wrap.appendChild(notesThread(p.id));

  const actions = [];
  if (p.status !== 'approved') {
    actions.push(h('button', { class: 'btn btn-primary rec-mini', onclick: () => approveProposal(p.id) }, 'Approve → make clip (A)'));
  }
  if (p.status === 'rejected') {
    actions.push(h('button', { class: 'btn btn-ghost rec-mini', onclick: () => setProposalStatus(p.id, 'proposed') }, 'Restore'));
  } else {
    actions.push(h('button', { class: 'btn btn-ghost rec-mini', onclick: () => setProposalStatus(p.id, 'rejected') }, 'Reject (R)'));
  }
  if (p.status !== 'needs_changes') {
    actions.push(h('button', { class: 'btn btn-ghost rec-mini', onclick: () => needsChanges(p.id) }, 'Needs changes'));
  }
  wrap.appendChild(h('div', { class: 'row rec-editor-actions' }, actions));
  return wrap;
}

async function approveProposal(pid) {
  try {
    const res = await post(`/api/recordings/${recId}/proposals/${pid}/approve`);
    Object.assign(proposalById(pid), res.proposal);
    toast(`Clip created — open it from the "clip →" link or the Board (${res.clip.id})`);
    renderRight();
    refresh();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function setProposalStatus(pid, status) {
  try {
    const updated = await patch(`/api/recordings/${recId}/proposals/${pid}`, { status });
    Object.assign(proposalById(pid), updated);
    renderRight();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function needsChanges(pid) {
  await setProposalStatus(pid, 'needs_changes');
  focusComposer(pid);
}

function renderGeneralNotes() {
  const el = root.querySelector('.rec-general-notes');
  if (!el) return;
  el.innerHTML = '';
  const count = (rec.comments || []).filter((c) => !c.proposal).length;
  el.appendChild(h('button', {
    class: 'rec-notes-toggle',
    onclick: () => { generalNotesOpen = !generalNotesOpen; renderGeneralNotes(); },
  }, `${generalNotesOpen ? '▾' : '▸'} Notes on the whole recording (${count})`));
  if (generalNotesOpen) el.appendChild(notesThread(null));
}

function agentStatusText() {
  const a = rec.agent || {};
  if (a.state === 'working') return 'Claude is finding clips…';
  if (a.state === 'queued') return 'Queued for Claude';
  if (a.state === 'error') return `Error: ${a.message || 'unknown'}`;
  return '';
}

async function sendNotes() {
  try {
    await post(`/api/recordings/${recId}/send`);
    toast('Sent to Claude');
    refetchRecording();
  } catch (e) {
    toast(e.message, 'err');
  }
}

async function findMoreClips() {
  try {
    const hasDraft = (rec.comments || []).some((c) => c.author === 'director' && c.status === 'draft');
    if (!hasDraft) {
      const c = await post(`/api/recordings/${recId}/comments`, { text: 'Find more clips', t: null, proposal: null });
      rec.comments = rec.comments || [];
      rec.comments.push(c);
    }
    await sendNotes();
  } catch (e) {
    toast(e.message, 'err');
  }
}

function renderBottomBar() {
  const el = root.querySelector('.rec-bottombar');
  if (!el) return;
  el.innerHTML = '';
  const draftCount = (rec.comments || []).filter((c) => c.author === 'director' && c.status === 'draft').length;
  el.append(
    h('button', { class: 'btn btn-primary', disabled: !draftCount, onclick: sendNotes }, `Send ${draftCount} notes to Claude`),
    h('button', { class: 'btn btn-ghost', onclick: findMoreClips }, 'Find more clips'),
    h('span', { class: 'muted rec-editor-status' }, agentStatusText()));
}

function renderRight() {
  if (editingLocked) { pendingRender = true; return; }
  renderHeader();
  renderFilters();
  renderProposalList();
  renderGeneralNotes();
  renderBottomBar();
}

function selectProposal(pid) {
  if (selectedPid === pid) return;
  selectedPid = pid;
  history.replaceState(null, '', `#/rec/${recId}${pid ? `?p=${pid}` : ''}`);
  refreshSelectionTint();
  renderTimeline();
  renderProposalList();
  jumpToProposal(pid);
}

// Bring the selected proposal into view: player (paused) and transcript at its first range.
function jumpToProposal(pid) {
  const p = pid && proposalById(pid);
  if (!p || !p.ranges || !p.ranges.length || !player) return;
  if (player.video && !player.video.paused) return; // don't yank the director out of what they're watching
  seekTo(p.ranges[0][0]);
}

// ---- keyboard shortcuts -------------------------------------------------

function stepProposal(dir) {
  const list = filteredSortedProposals();
  if (!list.length) return;
  const idx = list.findIndex((p) => p.id === selectedPid);
  const next = idx === -1 ? list[0] : list[(idx + dir + list.length) % list.length];
  selectProposal(next.id);
}

function setNearestRangeEdge(edge) {
  if (!selectedPid) return;
  const p = proposalById(selectedPid);
  if (!p || !p.ranges.length) return;
  let nearest = 0;
  let best = Infinity;
  p.ranges.forEach((r, i) => {
    const d = Math.min(Math.abs(r[0] - curTime), Math.abs(r[1] - curTime));
    if (d < best) { best = d; nearest = i; }
  });
  p.ranges[nearest][edge] = curTime;
  saveProposal(p.id, { ranges: p.ranges }, true);
}

function onKeydown(e) {
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) {
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  switch (e.key) {
    case ' ':
      e.preventDefault(); player.toggle(); break;
    case 'j': case 'J':
      seekTo(Math.max(0, curTime - 5)); break;
    case 'l': case 'L':
      seekTo(curTime + 5); break;
    case 'ArrowLeft':
      seekTo(Math.max(0, curTime - 1)); break;
    case 'ArrowRight':
      seekTo(curTime + 1); break;
    case 'ArrowUp':
      e.preventDefault(); stepProposal(-1); break;
    case 'ArrowDown':
      e.preventDefault(); stepProposal(1); break;
    case 'p': case 'P':
      if (selectedPid) player.playRanges(proposalById(selectedPid).ranges); break;
    case 'a': case 'A':
      if (selectedPid) approveProposal(selectedPid); break;
    case 'r': case 'R':
      if (selectedPid) setProposalStatus(selectedPid, 'rejected'); break;
    case 'n': case 'N':
      if (selectedPid) focusComposer(selectedPid); break;
    case '[':
      setNearestRangeEdge(0); break;
    case ']':
      setNearestRangeEdge(1); break;
    case 'Escape':
      if (document.activeElement) document.activeElement.blur(); break;
    default:
      return;
  }
}

// ---- polling -------------------------------------------------------------

async function refetchRecording() {
  try {
    const fresh = await get(`/api/recordings/${recId}`);
    rec = fresh;
    if (editingLocked) { pendingRender = true; return; }
    renderTimeline();
    renderRight();
  } catch (e) {
    // transient poll failure — try again on the next tick
  }
}

function maybeStartFastPoll() {
  const a = rec && rec.agent;
  const active = a && (a.state === 'queued' || a.state === 'working');
  if (active && !fastTimer) {
    fastTimer = setInterval(refetchRecording, 2000);
  } else if (!active && fastTimer) {
    clearInterval(fastTimer);
    fastTimer = null;
  }
}

function onGlobalState(state) {
  if (!rec) return;
  const summary = (state.recordings || []).find((r) => r.id === recId);
  if (!summary) return;
  const updatedChanged = rec.updated && summary.updated !== rec.updated;
  rec.agent = summary.agent;
  rec.status = summary.status;
  if (!editingLocked) { renderHeader(); renderBottomBar(); } else { pendingRender = true; }
  if (updatedChanged) refetchRecording();
  maybeStartFastPoll();
}

// ---- skeleton / mount ------------------------------------------------

function buildSkeleton() {
  root.innerHTML = '';
  const left = h('div', { class: 'rec-left' });
  const right = h('div', { class: 'rec-right' });
  root.appendChild(h('div', { class: 'split rec-split' }, left, right));

  const timelineWrap = h('div', { class: 'rec-timeline-wrap' },
    h('div', { class: 'row rec-timeline-controls' },
      h('div', { class: 'rec-zoom-toggle' },
        h('button', {
          class: `btn btn-ghost rec-mini${zoomMode === 'full' ? ' rec-zoom-active' : ''}`,
          onclick: () => setZoom('full'),
        }, 'Full'),
        h('button', {
          class: `btn btn-ghost rec-mini${zoomMode === 'zoom' ? ' rec-zoom-active' : ''}`,
          onclick: () => setZoom('zoom'),
        }, 'Zoom to selected'))));
  timelineEl = h('div', { class: 'rec-timeline' });
  tipEl = h('div', { class: 'rec-timeline-tip' });
  tipEl.style.display = 'none';
  timelineWrap.append(timelineEl, tipEl);

  timelineEl.addEventListener('mousemove', (e) => {
    const t = xToTime(e);
    tipEl.textContent = hoveredBandText ? `${fmtTime(t)} · ${hoveredBandText}` : fmtTime(t);
    tipEl.style.display = 'block';
    tipEl.style.left = `${e.clientX - timelineEl.getBoundingClientRect().left}px`;
  });
  timelineEl.addEventListener('mouseleave', () => { tipEl.style.display = 'none'; });
  timelineEl.addEventListener('mousedown', (e) => {
    if (e.target !== timelineEl) return;
    seekTo(xToTime(e));
    const onMove = (ev) => seekTo(xToTime(ev));
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  });

  const searchInput = h('input', {
    class: 'rec-search',
    placeholder: 'Search transcript…',
    oninput: debounce((e) => { searchQuery = e.target.value.trim(); searchIndex = -1; applySearchHighlight(); }, 200),
    onkeydown: (e) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      jumpSearch(e.shiftKey ? -1 : 1);
    },
  });
  const transcriptWrap = h('div', { class: 'rec-transcript-wrap' },
    h('div', { class: 'row rec-transcript-controls' },
      searchInput,
      h('span', { class: 'muted rec-search-count' }, ''),
      h('label', { class: 'row rec-follow' },
        h('input', { type: 'checkbox', checked: followOn, onchange: (e) => { followOn = e.target.checked; } }),
        h('span', { class: 'muted' }, 'Follow'))));
  transcriptEl = h('div', { class: 'rec-transcript' });
  transcriptWrap.appendChild(transcriptEl);

  left.append(h('div', { class: 'rec-player' }), timelineWrap, transcriptWrap);

  right.append(
    h('div', { class: 'rec-right-scroll' },
      h('div', { class: 'rec-right-header' }),
      h('div', { class: 'row rec-filters' }),
      h('div', { class: 'rec-proposal-list' }),
      h('div', { class: 'rec-general-notes' })),
    h('div', { class: 'row rec-bottombar' }));
  rightScrollEl = right.querySelector('.rec-right-scroll');

  player = createPlayer(left.querySelector('.rec-player'), {
    src: rec.media_url,
    aspect: '16/9',
    onTime: onPlayerTime,
  });

  buildTranscript();
  renderTimeline();
  renderRight();

  toolbarEl = h('div', { class: 'rec-selection-toolbar' },
    h('button', { class: 'btn btn-primary rec-mini', onclick: onNewClipFromSelection }, '+ New clip from selection'),
    h('button', { class: 'btn btn-ghost rec-mini', onclick: onNoteFromSelection }, 'Note here'));
  toolbarEl.style.display = 'none';
  document.body.appendChild(toolbarEl);
}

async function loadAll(id, pid) {
  recId = id;
  selectedPid = pid || null;
  const [recData, transcriptData] = await Promise.all([
    get(`/api/recordings/${id}`),
    get(`/api/recordings/${id}/transcript`),
  ]);
  rec = recData;
  transcript = { segments: transcriptData.segments || [], words: transcriptData.words || [] };
  buildSkeleton();
  maybeStartFastPoll();
  if (selectedPid) jumpToProposal(selectedPid);
}

const view = {
  async mount(el, params, query) {
    root = el;
    root.classList.add('rec-view', 'rec-recording-view');
    root.appendChild(h('div', { class: 'muted rec-loading' }, 'Loading recording…'));
    onSelectionChangeRef = onSelectionChange;
    onKeydownRef = onKeydown;
    document.addEventListener('selectionchange', onSelectionChangeRef);
    window.addEventListener('keydown', onKeydownRef);
    try {
      await loadAll(params.id, query && typeof query.get === 'function' ? query.get('p') : null);
    } catch (e) {
      root.innerHTML = '';
      root.appendChild(h('div', { class: 'panel rec-error-panel' }, `Failed to load recording: ${e.message}`));
    }
  },
  unmount() {
    if (onSelectionChangeRef) document.removeEventListener('selectionchange', onSelectionChangeRef);
    if (onKeydownRef) window.removeEventListener('keydown', onKeydownRef);
    if (fastTimer) { clearInterval(fastTimer); fastTimer = null; }
    if (player) { player.destroy(); player = null; }
    if (toolbarEl && toolbarEl.parentNode) toolbarEl.parentNode.removeChild(toolbarEl);
    toolbarEl = null;
    root = null; rec = null; transcript = null; recId = null; selectedPid = null;
    segmentEls = []; taggedSegments = new Set(); lastActiveSegment = -1;
    searchMatches = []; searchIndex = -1; searchQuery = ''; pendingSelection = null;
    editingLocked = false; pendingRender = false; generalNotesOpen = false;
  },
  onState(state) {
    onGlobalState(state);
  },
};

registerView('recording', view);
