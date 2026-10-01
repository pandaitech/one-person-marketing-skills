// Recordings list (#/recordings) — the entry point of the pipeline: full class
// recordings waiting for the editor to propose clips, or already triaged.
import { post } from './api.js';
import {
  h, fmtDur, relTime, statusPill, toast,
} from './util.js';
import { registerView, getState } from './app.js';

let root = null;

function agentLabel(agent) {
  if (!agent) return '';
  if (agent.state === 'working') return 'Claude is finding clips…';
  if (agent.state === 'queued') return 'Queued for Claude';
  if (agent.state === 'error') return agent.message ? `Error: ${agent.message}` : 'Error';
  return '';
}

function proposalChips(counts) {
  counts = counts || {};
  const kinds = [
    ['proposed', 'Proposed'],
    ['approved', 'Approved'],
    ['rejected', 'Rejected'],
    ['needs_changes', 'Needs changes'],
  ];
  return kinds
    .filter(([key]) => counts[key])
    .map(([key, label]) => h('span', { class: `chip rec-chip-${key}` }, `${counts[key]} ${label}`));
}

async function findClips(rec) {
  try {
    await post(`/api/recordings/${rec.id}/comments`, { text: 'Propose clips from this recording.', t: null });
    await post(`/api/recordings/${rec.id}/send`);
    toast('Sent to Claude');
  } catch (e) {
    toast(e.message, 'err');
  }
}

function card(rec) {
  const label = agentLabel(rec.agent);
  return h('div', { class: 'card rec-card' },
    h('a', {
      class: 'rec-card-poster',
      href: `#/rec/${rec.id}`,
      style: rec.poster_url ? `background-image:url(${rec.poster_url})` : '',
    }),
    h('div', { class: 'rec-card-body' },
      h('a', { class: 'rec-card-title', href: `#/rec/${rec.id}` }, rec.title),
      h('div', { class: 'muted rec-card-meta' },
        rec.date || '', rec.date ? ' · ' : '', fmtDur(rec.duration || 0), rec.batch ? ` · ${rec.batch}` : ''),
      h('div', { class: 'row rec-card-status' },
        statusPill(rec.status),
        label ? h('span', { class: 'muted rec-agent' }, label) : null),
      h('div', { class: 'row rec-card-chips' }, proposalChips(rec.proposals)),
      h('div', { class: 'row rec-card-actions' },
        h('a', { class: 'btn btn-primary', href: `#/ideas/${rec.id}` }, 'Watch ideas'),
        h('a', { class: 'btn btn-ghost', href: `#/rec/${rec.id}` }, 'Adjust cut / transcript'),
        h('button', { class: 'btn btn-ghost', onclick: () => findClips(rec) }, 'Find clips')),
      rec.updated ? h('div', { class: 'muted rec-card-updated' }, relTime(rec.updated)) : null));
}

function emptyState() {
  return h('div', { class: 'panel rec-empty' },
    h('h3', {}, 'No recordings yet'),
    h('p', { class: 'muted' }, 'Add a full class recording from the CLI, then ask Claude to find clips:'),
    h('pre', { class: 'rec-code' },
      'python3 studio/studio.py add-recording --title … --file … --transcript …'));
}

let lastSig = null;
let lastRender = 0;

function render(state) {
  if (!root) return;
  lastRender = Date.now();
  const recordings = (state && state.recordings) || [];
  root.innerHTML = '';
  root.append(
    h('div', { class: 'rec-list-header' },
      h('h1', {}, 'Ideas'),
      h('p', { class: 'muted' },
        'Full class recordings → clip ideas → production. Claude proposes short clip ideas from each '
        + 'recording; pick the ones worth making here.')),
    recordings.length
      ? h('div', { class: 'rec-grid' }, recordings.map(card))
      : emptyState());
}

const view = {
  mount(el) {
    root = el;
    root.classList.add('rec-view', 'rec-recordings-view');
    render(getState());
  },
  unmount() {
    root = null;
  },
  onState(state) {
    const sig = JSON.stringify(state && state.recordings);
    if (sig === lastSig && Date.now() - lastRender < 60000) return; // unchanged: keep DOM (and clicks) intact
    lastSig = sig;
    render(state);
  },
};

registerView('recordings', view);
