// home.js — the front door (#/). Explains the loop in one sentence, shows the 3-step pipeline as
// big cards with live counts, then "What needs you" and "Recent activity". Every empty state here
// should teach the next step, not just say "nothing here".

import {
  registerView, navigate, getState, ideasHash,
} from './app.js';
import { get } from './api.js';
import { h, relTime } from './util.js';

let root = null;
let events = [];
let eventsLoaded = false;

async function loadEvents() {
  try {
    const data = await get('/api/events?limit=12');
    events = data.events || [];
  } catch (e) {
    events = [];
  }
  eventsLoaded = true;
  render();
}

// ---- step strip -------------------------------------------------------------

function stepCard({
  n, title, detail, cta, onClick, primary = true,
}) {
  return h('div', { class: 'home-step' },
    h('div', { class: 'home-step-num' }, `①②③④⑤⑥⑦`[n - 1] || String(n)),
    h('div', { class: 'home-step-body' },
      h('div', { class: 'home-step-title' }, title),
      h('div', { class: 'home-step-detail muted' }, detail),
      h('button', { class: `btn ${primary ? 'btn-primary' : ''}`, onclick: onClick }, cta)));
}

function arrow() {
  return h('div', { class: 'home-step-arrow' }, '→');
}

function stepStrip(state) {
  const counts = state?.counts || {};
  const ideasWaiting = counts.proposals || 0;
  const needsYou = counts.review || 0;
  const withClaude = counts.working || 0;
  const rendering = counts.rendering || 0;
  const approved = counts.approved || 0;
  const published = counts.published || 0;

  const step1 = stepCard({
    n: 1,
    title: 'Pick clip ideas',
    detail: ideasWaiting ? `${ideasWaiting} idea${ideasWaiting === 1 ? '' : 's'} waiting` : 'No ideas waiting right now',
    cta: 'Open ideas',
    onClick: () => navigate(ideasHash(state)),
  });

  const reviewParts = [];
  if (needsYou) reviewParts.push(`${needsYou} need${needsYou === 1 ? 's' : ''} you`);
  if (withClaude) reviewParts.push(`${withClaude} with Claude`);
  if (rendering) reviewParts.push(`${rendering} rendering`);
  const step2 = stepCard({
    n: 2,
    title: 'Review & edit',
    detail: reviewParts.length ? reviewParts.join(' · ') : 'Nothing waiting on a decision',
    cta: needsYou ? `Review ${needsYou}` : 'Open clips',
    onClick: () => navigate(needsYou ? '#/review' : '#/clips'),
  });

  const step3 = stepCard({
    n: 3,
    title: 'Approve & publish',
    detail: `${approved} approved · ${published} published`,
    cta: 'Open clips',
    onClick: () => navigate('#/clips'),
    primary: false,
  });

  return h('div', { class: 'home-strip' }, step1, arrow(), step2, arrow(), step3);
}

// ---- what needs you ----------------------------------------------------------

function needsYouReasons(state) {
  const items = [];
  const clips = state?.clips || [];
  const recordings = state?.recordings || [];

  for (const c of clips) {
    if (c.agent?.state === 'error') {
      items.push({
        key: `err-${c.id}`, kind: 'error', href: `#/clip/${c.id}`, poster: c.poster_url,
        title: c.title, reason: c.agent.message ? `Error — ${c.agent.message}` : 'Error — Claude ran into a problem',
      });
      continue;
    }
    const needsReview = c.status === 'review' || (c.open && c.open.draft > 0);
    if (!needsReview) continue;
    let reason;
    if (c.new_version && c.open?.addressed) {
      reason = `v${c.latest_version} ready — ${c.open.addressed} note${c.open.addressed > 1 ? 's' : ''} to confirm`;
    } else if (c.new_version) {
      reason = `v${c.latest_version} ready to watch`;
    } else if (c.open?.draft) {
      reason = `${c.open.draft} draft note${c.open.draft > 1 ? 's' : ''} not sent yet`;
    } else {
      reason = 'Waiting for your review';
    }
    items.push({
      key: `clip-${c.id}`, kind: 'clip', href: `#/clip/${c.id}`, poster: c.poster_url, title: c.title, reason,
    });
  }

  for (const r of recordings) {
    const waiting = r.proposals?.proposed || 0;
    if (!waiting) continue;
    items.push({
      key: `rec-${r.id}`,
      kind: 'idea',
      href: `#/rec/${r.id}`,
      poster: r.poster_url,
      title: r.title,
      reason: `${waiting} idea${waiting > 1 ? 's' : ''} waiting for your call`,
    });
  }

  // Errors first, then clip reviews, then ideas — most urgent at the top.
  const rank = { error: 0, clip: 1, idea: 2 };
  items.sort((a, b) => rank[a.kind] - rank[b.kind]);
  return items;
}

function needsYouRow(item) {
  return h('a', { class: `needs-row needs-${item.kind}`, href: item.href },
    h('div', { class: 'needs-thumb' },
      item.poster ? h('img', { src: item.poster, loading: 'lazy', alt: '' }) : h('div', { class: 'needs-thumb-empty' })),
    h('div', { class: 'needs-body' },
      h('div', { class: 'needs-title' }, item.title),
      h('div', { class: `needs-reason ${item.kind === 'error' ? 'needs-reason-error' : 'muted'}` }, item.reason)));
}

function needsYouSection(state) {
  const items = needsYouReasons(state);
  return h('div', { class: 'home-section' },
    h('div', { class: 'home-section-head' }, h('h3', {}, 'What needs you')),
    items.length
      ? h('div', { class: 'needs-list' }, items.map(needsYouRow))
      : h('div', { class: 'empty-state small' }, 'Nothing needs you right now — pick a new idea, or check back later.'));
}

// ---- recent activity ----------------------------------------------------------

const ICONS = {
  comment: '💬', send: '📤', claim: '🛠', version: '🎬',
  approve: '✅', unapprove: '↩', publish: '📣', archive: '🗄',
  resolve: '✔', reopen: '↺', wontfix: '🚫', error: '⚠',
  taste: '📓', dispatch: '⚡', reply: '💬',
};

function activityRow(ev) {
  return h('div', { class: 'activity-row' },
    h('span', { class: 'activity-icon' }, ICONS[ev.type] || '•'),
    h('div', { class: 'activity-body' },
      h('div', { class: 'activity-text' },
        h('strong', {}, ev.actor || 'system'), ' ', ev.text || ev.type,
        ev.clip ? h('a', { class: 'activity-clip chip', href: `#/clip/${ev.clip}` }, ev.clip) : null),
      h('div', { class: 'activity-time muted small' }, relTime(ev.ts))));
}

function activitySection() {
  return h('div', { class: 'home-section' },
    h('div', { class: 'home-section-head' }, h('h3', {}, 'Recent activity'),
      h('a', { class: 'btn-link', href: '#/activity' }, 'View all')),
    !eventsLoaded
      ? h('div', { class: 'empty-state small' }, 'Loading…')
      : events.length
        ? h('div', { class: 'activity-feed' }, events.map(activityRow))
        : h('div', { class: 'empty-state small' }, 'Nothing has happened yet.'));
}

// ---- render -------------------------------------------------------------------

function render() {
  if (!root) return;
  const state = getState();
  root.innerHTML = '';

  const clips = state?.clips || [];
  const recordings = state?.recordings || [];

  root.append(
    h('div', { class: 'home-intro' }, 'Claude edits, you decide. Pick ideas, review versions, approve.'),
    stepStrip(state));

  if (!clips.length && !recordings.length) {
    root.append(h('div', { class: 'empty-state large' },
      h('div', { class: 'empty-icon' }, '🎬'),
      h('div', {}, 'Nothing here yet.'),
      h('div', { class: 'muted' }, 'Add a full class recording from the CLI, then ask Claude to find clips in it.'),
      h('pre', { class: 'rec-code' }, 'python3 studio/studio.py add-recording --title … --file … --transcript …'),
      h('button', { class: 'btn btn-primary', onclick: () => navigate('#/recordings') }, 'Open Ideas')));
    return;
  }

  root.append(needsYouSection(state), activitySection());
}

registerView('home', {
  mount(el) {
    root = el;
    root.className = 'view-home';
    eventsLoaded = false;
    events = [];
    render();
    loadEvents();
  },
  unmount() {
    root = null;
  },
  onState() {
    render();
  },
});
