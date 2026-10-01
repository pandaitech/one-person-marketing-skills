// taste.js — the taste book: active rules, editor-proposed rules, add / retire.

import { registerView, getState, refresh } from './app.js';
import { post, patch } from './api.js';
import { h, md, toast } from './util.js';

let root = null;

function ruleRow(rule, kind) {
  const main = [];
  if (rule._editing) {
    const ta = h('textarea', { class: 'textarea' }, rule.text);
    main.push(h('div', { class: 'rule-edit stack' },
      ta,
      h('div', { class: 'row' },
        h('button', {
          class: 'btn btn-primary btn-sm',
          onclick: async () => {
            try {
              await patch(`/api/taste/${rule.id}`, { text: ta.value });
              rule._editing = false;
              toast('Rule updated');
              await refresh();
              render();
            } catch (e) {
              toast(e.message, 'err');
            }
          },
        }, 'Save'),
        h('button', { class: 'btn btn-ghost btn-sm', onclick: () => { rule._editing = false; render(); } }, 'Cancel'))));
  } else {
    const textEl = h('div', { class: 'rule-text' });
    textEl.innerHTML = md(rule.text);
    main.push(textEl);
  }
  if (rule.source) {
    main.push(h('a', { class: 'rule-source muted small', href: `#/clip/${rule.source.clip}` },
      `from ${rule.source.clip}${rule.source.comment ? ` · ${rule.source.comment}` : ''}`));
  }

  const actions = [];
  if (kind === 'active' && !rule._editing) {
    actions.push(h('button', { class: 'btn-icon', 'aria-label': 'Edit rule', onclick: () => { rule._editing = true; render(); } }, '✎'));
    actions.push(h('button', {
      class: 'btn-icon', 'aria-label': 'Retire rule',
      onclick: async () => {
        try {
          await patch(`/api/taste/${rule.id}`, { status: 'retired' });
          toast('Rule retired');
          await refresh();
        } catch (e) {
          toast(e.message, 'err');
        }
      },
    }, '✕'));
  } else if (kind === 'proposed') {
    actions.push(h('button', {
      class: 'btn btn-primary btn-sm',
      onclick: async () => {
        try {
          await patch(`/api/taste/${rule.id}`, { status: 'active' });
          toast('Rule accepted');
          await refresh();
        } catch (e) {
          toast(e.message, 'err');
        }
      },
    }, 'Accept'));
    actions.push(h('button', {
      class: 'btn btn-ghost btn-sm',
      onclick: async () => {
        try {
          await patch(`/api/taste/${rule.id}`, { status: 'retired' });
          toast('Rule rejected');
          await refresh();
        } catch (e) {
          toast(e.message, 'err');
        }
      },
    }, 'Reject'));
  } else if (kind === 'retired') {
    actions.push(h('button', {
      class: 'btn-icon', 'aria-label': 'Reactivate rule',
      onclick: async () => {
        try {
          await patch(`/api/taste/${rule.id}`, { status: 'active' });
          toast('Rule reactivated');
          await refresh();
        } catch (e) {
          toast(e.message, 'err');
        }
      },
    }, '↺'));
  }

  return h('div', { class: 'rule-row' },
    h('div', { class: 'rule-main' }, main),
    h('div', { class: 'rule-actions' }, actions));
}

function section(title, rules, kind, collapsed = false) {
  return h('details', { class: 'taste-section', open: !collapsed },
    h('summary', {}, `${title} (${rules.length})`),
    h('div', { class: 'taste-list' },
      rules.length ? rules.map((r) => ruleRow(r, kind)) : h('div', { class: 'empty-state small' }, 'None yet')));
}

function render() {
  if (!root) return;
  const state = getState();
  const rules = state?.taste?.rules || [];
  const active = rules.filter((r) => r.status === 'active');
  const proposed = rules.filter((r) => r.status === 'proposed');
  const retired = rules.filter((r) => r.status === 'retired');

  let addInput;
  root.innerHTML = '';
  root.append(...[
    h('div', { class: 'taste-intro' }, 'Your taste, applied to every edit.'),
    proposed.length ? section('Proposed by the editor', proposed, 'proposed') : null,
    section('Active rules', active, 'active'),
    h('form', {
      class: 'taste-add row',
      onsubmit: async (e) => {
        e.preventDefault();
        const text = addInput.value.trim();
        if (!text) return;
        try {
          await post('/api/taste', { text, author: 'director' });
          addInput.value = '';
          toast('Rule added');
          await refresh();
        } catch (err) {
          toast(err.message, 'err');
        }
      },
    },
    addInput = h('input', { class: 'input', placeholder: 'Add a taste rule…' }),
    h('button', { class: 'btn btn-primary', type: 'submit' }, 'Add')),
    section('Retired', retired, 'retired', true),
  ].filter(Boolean));
}

registerView('taste', {
  mount(el) {
    root = el;
    root.className = 'view-taste';
    render();
  },
  unmount() {
    root = null;
  },
  onState() {
    const sig = JSON.stringify((getState() || {}).taste);
    if (sig === lastTasteSig) return; // unchanged: keep the DOM so clicks aren't lost mid-poll
    // Don't clobber an in-progress edit / the add-rule input on a background poll.
    const active = document.activeElement;
    if (root && active && root.contains(active) && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
    lastTasteSig = sig;
    render();
  },
});
let lastTasteSig = null;
