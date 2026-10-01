// settings.js — director/editor names, auto-dispatch, dispatch command, media roots.

import { registerView, getState, refresh } from './app.js';
import { patch } from './api.js';
import { h, toast } from './util.js';

let root = null;
let rendered = false;

function render() {
  if (!root) return;
  const state = getState();
  if (!state) return;
  rendered = true;
  const settings = state.settings || {};
  root.innerHTML = '';

  const save = async (body, okMsg) => {
    try {
      await patch('/api/settings', body);
      toast(okMsg || 'Saved');
      await refresh();
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  const directorInput = h('input', { class: 'input', value: settings.director_name || '' });
  directorInput.addEventListener('blur', () => save({ director_name: directorInput.value }));

  const editorInput = h('input', { class: 'input', value: settings.editor_name || '' });
  editorInput.addEventListener('blur', () => save({ editor_name: editorInput.value }));

  const autoToggle = h('input', { type: 'checkbox', checked: !!settings.auto_dispatch });
  autoToggle.addEventListener('change', () => save({ auto_dispatch: autoToggle.checked }));

  const theme = settings.theme || {};
  const themeField = (key, label, placeholder) => {
    const input = h('input', { class: 'input', value: theme[key] || '', placeholder });
    input.addEventListener('blur', () => save({ theme: { ...theme, [key]: input.value.trim() || undefined } }, 'Theme saved'));
    return h('div', { class: 'field' }, h('label', {}, label), input);
  };

  const templateInput = h('input', { class: 'input', value: settings.house_template || '' });
  templateInput.addEventListener('blur', () => save({ house_template: templateInput.value.trim() }, 'House template saved'));

  const cmdTextarea = h('textarea', { class: 'textarea code', rows: 5 }, JSON.stringify(settings.dispatch_command || [], null, 2));
  const rootsTextarea = h('textarea', { class: 'textarea', rows: 4 }, (settings.media_roots || []).join('\n'));

  const form = h('div', { class: 'settings-form stack' },
    h('div', { class: 'field' },
      h('label', {}, 'Director name'),
      directorInput),
    h('div', { class: 'field' },
      h('label', {}, 'Editor name'),
      editorInput),
    h('div', { class: 'field' },
      h('label', { class: 'checkbox' }, autoToggle, h('span', {}, 'Auto-dispatch')),
      h('div', { class: 'muted small' },
        'When on, "Send notes" and "Approve proposal" immediately start a headless AI editor run for that clip. '
        + 'When off, nothing happens until you tell the AI editor in chat to process the studio queue.')),
    h('h3', {}, 'Theme (house-style renderer)'),
    h('div', { class: 'muted small' },
      'Neutral by default. Set these to a brand\'s colours/font to restyle new renders; existing versions are unaffected.'),
    themeField('background', 'Background colour (hex)', '#F4F3EF'),
    themeField('text', 'Text colour (hex)', '#1C1C1C'),
    themeField('accent', 'Accent colour (hex)', '#3B6EA5'),
    themeField('accent2', 'Secondary accent colour (hex)', '#2B4C6F'),
    themeField('font', 'Font (Google Fonts family name)', 'Inter'),
    h('div', { class: 'field' },
      h('label', {}, 'House-style template (folder with render.py + assets/)'),
      templateInput,
      h('div', { class: 'muted small' },
        'A new clip\'s first cut starts from this approved project. Point it at a newer project when the style evolves.')),
    h('div', { class: 'field' },
      h('label', {}, 'Dispatch command (JSON array)'),
      cmdTextarea,
      h('div', { class: 'row' },
        h('button', {
          class: 'btn btn-primary btn-sm',
          onclick: () => {
            let parsed;
            try {
              parsed = JSON.parse(cmdTextarea.value);
            } catch (e) {
              toast(`Invalid JSON: ${e.message}`, 'err');
              return;
            }
            if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === 'string')) {
              toast('Dispatch command must be a JSON array of strings', 'err');
              return;
            }
            save({ dispatch_command: parsed }, 'Dispatch command saved');
          },
        }, 'Save command'))),
    h('div', { class: 'field' },
      h('label', {}, 'Media roots (one per line)'),
      rootsTextarea,
      h('div', { class: 'row' },
        h('button', {
          class: 'btn btn-primary btn-sm',
          onclick: () => {
            const roots = rootsTextarea.value.split('\n').map((s) => s.trim()).filter(Boolean);
            save({ media_roots: roots }, 'Media roots saved');
          },
        }, 'Save roots'))));

  root.append(h('h2', {}, 'Settings'), form);
}

registerView('settings', {
  mount(el) {
    root = el;
    root.className = 'view-settings';
    rendered = false;
    render();
  },
  unmount() {
    root = null;
  },
  onState() {
    if (!rendered) render();
  },
});
