// edit-moments.js — Moments step: optional visual beats (images, year counter,
// manuscript page, zoom), described in plain words. Owns only its own DOM inside
// `container`. Every edit goes through ctx.update(mutator, label); this module
// never calls ctx.api.put directly. The one exception is image upload, which the
// backend contract requires as a raw POST of the file body (not JSON), so it uses
// fetch() directly against `/api/clips/<id>/assets`.

import { h, fmtTime, parseTime, toast } from './util.js';

const FRAME_OPTIONS = [
  { value: 'photo', text: 'Photo' },
  { value: 'cutout', text: 'Cut-out' },
  { value: 'book', text: 'Book' },
];

const CAM_OPTIONS = [
  { value: 'bottom-right', text: 'Bottom right' },
  { value: 'bottom-left', text: 'Bottom left' },
  { value: 'top-right', text: 'Top right' },
  { value: 'top-left', text: 'Top left' },
  { value: 'none', text: 'None' },
];

// The studio's class recordings are Zoom-style captures at 1280x720; that's
// the only sensible default for a brand-new screen moment's crop (like
// DEFAULT_SPEAKER_TILE in house_plan.py, which assumes the same source size).
// A class recorded at a different resolution needs its crop fields adjusted.
const DEFAULT_SCREEN_CROP = [0, 0, 1280, 720];

function kindMeta(sm) {
  if (sm.kind === 'fullscreen') return sm.counter ? { icon: '🔢', name: 'Year counter' } : { icon: '🖼', name: 'Full-screen images' };
  if (sm.kind === 'manuscript') return { icon: '📜', name: 'Old manuscript page' };
  if (sm.kind === 'zoom') return { icon: '🔍', name: 'Zoom-in on speaker' };
  if (sm.kind === 'screen') return { icon: '🖥', name: 'Screen share' };
  return { icon: '❓', name: sm.kind || 'Moment' };
}

function basename(p) {
  return String(p || '').split('/').pop();
}

export function mountMomentsStep(container, ctx0) {
  let ctx = ctx0;
  let expandedId = ctx0.selected && ctx0.selected.kind === 'moment' ? ctx0.selected.id : null;

  container.classList.add('ed-moments');
  update(ctx0);
  return { update, destroy };

  // ---- lifecycle ----------------------------------------------------------

  function update(newCtx) {
    ctx = newCtx;
    if (ctx.selected && ctx.selected.kind === 'moment') expandedId = ctx.selected.id;
    else if (!ctx.selected) expandedId = null;
    render();
  }

  function destroy() {
    container.innerHTML = '';
  }

  // ---- recipe helpers -------------------------------------------------------

  function updateMoment(id, mutator, label) {
    ctx.update((draft) => {
      const m = (draft.moments || []).find((x) => x.id === id);
      if (m) mutator(m);
    }, label);
  }

  function nextId() {
    const nums = (ctx.spec.moments || []).map((m) => {
      const mm = /^m(\d+)$/.exec(m.id || '');
      return mm ? parseInt(mm[1], 10) : 0;
    });
    const n = nums.length ? Math.max(...nums) + 1 : 1;
    return `m${n}`;
  }

  function collectClipImages() {
    const set = new Set();
    (ctx.spec.moments || []).forEach((m) => (m.items || []).forEach((it) => { if (it.image) set.add(it.image); }));
    return Array.from(set);
  }

  // ---- render ---------------------------------------------------------------

  function render() {
    container.innerHTML = '';
    const planMoments = ((ctx.plan && ctx.plan.moments) || []).slice().sort((a, b) => a.t0 - b.t0);
    const byId = new Map((ctx.spec.moments || []).map((m) => [m.id, m]));

    const list = h('div', { class: 'stack ed-moments-list' });
    if (!planMoments.length) {
      list.append(h('div', { class: 'empty-state' },
        'No moments yet. Add one below to bring in images, a year counter, an old page, or a zoom.'));
    }
    planMoments.forEach((pm) => {
      const sm = byId.get(pm.id);
      if (!sm) return;
      list.append(momentCard(sm, pm));
    });

    container.append(list, addMenu());
  }

  function momentCard(sm, pm) {
    const expanded = expandedId === sm.id;
    const meta = kindMeta(sm);
    const head = h('div', {
      class: 'ed-moment-head row',
      onclick: (e) => { if (e.target.closest('button')) return; selectCard(sm.id); },
    },
      h('span', { class: 'ed-moment-icon' }, meta.icon),
      h('div', { class: 'ed-moment-title-wrap' },
        h('div', { class: 'ed-moment-title' }, meta.name),
        h('div', { class: 'ed-moment-time muted small' }, `${fmtTime(pm.t0)} – ${fmtTime(pm.t1)}`),
        pm.summary ? h('div', { class: 'ed-moment-summary small muted' }, pm.summary) : null),
      h('div', { class: 'ed-moment-actions row' },
        h('button', { class: 'btn btn-sm', onclick: (e) => { e.stopPropagation(); ctx.seek(pm.t0); ctx.play(); } }, '▶ Preview'),
        h('button', {
          class: 'btn-icon', title: 'Delete moment',
          onclick: (e) => { e.stopPropagation(); deleteMoment(sm.id); },
        }, '✕')));
    const card = h('div', { class: `ed-moment-card panel${expanded ? ' ed-moment-expanded' : ''}` }, head);
    if (expanded) card.append(h('div', { class: 'ed-moment-body' }, buildEditor(sm)));
    return card;
  }

  function selectCard(id) {
    expandedId = id;
    ctx.select('moment', id);
    render();
  }

  function deleteMoment(id) {
    ctx.update((draft) => { draft.moments = (draft.moments || []).filter((m) => m.id !== id); }, 'Moments: deleted moment');
    if (expandedId === id) expandedId = null;
    toast('Moment deleted — ⌘Z to undo', 'ok');
  }

  function buildEditor(sm) {
    if (sm.kind === 'fullscreen') return fullscreenEditor(sm);
    if (sm.kind === 'manuscript') return manuscriptEditor(sm);
    if (sm.kind === 'zoom') return zoomEditor(sm);
    if (sm.kind === 'screen') return screenEditor(sm);
    return h('div', { class: 'muted' }, `Unknown moment kind: ${sm.kind}`);
  }

  // ---- field helpers ----------------------------------------------------------

  function timeField(labelText, id, readSrc, applyToM, label) {
    const current = readSrc();
    const input = h('input', { class: 'input ed-time-input', value: fmtTime(ctx.srcToOut(current)) });
    input.addEventListener('change', () => {
      const out = parseTime(input.value);
      updateMoment(id, (m) => applyToM(m, ctx.outToSrc(out)), label);
    });
    return h('div', { class: 'field ed-time-field' },
      h('label', {}, labelText),
      h('div', { class: 'row' },
        input,
        h('button', { class: 'btn-icon', title: 'Set to playhead', onclick: () => updateMoment(id, (m) => applyToM(m, ctx.outToSrc(ctx.time())), label) }, '⏱'),
        h('button', { class: 'btn-icon', title: '−0.1s', onclick: () => updateMoment(id, (m) => applyToM(m, current - 0.1), label) }, '−0.1'),
        h('button', { class: 'btn-icon', title: '+0.1s', onclick: () => updateMoment(id, (m) => applyToM(m, current + 0.1), label) }, '+0.1')));
  }

  function textField(labelText, id, readVal, applyToM, label, opts = {}) {
    const input = opts.textarea ? h('textarea', { class: 'textarea', rows: opts.rows || 2 }) : h('input', { class: 'input' });
    input.value = readVal() || '';
    input.addEventListener('change', () => updateMoment(id, (m) => applyToM(m, input.value), label));
    return h('div', { class: 'field' }, h('label', {}, labelText), input);
  }

  function numberField(labelText, id, readVal, applyToM, label, opts = {}) {
    const input = h('input', { class: 'input', type: 'number', value: readVal(), min: opts.min, max: opts.max, step: opts.step || 1 });
    input.addEventListener('change', () => updateMoment(id, (m) => applyToM(m, parseFloat(input.value) || 0), label));
    return h('div', { class: 'field' }, h('label', {}, labelText), input);
  }

  function sliderField(labelText, id, readVal, applyToM, label, { min, max, step }) {
    const val = readVal();
    const out = h('span', { class: 'muted small ed-slider-val' }, String(val));
    const input = h('input', {
      class: 'ed-slider', type: 'range', min, max, step, value: val,
      oninput: () => { out.textContent = input.value; },
    });
    input.addEventListener('change', () => updateMoment(id, (m) => applyToM(m, parseFloat(input.value)), label));
    return h('div', { class: 'field' }, h('label', {}, labelText), h('div', { class: 'row' }, input, out));
  }

  function selectField(labelText, id, readVal, applyToM, label, options) {
    const current = readVal();
    const select = h('select', { class: 'select' }, options.map((o) => h('option', { value: o.value, selected: o.value === current }, o.text)));
    select.addEventListener('change', () => updateMoment(id, (m) => applyToM(m, select.value), label));
    return h('div', { class: 'field' }, h('label', {}, labelText), select);
  }

  function rectPicker(spaceW, spaceH, x, y, onSet) {
    const dispW = 84;
    const dispH = Math.round((dispW * spaceH) / spaceW);
    const dot = h('div', {
      class: 'ed-pos-dot',
      style: `left:${Math.round((x / spaceW) * dispW)}px; top:${Math.round((y / spaceH) * dispH)}px;`,
    });
    const box = h('div', { class: 'ed-pos-picker', style: `width:${dispW}px; height:${dispH}px;` }, dot);
    box.addEventListener('click', (e) => {
      const rect = box.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / dispW) * spaceW;
      const py = ((e.clientY - rect.top) / dispH) * spaceH;
      onSet(Math.round(Math.max(0, Math.min(spaceW, px))), Math.round(Math.max(0, Math.min(spaceH, py))));
    });
    return box;
  }

  // ---- fullscreen editor -----------------------------------------------------

  function fullscreenEditor(sm) {
    const head = sm.head || { lines: [], until: sm.until };
    const wrap = h('div', { class: 'stack ed-moment-form' });

    wrap.append(
      h('div', { class: 'row' },
        timeField('Speaker hides at', sm.id, () => sm.slide, (m, v) => { m.slide = v; }, 'Moments: moved when speaker hides'),
        timeField('Speaker comes back at', sm.id, () => sm.until, (m, v) => { m.until = v; }, 'Moments: moved when speaker comes back')),
      h('div', { class: 'ed-subhead' }, 'Heading'),
      timeField('Heading stays until', sm.id, () => head.until, (m, v) => { m.head = m.head || { lines: [] }; m.head.until = v; }, 'Moments: moved heading end'));

    const linesWrap = h('div', { class: 'stack ed-lines' });
    (head.lines || []).forEach((line, li) => linesWrap.append(headLineRow(sm, li)));
    linesWrap.append(h('button', { class: 'btn btn-sm', onclick: () => addHeadLine(sm) }, '+ Add heading line'));
    wrap.append(linesWrap);

    wrap.append(h('div', { class: 'ed-subhead' }, 'Images'));
    const itemsWrap = h('div', { class: 'stack ed-items' });
    (sm.items || []).forEach((item, ii) => itemsWrap.append(itemRow(sm, ii)));
    itemsWrap.append(h('button', { class: 'btn btn-sm', onclick: () => addItem(sm) }, '+ Add image'));
    wrap.append(itemsWrap);

    wrap.append(h('div', { class: 'ed-subhead' }, 'Year counter'));
    if (sm.counter) {
      wrap.append(counterForm(sm),
        h('button', { class: 'btn btn-sm btn-ghost', onclick: () => updateMoment(sm.id, (m) => { delete m.counter; }, 'Moments: removed year counter') }, 'Remove year counter'));
    } else {
      wrap.append(h('button', { class: 'btn btn-sm', onclick: () => addCounter(sm) }, '+ Add year counter'));
    }
    return wrap;
  }

  function headLineRow(sm, li) {
    const line = sm.head.lines[li];
    const textInput = h('input', { class: 'input', value: line.text || '' });
    textInput.addEventListener('change', () => updateMoment(sm.id, (m) => { m.head.lines[li].text = textInput.value; }, 'Moments: edited heading line'));
    const words = (line.text || '').split(/\s+/).filter(Boolean);
    const chips = h('div', { class: 'row ed-word-chips' }, words.map((w) => h('button', {
      class: `chip${line.hl === w ? ' ed-chip-active' : ''}`, type: 'button',
      onclick: () => updateMoment(sm.id, (m) => { m.head.lines[li].hl = m.head.lines[li].hl === w ? null : w; }, 'Moments: changed heading highlight'),
    }, w)));
    return h('div', { class: 'ed-line-row panel' },
      h('div', { class: 'row' },
        h('div', { class: 'field' }, h('label', {}, 'Text'), textInput),
        h('button', { class: 'btn-icon', title: 'Remove line', onclick: () => updateMoment(sm.id, (m) => { m.head.lines.splice(li, 1); }, 'Moments: removed heading line') }, '✕')),
      words.length ? h('div', { class: 'field' }, h('label', {}, 'Tap a word to highlight it'), chips) : null,
      timeField('Appears at', sm.id, () => line.at, (m, v) => { m.head.lines[li].at = v; }, 'Moments: moved heading line'));
  }

  function addHeadLine(sm) {
    updateMoment(sm.id, (m) => {
      m.head = m.head || { lines: [] };
      m.head.lines.push({ text: '', at: ctx.outToSrc(ctx.time()), hl: null });
    }, 'Moments: added heading line');
  }

  function itemRow(sm, ii) {
    const item = sm.items[ii];
    const images = collectClipImages();
    const select = h('select', { class: 'select' },
      h('option', { value: '', selected: !item.image }, 'Choose image…'),
      images.map((p) => h('option', { value: p, selected: p === item.image }, basename(p))),
      h('option', { value: '__upload__' }, 'Upload new…'));
    const fileInput = h('input', { type: 'file', accept: 'image/*', class: 'hidden' });
    select.addEventListener('change', () => {
      if (select.value === '__upload__') { fileInput.click(); select.value = item.image || ''; return; }
      updateMoment(sm.id, (m) => { m.items[ii].image = select.value; }, 'Moments: changed image');
    });
    fileInput.addEventListener('change', async () => {
      const file = fileInput.files[0];
      if (!file) return;
      try {
        const res = await fetch(`/api/clips/${ctx.clip.id}/assets?name=${encodeURIComponent(file.name)}`, { method: 'POST', body: file });
        const data = await res.json().catch(() => null);
        if (!res.ok || !data || !data.path) throw new Error((data && data.error) || 'Upload failed');
        updateMoment(sm.id, (m) => { m.items[ii].image = data.path; }, 'Moments: uploaded image');
        toast('Image uploaded', 'ok');
      } catch (err) {
        toast(`Upload failed: ${err.message}`, 'err');
      }
    });

    return h('div', { class: 'ed-item-row panel' },
      h('div', { class: 'row' },
        h('div', { class: 'muted small' }, item.image ? basename(item.image) : 'No image chosen'),
        h('button', { class: 'btn-icon', title: 'Remove image', onclick: () => updateMoment(sm.id, (m) => { m.items.splice(ii, 1); }, 'Moments: removed image') }, '✕')),
      h('div', { class: 'field' }, h('label', {}, 'Image'), h('div', { class: 'row' }, select, fileInput)),
      h('div', { class: 'row' },
        selectField('Frame style', sm.id, () => item.frame || 'photo', (m, v) => { m.items[ii].frame = v; }, 'Moments: changed frame style', FRAME_OPTIONS),
        textField('Label (optional)', sm.id, () => item.label || '', (m, v) => { m.items[ii].label = v || null; }, 'Moments: edited image label')),
      timeField('Appears at', sm.id, () => item.at, (m, v) => { m.items[ii].at = v; }, 'Moments: moved image appearance'),
      h('div', { class: 'row' },
        numberField('X', sm.id, () => item.x, (m, v) => { m.items[ii].x = v; }, 'Moments: moved image', { min: 0, max: 1080 }),
        numberField('Y', sm.id, () => item.y, (m, v) => { m.items[ii].y = v; }, 'Moments: moved image', { min: 0, max: 1920 }),
        rectPicker(1080, 1920, item.x, item.y, (x, y) => updateMoment(sm.id, (m) => { m.items[ii].x = x; m.items[ii].y = y; }, 'Moments: moved image'))),
      h('div', { class: 'row' },
        sliderField('Scale', sm.id, () => item.scale || 1, (m, v) => { m.items[ii].scale = v; }, 'Moments: resized image', { min: 0.5, max: 2, step: 0.02 }),
        sliderField('Angle', sm.id, () => item.angle || 0, (m, v) => { m.items[ii].angle = v; }, 'Moments: rotated image', { min: -15, max: 15, step: 1 })));
  }

  function addItem(sm) {
    const t = ctx.outToSrc(ctx.time());
    updateMoment(sm.id, (m) => {
      m.items = m.items || [];
      m.items.push({ image: null, frame: 'photo', label: null, at: t, x: 540, y: 930, scale: 1, angle: 0 });
    }, 'Moments: added image');
  }

  function counterForm(sm) {
    const c = sm.counter;
    return h('div', { class: 'stack ed-counter-form panel' },
      h('div', { class: 'row' },
        textField('From year', sm.id, () => c.from, (m, v) => { m.counter.from = v; }, 'Moments: changed counter start year'),
        textField('To year', sm.id, () => c.to, (m, v) => { m.counter.to = v; }, 'Moments: changed counter end year')),
      h('div', { class: 'row' },
        timeField('Rolls at', sm.id, () => c.start, (m, v) => { m.counter.start = v; }, 'Moments: moved counter start'),
        timeField('Lands at', sm.id, () => c.land, (m, v) => { m.counter.land = v; }, 'Moments: moved counter landing')),
      numberField('Y position', sm.id, () => c.y, (m, v) => { m.counter.y = v; }, 'Moments: moved counter', { min: 0, max: 1920 }),
      c.shrink != null
        ? h('div', { class: 'row' },
          timeField('Shrinks to top at', sm.id, () => c.shrink, (m, v) => { m.counter.shrink = v; }, 'Moments: moved counter shrink'),
          h('button', {
            class: 'btn-icon', title: 'Remove shrink',
            onclick: () => updateMoment(sm.id, (m) => { delete m.counter.shrink; delete m.counter.shrink_to; delete m.counter.persist; }, 'Moments: removed counter shrink'),
          }, '✕'))
        : h('button', {
          class: 'btn btn-sm',
          onclick: () => updateMoment(sm.id, (m) => { m.counter.shrink = (m.counter.land || 0) + 0.5; m.counter.shrink_to = [250, 0.42]; }, 'Moments: added counter shrink'),
        }, '+ Shrink to top after landing'),
      c.shrink != null
        ? timeField('Stays pinned until', sm.id, () => c.persist || c.shrink, (m, v) => { m.counter.persist = v; }, 'Moments: moved counter persist')
        : null);
  }

  function addCounter(sm) {
    const t = ctx.outToSrc(ctx.time());
    updateMoment(sm.id, (m) => { m.counter = { from: '2026', to: '1923', start: t, land: t + 2, y: 960 }; }, 'Moments: added year counter');
  }

  // ---- manuscript editor -----------------------------------------------------

  function manuscriptEditor(sm) {
    return h('div', { class: 'stack ed-moment-form' },
      textField('Header text', sm.id, () => sm.header || '', (m, v) => { m.header = v; }, 'Moments: edited header'),
      textField('Main text', sm.id, () => sm.text || '', (m, v) => { m.text = v; }, 'Moments: edited text', { textarea: true, rows: 2 }),
      h('div', { class: 'row' },
        timeField('Appears at', sm.id, () => sm.at, (m, v) => { m.at = v; }, 'Moments: moved page appearance'),
        timeField('Ends at', sm.id, () => sm.until, (m, v) => { m.until = v; }, 'Moments: moved page end')),
      h('div', { class: 'row' },
        timeField('Typing starts', sm.id, () => sm.type_at, (m, v) => { m.type_at = v; }, 'Moments: moved typing start'),
        timeField('Typing ends', sm.id, () => sm.type_end, (m, v) => { m.type_end = v; }, 'Moments: moved typing end')),
      h('div', { class: 'row' },
        numberField('X', sm.id, () => sm.x, (m, v) => { m.x = v; }, 'Moments: moved page', { min: 0, max: 1080 }),
        numberField('Y', sm.id, () => sm.y, (m, v) => { m.y = v; }, 'Moments: moved page', { min: 0, max: 1920 }),
        sliderField('Angle', sm.id, () => sm.angle || 0, (m, v) => { m.angle = v; }, 'Moments: rotated page', { min: -15, max: 15, step: 1 })));
  }

  // ---- zoom editor ------------------------------------------------------------

  function zoomEditor(sm) {
    return h('div', { class: 'stack ed-moment-form' },
      h('div', { class: 'row' },
        timeField('Starts at', sm.id, () => sm.at, (m, v) => { m.at = v; }, 'Moments: moved zoom start'),
        timeField('Ends at', sm.id, () => sm.until, (m, v) => { m.until = v; }, 'Moments: moved zoom end')),
      sliderField('Zoom amount', sm.id, () => sm.zoom || 1.1, (m, v) => { m.zoom = v; }, 'Moments: changed zoom amount', { min: 1.05, max: 1.4, step: 0.01 }),
      h('div', { class: 'field' }, h('label', {}, 'Focus point (on the speaker frame)'),
        h('div', { class: 'row' },
          rectPicker(968, 542, sm.cx, sm.cy, (x, y) => updateMoment(sm.id, (m) => { m.cx = x; m.cy = y; }, 'Moments: moved zoom focus')),
          numberField('CX', sm.id, () => sm.cx, (m, v) => { m.cx = v; }, 'Moments: moved zoom focus', { min: 0, max: 968 }),
          numberField('CY', sm.id, () => sm.cy, (m, v) => { m.cy = v; }, 'Moments: moved zoom focus', { min: 0, max: 542 }))));
  }

  // ---- screen editor ------------------------------------------------------------

  function cropFieldsRow(sm, field, crop) {
    const labels = ['X', 'Y', 'W', 'H'];
    return h('div', { class: 'row' }, labels.map((lab, i) => numberField(
      lab, sm.id, () => crop[i],
      (m, v) => { m[field] = (m[field] || crop.slice()); m[field][i] = v; },
      `Moments: edited screen ${field === 'crop' ? 'crop' : 'push/pan target'}`,
      { min: 0 },
    )));
  }

  function screenEditor(sm) {
    const wrap = h('div', { class: 'stack ed-moment-form' },
      h('div', { class: 'row' },
        timeField('Starts at', sm.id, () => sm.at, (m, v) => { m.at = v; }, 'Moments: moved screen start'),
        timeField('Ends at', sm.id, () => sm.until, (m, v) => { m.until = v; }, 'Moments: moved screen end')),
      selectField('Corner cam', sm.id, () => sm.cam || 'bottom-right', (m, v) => { m.cam = v; }, 'Moments: changed corner cam position', CAM_OPTIONS));

    wrap.append(h('div', { class: 'ed-subhead' }, 'Crop (source pixels: x, y, w, h)'));
    if (sm.crop) {
      wrap.append(
        cropFieldsRow(sm, 'crop', sm.crop),
        h('button', { class: 'btn btn-sm btn-ghost', onclick: () => updateMoment(sm.id, (m) => { delete m.crop; }, 'Moments: reset screen crop to full frame') }, 'Use full source frame'));
    } else {
      wrap.append(
        h('div', { class: 'muted small' }, 'Using the full source frame.'),
        h('button', { class: 'btn btn-sm', onclick: () => updateMoment(sm.id, (m) => { m.crop = DEFAULT_SCREEN_CROP.slice(); }, 'Moments: set screen crop') }, '+ Set custom crop'));
    }

    wrap.append(h('div', { class: 'ed-subhead' }, 'Push / pan to'));
    if (sm.crop_to) {
      wrap.append(
        cropFieldsRow(sm, 'crop_to', sm.crop_to),
        h('button', { class: 'btn btn-sm btn-ghost', onclick: () => updateMoment(sm.id, (m) => { delete m.crop_to; }, 'Moments: removed screen push/pan') }, 'Remove push/pan'));
    } else {
      wrap.append(h('button', {
        class: 'btn btn-sm',
        onclick: () => updateMoment(sm.id, (m) => { m.crop_to = (m.crop || DEFAULT_SCREEN_CROP).slice(); }, 'Moments: added screen push/pan'),
      }, '+ Add push/pan (virtual camera)'));
    }
    return wrap;
  }

  // ---- add moment -------------------------------------------------------------

  function makeFullscreen(t, id) {
    return { id, kind: 'fullscreen', slide: t, until: t + 3, head: { lines: [], until: t + 3 }, items: [] };
  }
  function makeCounterFullscreen(t, id) {
    return {
      id, kind: 'fullscreen', slide: t, until: t + 3, head: { lines: [], until: t + 3 }, items: [],
      counter: { from: '2026', to: '1923', start: t + 0.5, land: t + 2, y: 960 },
    };
  }
  function makeManuscript(t, id) {
    return { id, kind: 'manuscript', at: t, until: t + 5, header: '', text: '…', type_at: t + 0.6, type_end: t + 1.8, x: 540, y: 470, angle: -2 };
  }
  function makeZoom(t, id) {
    return { id, kind: 'zoom', at: t, until: t + 1.5, zoom: 1.16, cx: 484, cy: 190 };
  }
  function makeScreen(t, id) {
    return { id, kind: 'screen', at: t, until: t + 5, cam: 'bottom-right' };
  }

  function addMenu() {
    const options = [
      { label: '🖼 Full-screen images', make: makeFullscreen },
      { label: '🔢 Year counter', make: makeCounterFullscreen },
      { label: '📜 Manuscript page', make: makeManuscript },
      { label: '🔍 Zoom-in', make: makeZoom },
      { label: '🖥 Screen share', make: makeScreen },
    ];
    return h('div', { class: 'ed-add-wrap' },
      h('div', { class: 'ed-subhead' }, '+ Add moment'),
      h('div', { class: 'row' }, options.map((opt) => h('button', { class: 'btn btn-sm', onclick: () => addMoment(opt.make) }, opt.label))));
  }

  function addMoment(makeFn) {
    const t = ctx.outToSrc(ctx.time());
    const id = nextId();
    const moment = makeFn(t, id);
    ctx.update((draft) => { draft.moments = draft.moments || []; draft.moments.push(moment); }, `Moments: added ${kindMeta(moment).name.toLowerCase()}`);
    expandedId = id;
    ctx.select('moment', id);
  }
}
