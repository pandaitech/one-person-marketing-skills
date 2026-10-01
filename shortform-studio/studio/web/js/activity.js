// activity.js — the /api/events feed, optionally filtered by clip.

import { registerView } from './app.js';
import { get } from './api.js';
import { h, relTime } from './util.js';

let root = null;
let events = [];
let clipFilter = '';
let loading = false;

const ICONS = {
  comment: '💬', send: '📤', claim: '🛠', version: '🎬',
  approve: '✅', unapprove: '↩', publish: '📣', archive: '🗄',
  resolve: '✔', reopen: '↺', wontfix: '🚫', error: '⚠',
  taste: '📓', dispatch: '⚡', reply: '💬',
};

function iconFor(type) {
  return ICONS[type] || '•';
}

async function load() {
  loading = true;
  render();
  try {
    const qs = new URLSearchParams({ limit: '200' });
    if (clipFilter) qs.set('clip', clipFilter);
    const data = await get(`/api/events?${qs.toString()}`);
    events = data.events || [];
  } catch (e) {
    events = [];
  }
  loading = false;
  render();
}

function row(ev) {
  return h('div', { class: 'activity-row' },
    h('span', { class: 'activity-icon' }, iconFor(ev.type)),
    h('div', { class: 'activity-body' },
      h('div', { class: 'activity-text' },
        h('strong', {}, ev.actor || 'system'), ' ', ev.text || ev.type,
        ev.clip ? h('a', { class: 'activity-clip chip', href: `#/clip/${ev.clip}` }, ev.clip) : null),
      h('div', { class: 'activity-time muted small' }, relTime(ev.ts))));
}

function render() {
  if (!root) return;
  root.innerHTML = '';
  const filterInput = h('input', {
    class: 'input', placeholder: 'Filter by clip id…', value: clipFilter,
    oninput: (e) => { clipFilter = e.target.value; load(); },
  });
  root.append(
    h('div', { class: 'activity-toolbar' }, filterInput),
    loading
      ? h('div', { class: 'empty-state' }, 'Loading…')
      : events.length
        ? h('div', { class: 'activity-feed' }, events.map(row))
        : h('div', { class: 'empty-state' }, 'No activity yet.'));
}

registerView('activity', {
  mount(el) {
    root = el;
    root.className = 'view-activity';
    load();
  },
  unmount() {
    root = null;
  },
  onState() {},
});
