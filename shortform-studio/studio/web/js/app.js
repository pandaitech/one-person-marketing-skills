// app.js — router, top bar, /api/state polling. Loaded as the single <script type="module"> in index.html.

import { get } from './api.js';
import { h, toast } from './util.js';

// View modules call registerView()/getState()/navigate()/refresh() from this module at their
// own top level. If they were statically imported above, they would be evaluated (and would
// call registerView) *before* this module's own body below (e.g. `const views = {}`) has run —
// ES modules always finish evaluating static imports before the importer's own statements.
// So every view — including our own — is loaded dynamically, from boot(), after `views` exists.

const views = {};
let currentView = null;
let currentViewName = null;
let state = null;
let pollTimer = null;
let helpVisible = false;

// v2 shell: Home · Ideas (was Recordings) · Clips (was Board, now #/clips) · Taste · ⚙ Settings.
// Review and Activity keep working as routes, but only Settings gets an icon-only nav slot —
// Review is reached through a clip, Activity through Home's "Recent activity" link.
const NAV_ITEMS = [
  { name: 'home', label: 'Home', hash: '#/' },
  {
    name: 'recordings', altNames: ['ideas'], label: 'Ideas', hash: (s) => ideasHash(s),
    badge: (s) => s?.counts?.proposals,
  },
  { name: 'board', label: 'Clips', hash: '#/clips', badge: (s) => s?.counts?.review },
  { name: 'taste', label: 'Taste', hash: '#/taste' },
];

/** Where the "Ideas" nav item / Home's "Pick clip ideas" button should go: straight
 * into the watch-and-decide feed when there's exactly one recording, otherwise the
 * recordings list (so the director picks which recording to triage first). */
export function ideasHash(state) {
  const recordings = (state && state.recordings) || [];
  if (recordings.length === 1) return `#/ideas/${recordings[0].id}`;
  return '#/recordings';
}

/** view = {mount(el, params, query), unmount(), onState(state)} */
export function registerView(name, view) {
  views[name] = view;
}

export function getState() {
  return state;
}

export function navigate(hash) {
  if (!hash.startsWith('#')) hash = `#${hash}`;
  if (location.hash === hash) {
    route();
  } else {
    location.hash = hash;
  }
}

function parseRoute() {
  const raw = location.hash || '#/';
  const hash = raw.slice(1);
  const [pathPart, queryStr] = hash.split('?');
  const query = new URLSearchParams(queryStr || '');
  const segs = pathPart.split('/').filter(Boolean);
  if (segs.length === 0) return { name: 'home', params: {}, query };
  if (segs[0] === 'clips') return { name: 'board', params: {}, query };
  if (segs[0] === 'review') return { name: 'review', params: {}, query };
  if (segs[0] === 'clip' && segs[1]) return { name: 'review', params: { id: decodeURIComponent(segs[1]) }, query };
  if (segs[0] === 'edit' && segs[1]) return { name: 'edit', params: { id: decodeURIComponent(segs[1]) }, query };
  if (segs[0] === 'recordings') return { name: 'recordings', params: {}, query };
  if (segs[0] === 'rec' && segs[1]) return { name: 'recording', params: { id: decodeURIComponent(segs[1]) }, query };
  if (segs[0] === 'ideas' && segs[1]) return { name: 'ideas', params: { id: decodeURIComponent(segs[1]) }, query };
  if (segs[0] === 'ideas') return { name: 'recordings', params: {}, query };
  if (segs[0] === 'taste') return { name: 'taste', params: {}, query };
  if (segs[0] === 'activity') return { name: 'activity', params: {}, query };
  if (segs[0] === 'settings') return { name: 'settings', params: {}, query };
  return { name: 'home', params: {}, query };
}

function route() {
  const { name, params, query } = parseRoute();
  const viewEl = document.getElementById('view');
  if (currentView && typeof currentView.unmount === 'function') {
    try {
      currentView.unmount();
    } catch (e) {
      console.error(e);
    }
  }
  viewEl.innerHTML = '';
  currentViewName = name;
  const view = views[name];
  if (!view) {
    viewEl.appendChild(h('div', { class: 'empty-state' }, `"${name}" isn't available yet.`));
    currentView = null;
    renderTopbar();
    return;
  }
  currentView = view;
  try {
    view.mount(viewEl, params, query);
  } catch (e) {
    console.error(e);
    toast(`Failed to load view: ${e.message}`, 'err');
  }
  if (state && typeof view.onState === 'function') {
    try {
      view.onState(state);
    } catch (e) {
      console.error(e);
    }
  }
  renderTopbar();
}

function editorStatusNode() {
  const name = state?.settings?.editor_name || 'Editor';
  const working = state?.counts?.working || 0;
  const queued = state?.counts?.queued || 0;
  const rendering = state?.counts?.rendering || 0;
  const dotClass = `status-dot${working > 0 || rendering > 0 ? ' pulse' : ''}`;
  let text;
  if (!working && !queued) text = `${name} · idle`;
  else {
    const parts = [];
    if (working) parts.push(`${working} editing`);
    if (queued) parts.push(`${queued} queued`);
    text = `${name} · ${parts.join(' · ')}`;
  }
  return h('div', { class: 'editor-status' },
    h('span', { class: dotClass }),
    h('span', {}, text),
    rendering ? h('span', { class: 'badge badge-rendering' }, `Rendering ${rendering}`) : null);
}

function renderTopbar() {
  const bar = document.getElementById('topbar');
  bar.innerHTML = '';
  const brand = h('a', { class: 'brand', href: '#/' },
    h('span', { class: 'logo' }),
    h('span', { class: 'wordmark' }, 'Shortform Studio'));

  const nav = h('nav', { class: 'nav' }, NAV_ITEMS.map((item) => {
    const active = item.name === currentViewName || (item.altNames || []).includes(currentViewName);
    const count = item.badge ? item.badge(state) : null;
    const href = typeof item.hash === 'function' ? item.hash(state) : item.hash;
    return h('a', {
      href,
      class: `nav-item${active ? ' active' : ''}`,
    }, item.label, count ? h('span', { class: 'badge' }, String(count)) : null);
  }));

  const settingsActive = currentViewName === 'settings';
  const settingsBtn = h('a', {
    href: '#/settings',
    class: `nav-item nav-icon${settingsActive ? ' active' : ''}`,
    title: 'Settings',
    'aria-label': 'Settings',
  }, '⚙');

  bar.append(brand, nav, editorStatusNode(), settingsBtn);
}

async function poll() {
  try {
    state = await get('/api/state');
    renderTopbar();
    if (currentView && typeof currentView.onState === 'function') {
      currentView.onState(state);
    }
  } catch (e) {
    console.error('poll failed', e);
  }
}

export async function refresh() {
  await poll();
}

function isTyping(e) {
  const t = e.target;
  return !!(t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable));
}

const HELP_KEYS = [
  ['g h', 'Go to Home'], ['g r', 'Go to Ideas'], ['g b', 'Go to Clips'], ['?', 'Toggle this help'],
];

function renderHelp() {
  const overlayRoot = document.getElementById('overlay-root');
  if (!overlayRoot) return;
  overlayRoot.innerHTML = '';
  if (!helpVisible) return;
  overlayRoot.appendChild(h('div', { class: 'overlay-backdrop', onclick: () => { helpVisible = false; renderHelp(); } },
    h('div', { class: 'help-card', onclick: (e) => e.stopPropagation() },
      h('h3', {}, 'Keyboard shortcuts'),
      h('div', { class: 'help-grid' }, HELP_KEYS.flatMap(([k, d]) => [h('span', { class: 'kbd' }, k), h('span', {}, d)])),
      h('div', { class: 'muted small' }, 'Review has its own shortcuts — open a clip and press ? there.'))));
}

let lastKey = null;
let lastKeyTime = 0;
document.addEventListener('keydown', (e) => {
  if (isTyping(e) && e.key !== 'Escape') return;
  if (e.key === '?') {
    helpVisible = !helpVisible;
    renderHelp();
    return;
  }
  if (e.key === 'Escape' && helpVisible) {
    helpVisible = false;
    renderHelp();
    return;
  }
  const now = Date.now();
  if (lastKey === 'g' && now - lastKeyTime < 600) {
    if (e.key === 'r') navigate(ideasHash(state));
    else if (e.key === 'b') navigate('#/clips');
    else if (e.key === 'h') navigate('#/');
    lastKey = null;
    return;
  }
  lastKey = e.key;
  lastKeyTime = now;
});

async function boot() {
  await Promise.allSettled([
    import('./home.js'),
    import('./board.js'),
    import('./review.js'),
    import('./edit.js'),
    import('./taste.js'),
    import('./activity.js'),
    import('./settings.js'),
    import('./recordings.js'),
    import('./recording.js'),
    import('./ideas.js'),
  ]);
  window.addEventListener('hashchange', route);
  await poll();
  route();
  pollTimer = setInterval(poll, 3000);
}

window.addEventListener('beforeunload', () => {
  if (pollTimer) clearInterval(pollTimer);
});

boot();
