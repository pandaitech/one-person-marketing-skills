// util.js — DOM builder + small formatting/UI helpers shared by every view.
// Zero dependencies, plain ES module.

/**
 * DOM builder.
 * h(tag, attrs, ...children)
 * attrs: class, style (string|object), on<Event> handlers, dataset object,
 *        boolean props (set/unset via setAttribute), everything else via setAttribute.
 * children: Node | string | number | null | false | arrays (flattened, recursively).
 */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  attrs = attrs || {};
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === 'class') {
      el.className = value;
    } else if (key === 'style') {
      if (typeof value === 'string') el.style.cssText = value;
      else Object.assign(el.style, value);
    } else if (key === 'dataset') {
      Object.assign(el.dataset, value);
    } else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (typeof value === 'boolean') {
      if (value) el.setAttribute(key, '');
    } else {
      el.setAttribute(key, value);
    }
  }
  const append = (child) => {
    if (child == null || child === false) return;
    if (Array.isArray(child)) {
      child.forEach(append);
      return;
    }
    if (child instanceof Node) el.appendChild(child);
    else el.appendChild(document.createTextNode(String(child)));
  };
  children.forEach(append);
  return el;
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

/** m:ss.s (h:mm:ss.s when >= 1h) */
export function fmtTime(sec) {
  if (sec == null || Number.isNaN(sec)) sec = 0;
  sec = Math.max(0, sec);
  const h3 = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const sStr = s.toFixed(1).padStart(4, '0');
  if (h3 > 0) return `${h3}:${pad2(m)}:${sStr}`;
  return `${m}:${sStr}`;
}

/** m:ss (h:mm:ss when >= 1h) */
export function fmtDur(sec) {
  if (sec == null || Number.isNaN(sec)) sec = 0;
  sec = Math.round(Math.max(0, sec));
  const h3 = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h3 > 0) return `${h3}:${pad2(m)}:${pad2(s)}`;
  return `${m}:${pad2(s)}`;
}

/** Accepts "ss", "m:ss(.s)", "h:mm:ss(.s)" -> seconds (number) */
export function parseTime(str) {
  if (typeof str === 'number') return str;
  str = String(str ?? '').trim();
  if (!str) return 0;
  const parts = str.split(':').map((p) => parseFloat(p));
  if (parts.some((p) => Number.isNaN(p))) return 0;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0];
}

/** ISO timestamp -> "3m ago" / "in 3m" / "just now" */
export function relTime(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  let diff = Math.round((Date.now() - then) / 1000);
  const future = diff < 0;
  diff = Math.abs(diff);
  let out;
  if (diff < 5) return 'just now';
  else if (diff < 60) out = `${diff}s`;
  else if (diff < 3600) out = `${Math.floor(diff / 60)}m`;
  else if (diff < 86400) out = `${Math.floor(diff / 3600)}h`;
  else if (diff < 86400 * 30) out = `${Math.floor(diff / 86400)}d`;
  else out = new Date(then).toLocaleDateString();
  return future ? `in ${out}` : `${out} ago`;
}

export function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function inlineMd(s) {
  return s
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

/** Escape then: paragraphs, "- " bullets, **bold**, `code`. Returns safe HTML string. */
export function md(text) {
  if (!text) return '';
  const escaped = escapeHtml(text);
  const lines = escaped.split(/\r?\n/);
  const blocks = [];
  let para = [];
  let list = [];
  const flushPara = () => {
    if (para.length) {
      blocks.push(`<p>${para.join(' ')}</p>`);
      para = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      blocks.push(`<ul>${list.map((i) => `<li>${i}</li>`).join('')}</ul>`);
      list = [];
    }
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushPara();
      flushList();
      continue;
    }
    if (line.startsWith('- ')) {
      flushPara();
      list.push(inlineMd(line.slice(2)));
      continue;
    }
    flushList();
    para.push(inlineMd(line));
  }
  flushPara();
  flushList();
  return blocks.join('');
}

const STATUS_LABELS = {
  drafting: 'Drafting', queued: 'Queued', working: 'Working', review: 'Review',
  approved: 'Approved', published: 'Published', archived: 'Archived', error: 'Error',
  idle: 'Idle', draft: 'Draft', sent: 'Sent', addressed: 'Addressed',
  resolved: 'Resolved', wontfix: "Won't fix", proposed: 'Proposed', rejected: 'Rejected',
  needs_changes: 'Needs changes', active: 'Active', retired: 'Retired', new: 'New', done: 'Done',
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || (status ? status[0].toUpperCase() + status.slice(1) : '');
}

export function statusPill(status) {
  const span = document.createElement('span');
  span.className = `pill pill-${status}`;
  span.textContent = statusLabel(status);
  return span;
}

let toastRoot = null;
export function toast(msg, kind = 'ok') {
  if (!toastRoot) {
    toastRoot = document.getElementById('toast-root');
    if (!toastRoot) {
      toastRoot = document.createElement('div');
      toastRoot.id = 'toast-root';
      document.body.appendChild(toastRoot);
    }
  }
  const el = document.createElement('div');
  el.className = `toast toast-${kind}`;
  el.textContent = msg;
  toastRoot.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 250);
  }, 3000);
}

export async function copy(text) {
  try {
    await navigator.clipboard.writeText(String(text ?? ''));
    toast('Copied', 'ok');
  } catch (e) {
    toast('Copy failed', 'err');
  }
}

export function debounce(fn, ms = 200) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
