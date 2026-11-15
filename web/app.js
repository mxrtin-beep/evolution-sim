'use strict';
const $ = s => document.querySelector(s);
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'html') e.innerHTML = v; else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(k));
  return e;
}
const api = async (path, body) => {
  const r = await fetch('/api/' + path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
};
const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };

let SCHEMA, cfg, map;                  // setup state
const T = { OPEN: 0, WALL: 1, HAZARD: 2, SAFE: 3 };
const TERRAIN_COLORS = ['#ffffff', '#111111', '#ffc4bf', '#bff0cf'];

/* ============================================================== setup UI */
async function init() {
  SCHEMA = await api('schema');
  const saved = store.get('evosim.cfg2', null);
  cfg = { mode: 'asexual', partners: 1, crossover: 'gene', offspring: 'equal', spawn: 'anywhere', seed: '', rules: {}, ...(saved || {}) };
  for (const s of SCHEMA.settings) if (cfg[s.key] == null) cfg[s.key] = s.default;
  for (const k of ['disabled_sensors', 'disabled_inner', 'disabled_actions']) if (!Array.isArray(cfg[k])) cfg[k] = [];
  for (const r of SCHEMA.rules) {
    cfg.rules[r.id] = { enabled: false, ...Object.fromEntries(r.params.map(p => [p.key, p.default])), ...(cfg.rules[r.id] || {}) };
  }
  map = { shape: 'square', zone: 'safe_right', w: 128, h: 128, ...(store.get('evosim.map2', {})), terrain: null };
  if (!saved) applyScenario(SCHEMA.scenarios[0], false);
  buildSetup();
  await loadMap();
  brainView = new BrainView($('#brain'), $('#brain-tip'), SCHEMA);
  deathChart = new LineChart($('#chart-death'), [{ key: 'death_rate', label: 'Death rate', color: '#ff2d2d' }], {});
  divChart = new LineChart($('#chart-div'), [{ key: 'diversity', label: 'Distinct genes', color: '#1f5bff' }, { key: 'minority', label: 'Genomes unlike the most common one', color: '#ff2fa0' }], {});
  bindRunUI();
  // resume an in-progress run (e.g. after a page reload)
  const f = await api('frame');
  if (f.active) { map.w = f.w; map.h = f.h; enterRun(true); }
}

function slider(key, label, min, max, step, hint, obj = cfg, onchange) {
  const num = h('input', { type: 'number', min, max, step });
  const rng = h('input', { type: 'range', min, max, step });
  const set = (v, fromUser) => {
    v = Math.min(max, Math.max(min, +v)); if (isNaN(v)) v = obj[key];
    obj[key] = v; num.value = v; rng.value = v; if (fromUser) { persist(); onchange && onchange(v); }
  };
  rng.oninput = () => set(rng.value, true); num.onchange = () => set(num.value, true);
  set(obj[key], false);
  return h('div', { class: 'field' }, h('label', {}, label), h('div', { class: 'row' }, rng, num), hint ? h('div', { class: 'hint' }, hint) : null);
}
function select(label, value, options, onchange, hint) {
  const s = h('select', { onchange: () => onchange(s.value) }, options.map(o => h('option', { value: o.id ?? o[0], selected: (o.id ?? o[0]) === value }, o.name ?? o[1])));
  return h('div', { class: 'field' }, h('label', {}, label), s, hint ? h('div', { class: 'hint' }, hint) : null);
}
const persist = () => { store.set('evosim.cfg2', cfg); store.set('evosim.map2', { shape: map.shape, zone: map.zone, w: map.w, h: map.h }); };

function card(title, ...body) { return h('div', { class: 'card' }, h('h3', {}, title), ...body); }

function buildSetup() {
  const root = $('#setup-form'); root.innerHTML = '';
  const S = Object.fromEntries(SCHEMA.settings.map(s => [s.key, s]));
  const sl = k => slider(k, S[k].label, S[k].min, S[k].max, S[k].step, S[k].hint);

  // scenarios
  const scn = h('div', { class: 'scenarios' }, SCHEMA.scenarios.map(s =>
    h('button', { class: 'scn', 'data-id': s.id, onclick: () => { applyScenario(s, true); } }, h('b', {}, s.name), h('span', {}, s.desc))));
  root.append(card('Start from a scenario', scn, h('div', { class: 'hint', style: 'margin-top:8px' }, 'Pick one as a starting point, then tweak anything below.')));

  root.append(card('Population & time', h('div', { class: 'form-grid' }, sl('population'), sl('steps'), sl('max_gens'),
    h('div', { class: 'field' }, h('label', {}, 'Random seed'), h('input', { type: 'number', placeholder: 'random', value: cfg.seed, onchange: e => { cfg.seed = e.target.value; persist(); } }), h('div', { class: 'hint' }, 'Fill in for reproducible runs.')))));

  const nCard = neuronCard();
  root.append(card('Genetics', h('div', { class: 'form-grid' }, sl('n_genes'),
    slider('n_inner', S.n_inner.label, S.n_inner.min, S.n_inner.max, S.n_inner.step, S.n_inner.hint, cfg, nCard.render), sl('mutation_rate'))));
  root.append(card('Brain neurons', h('div', { class: 'hint', style: 'margin-bottom:8px' }, 'Untick a neuron to remove it from every cell\'s brain. Genes are re-mapped onto the neurons that remain.'), nCard.el));

  const partners = slider('partners', 'Partners per child', 1, 9, 1, 'Each child mixes genes from itself plus this many random mates.');
  const repro = h('div', {}, );
  const modeSeg = h('div', { class: 'seg' }, [['asexual', 'Asexual (clones)'], ['sexual', 'Sexual (mix genes)']].map(([m, l]) =>
    h('button', { 'data-m': m, class: cfg.mode === m ? 'on' : '', onclick: () => { cfg.mode = m; persist(); refreshMode(); } }, l)));
  const extra = h('div', { class: 'form-grid', style: 'margin-top:12px' }, partners,
    select('Gene mixing', cfg.crossover, [['gene', 'Whole genes from each parent'], ['nucleotide', 'Hex digit by digit (finer)']], v => { cfg.crossover = v; persist(); }),
    select('Who gets to breed', cfg.offspring, [['equal', 'Every survivor equally'], ['random', 'Random survivors (luck)']], v => { cfg.offspring = v; persist(); }));
  const refreshMode = () => {
    modeSeg.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.m === cfg.mode));
    partners.style.display = cfg.mode === 'sexual' ? '' : 'none'; extra.children[1].style.display = cfg.mode === 'sexual' ? '' : 'none';
  };
  repro.append(modeSeg, extra); root.append(card('Reproduction', repro)); refreshMode();

  // world
  const sizeChange = () => { persist(); loadMap(); };
  const mw = { w: map.w, h: map.h };
  root.append(card('World', h('div', { class: 'form-grid' },
    select('Map shape', map.shape, SCHEMA.shapes, v => { map.shape = v; sizeChange(); }),
    select('Zone preset', map.zone, SCHEMA.zones, v => { map.zone = v; sizeChange(); }, 'Safe (green) and hazard (red) pixels used by the mortality rules.'),
    slider('w', 'Map width (px)', 32, 256, 8, '', map, sizeChange), slider('h', 'Map height (px)', 32, 256, 8, '', map, sizeChange),
    select('Spawn area', cfg.spawn, SCHEMA.spawns, v => { cfg.spawn = v; persist(); }, 'Where each generation starts.'), sl('pher_decay'), sl('death_pher'),
    h('div', { class: 'field' }, h('label', {}, 'Moving hazards'),
      h('label', { class: 'check' }, h('input', { type: 'checkbox', checked: !!cfg.hazard_shuffle, onchange: e => { cfg.hazard_shuffle = e.target.checked; persist(); } }), 'Slide the hazard pattern to a new spot every generation'),
      h('div', { class: 'hint' }, 'Stops cells memorising where the hazards are from their X/Y position.')))));

  // rules
  const rl = h('div', {});
  for (const r of SCHEMA.rules) {
    const c = cfg.rules[r.id];
    const el = h('div', { class: 'rule' + (c.enabled ? ' on' : ''), style: `--rc:${r.color}` });
    const head = h('div', { class: 'rule-head', onclick: () => { c.enabled = !c.enabled; el.classList.toggle('on', c.enabled); persist(); warn(); } },
      h('i', { class: 'dot' }), h('b', {}, r.name), h('span', { class: 'switch' }));
    const body = h('div', { class: 'rule-body' }, h('p', {}, r.desc),
      h('div', { class: 'form-grid' }, r.params.map(p => p.type === 'select'
        ? select(p.label, c[p.key], p.options, v => { c[p.key] = v; persist(); })
        : slider(p.key, p.label, p.min, p.max, p.step, p.hint, c, warn))));
    el.append(head, body); rl.append(el);
  }
  root.append(card('Mortality conditions', h('div', { class: 'hint', style: 'margin-bottom:10px' }, 'A cell dies as soon as any enabled rule says so. Combine as many as you like.'), rl));
  refreshScenarioButtons();
}

/* a brain-shaped checklist: senses on the left, inner neurons in the middle, actions on the right */
function neuronCard() {
  const el = h('div', { class: 'neurons' });
  const render = () => {
    el.innerHTML = '';
    const toggle = (list, key, on) => { const i = list.indexOf(key); if (on && i >= 0) list.splice(i, 1); if (!on && i < 0) list.push(key); persist(); render(); };
    const row = (cls, kind, key, text, desc, list, label) => {
      const on = !list.includes(key);
      const cb = h('input', { type: 'checkbox', checked: on, title: 'Switch this neuron on or off', onchange: e => toggle(list, key, e.target.checked) });
      const circ = h('i', { class: 'ncirc ' + kind }, label || '');
      const nl = h('span', { class: 'nl', title: desc }, text || '');
      const kids = cls === 's' ? [nl, circ, cb] : cls === 'a' ? [cb, circ, nl] : [circ, cb];
      return h('div', { class: 'nrow ' + cls + (on ? '' : ' off') }, ...kids);
    };
    const bulk = (name, list, keys) => h('div', { class: 'nbulk' },
      h('a', { onclick: () => { list.length = 0; persist(); render(); } }, 'all on'), ' · ',
      h('a', { onclick: () => { list.length = 0; list.push(...keys); persist(); render(); } }, 'all off'));
    const inner = [...Array(cfg.n_inner).keys()];
    cfg.disabled_inner = cfg.disabled_inner.filter(i => i < cfg.n_inner);
    el.append(
      h('div', { class: 'ncol' }, h('div', { class: 'nhead' }, 'SENSES'), bulk('s', cfg.disabled_sensors, SCHEMA.sensors.map(s => s.key)),
        ...SCHEMA.sensors.map(s => row('s', 'sensor', s.key, s.name, s.desc, cfg.disabled_sensors))),
      h('div', { class: 'ncol' }, h('div', { class: 'nhead' }, 'INNER'), bulk('i', cfg.disabled_inner, inner),
        ...(inner.length ? inner.map(i => row('i', 'inner', i, '', 'Inner neuron ' + (i + 1), cfg.disabled_inner, String(i + 1))) : [h('div', { class: 'hint center' }, 'none')])),
      h('div', { class: 'ncol' }, h('div', { class: 'nhead' }, 'ACTIONS'), bulk('a', cfg.disabled_actions, SCHEMA.actions.map(a => a.key)),
        ...SCHEMA.actions.map(a => row('a', 'action', a.key, a.name, a.desc, cfg.disabled_actions))));
    if (cfg.disabled_sensors.length === SCHEMA.sensors.length || cfg.disabled_actions.length === SCHEMA.actions.length)
      el.append(h('div', { class: 'warn', style: 'grid-column:1/-1;margin-top:6px' }, '⚠ With every sense or every action off, cells cannot do anything.'));
  };
  render();
  return { el, render };
}

function applyScenario(s, rebuild) {
  cfg.rules = Object.fromEntries(SCHEMA.rules.map(r => [r.id, { enabled: false, ...Object.fromEntries(r.params.map(p => [p.key, p.default])), ...(s.rules[r.id] || {}) }]));
  for (const sd of SCHEMA.settings) cfg[sd.key] = (s.settings && s.settings[sd.key]) ?? sd.default;
  cfg.spawn = s.spawn || 'anywhere'; map.shape = s.shape; map.zone = s.zone; cfg.scenario = s.id; cfg.hazard_shuffle = !!s.shuffle;
  cfg.disabled_sensors = []; cfg.disabled_inner = []; cfg.disabled_actions = [];
  [map.w, map.h] = s.size || [128, 128];
  persist();
  if (rebuild) { buildSetup(); loadMap(); }
}
function refreshScenarioButtons() { document.querySelectorAll('.scn').forEach(b => b.classList.toggle('on', b.dataset.id === cfg.scenario)); }

/* ============================================================== map editor */
let tool = T.WALL;
async function loadMap() {
  const r = await api(`map?shape=${map.shape}&zone=${map.zone}&w=${map.w}&h=${map.h}`);
  map.w = r.w; map.h = r.h; map.terrain = Uint8Array.from(atob(r.data), c => c.charCodeAt(0));
  drawPreview(); warn();
}
function drawPreview() {
  const cv = $('#map-preview'); cv.width = map.w; cv.height = map.h;
  const g = cv.getContext('2d'), img = g.createImageData(map.w, map.h);
  const pal = TERRAIN_COLORS.map(c => [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)]);
  for (let x = 0; x < map.w; x++) for (let y = 0; y < map.h; y++) {
    const p = pal[map.terrain[x * map.h + y]], o = (y * map.w + x) * 4; img.data[o] = p[0]; img.data[o + 1] = p[1]; img.data[o + 2] = p[2]; img.data[o + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  $('#map-info').textContent = `${map.w}×${map.h}`;
  refreshScenarioButtons();
}
function warn() {
  const box = $('#warnings'); box.innerHTML = '';
  if (!map.terrain) return;
  const cnt = [0, 0, 0, 0]; for (const v of map.terrain) cnt[v]++;
  const add = t => box.append(h('div', { class: 'warn' }, '⚠ ' + t));
  const R = cfg.rules;
  if (R.safe.enabled && !cnt[T.SAFE]) add('"Safe zone" is on but there are no safe pixels, so the rule is ignored. Pick a zone preset or paint some.');
  if (R.hazard.enabled && !cnt[T.HAZARD]) add('"Hazard pixels" is on but there are no hazard pixels, so the rule is ignored.');
  if (!Object.values(R).some(r => r.enabled)) add('No mortality rule is enabled: nobody will ever die and nothing will evolve.');
  if (cfg.population > cnt[0] + cnt[3]) add(`Only ${cnt[0] + cnt[3]} free pixels: population will be capped.`);
}
(function paintSetup() {
  const seg = $('#paint-tool');
  [['Wall', T.WALL], ['Hazard', T.HAZARD], ['Safe', T.SAFE], ['Erase', T.OPEN]].forEach(([l, v]) =>
    seg.append(h('button', { class: v === tool ? 'on' : '', onclick: e => { tool = v; seg.querySelectorAll('button').forEach(b => b.classList.remove('on')); e.target.classList.add('on'); } }, l)));
  $('#brush').oninput = e => $('#brush-v').textContent = e.target.value;
  $('#clear-paint').onclick = () => { for (let i = 0; i < map.terrain.length; i++) if (map.terrain[i] >= 2) map.terrain[i] = 0; drawPreview(); warn(); };
  const cv = $('#map-preview'); let down = false;
  const paintAt = e => {
    const r = cv.getBoundingClientRect(), cx = (e.clientX - r.left) / r.width * map.w, cy = (e.clientY - r.top) / r.height * map.h;
    const br = +$('#brush').value; let changed = false;
    for (let x = Math.max(0, Math.floor(cx - br)); x <= Math.min(map.w - 1, Math.ceil(cx + br)); x++)
      for (let y = Math.max(0, Math.floor(cy - br)); y <= Math.min(map.h - 1, Math.ceil(cy + br)); y++)
        if ((x + .5 - cx) ** 2 + (y + .5 - cy) ** 2 <= br * br) { map.terrain[x * map.h + y] = tool; changed = true; }
    if (changed) drawPreview();
  };
  cv.addEventListener('pointerdown', e => { down = true; cv.setPointerCapture(e.pointerId); paintAt(e); });
  cv.addEventListener('pointermove', e => { if (down) paintAt(e); });
  cv.addEventListener('pointerup', () => { down = false; warn(); });
})();

/* ============================================================ run state */
let brainView, deathChart, divChart;
let polling = false, stats = [], world = null, spotCanvas = null, terrainCanvas = null, S = 5;
let selected = null, brainGen = 0, brainGens = 1, brainLive = true, brainMode = 'pop', brainCache = {}, lastFrame = null, brainPlay = null;
let tickBusy = false, statsBusy = false, artShown = false, lastTver = -1, lastTrid = 0, trAnim = null, prevCanvas = null;

function b64(u8) { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }

async function startRun() {
  persist();
  const rules = JSON.parse(JSON.stringify(cfg.rules));
  const config = { ...cfg, rules };
  try {
    await api('start', { w: map.w, h: map.h, terrain: b64(map.terrain), config, speed: speedFromSlider() });
  } catch (e) { alert('Could not start: ' + e.message); return; }
  enterRun(false);
}
function enterRun(resumed) {
  document.body.dataset.view = 'run'; artShown = false;
  lastTver = -1; lastTrid = 0; trAnim = null; $('#trans-note').hidden = true;
  Hands.init(map.w, map.h); Hands.setSource('off'); syncHandButtons();
  stats = []; brainCache = {}; selected = null; brainGen = 0; brainLive = true; brainMode = 'pop'; lastFrame = null;
  setBrainMode('pop');
  S = Math.max(2, Math.ceil(720 / Math.max(map.w, map.h)));
  world = $('#world'); world.width = map.w * S; world.height = map.h * S;
  terrainCanvas = document.createElement('canvas'); terrainCanvas.width = world.width; terrainCanvas.height = world.height;
  spotCanvas = document.createElement('canvas'); spotCanvas.width = world.width; spotCanvas.height = world.height;
  prevCanvas = document.createElement('canvas'); prevCanvas.width = world.width; prevCanvas.height = world.height;
  drawTerrain();
  $('#banner').hidden = true; $('#btn-play').textContent = 'Pause';
  deathChart.setData([]); divChart.setData([]); $('#cause-chips').innerHTML = '';
  if (resumed) api('frame').then(f => { $('#speed').value = sliderFromSpeed(f.speed); updateSpeedLabel(); });
  if (!tickBusy) loop();
}
function drawTerrain() {
  // when resuming after reload `map.terrain` may not match; fall back to the regenerated preview
  const g = terrainCanvas.getContext('2d'); g.fillStyle = TERRAIN_COLORS[0]; g.fillRect(0, 0, terrainCanvas.width, terrainCanvas.height);
  if (!map.terrain) return;
  for (let x = 0; x < map.w; x++) for (let y = 0; y < map.h; y++) {
    const v = map.terrain[x * map.h + y]; if (!v) continue;
    g.fillStyle = TERRAIN_COLORS[v]; g.fillRect(x * S, y * S, S, S);
  }
}
const cellColor = c => '#' + c.toString(16).padStart(6, '0');   // the genome's own colour, undiluted, one pixel per cell

function renderWorld() {
  if (!lastFrame || !world) return;
  const g = world.getContext('2d'); g.drawImage(terrainCanvas, 0, 0);
  if ($('#t-spots').checked) g.drawImage(spotCanvas, 0, 0);
  if ($('#t-prev').checked) g.drawImage(prevCanvas, 0, 0);
  if ($('#t-pher').checked && lastFrame.pher) {
    const bin = atob(lastFrame.pher);
    for (let x = 0; x < map.w; x++) for (let y = 0; y < map.h; y++) {
      const v = bin.charCodeAt(x * map.h + y); if (v < 6) continue;
      g.fillStyle = `rgba(255,47,160,${Math.min(.85, v / 255 * 1.1)})`; g.fillRect(x * S, y * S, S, S);
    }
  }
  if (Hands.active && Hands.any) { g.imageSmoothingEnabled = false; g.globalAlpha = .45; g.drawImage(Hands.canvas, 0, 0, world.width, world.height); g.globalAlpha = 1; }
  if (trAnim) { drawTransition(g, trAnim); return; }
  if ($('#t-cells').checked) {
    const f = lastFrame;
    for (let i = 0; i < f.x.length; i++) { g.fillStyle = cellColor(f.c[i]); g.fillRect(f.x[i] * S, f.y[i] * S, S, S); }
  }
  if (selected && selected.pos) {
    g.strokeStyle = '#111'; g.lineWidth = 2; g.strokeRect(selected.pos[0] * S - 3, selected.pos[1] * S - 3, S + 6, S + 6);
  }
}

/* generation changeover: who died, who bred, where the children appear */
const TR_A = 1.1, TR_B = 2.2, TR_END = 3.4;
function drawTransition(g, a) {
  const t = (performance.now() - a.t0) / 1000, d = a.d, note = $('#trans-note');
  if (t > TR_END) { trAnim = null; note.hidden = true; return; }
  const surv = d.survivors, ch = d.children, S2 = S;
  note.hidden = false;
  note.textContent = `Generation ${d.gen + 1}: ${d.dead.length / 3} died, ${surv.x.length} survived and bred ${ch.x.length} new cells for generation ${d.gen + 2}`;
  const ease = x => Math.min(1, Math.max(0, x));
  const survAlpha = t < TR_A ? 1 : 1 - .65 * ease((t - TR_A) / (TR_B - TR_A)) - (t > TR_B ? .35 * ease((t - TR_B) / 0.5) : 0);
  // dead: crosses in their cause-of-death colour, pulsing then fading
  const deadAlpha = t < TR_A ? .65 + .35 * Math.sin(t * 12) : 1 - ease((t - TR_A) / .6);
  if (deadAlpha > 0) {
    g.lineWidth = 2; g.globalAlpha = Math.max(0, deadAlpha);
    for (let i = 0; i < d.dead.length; i += 3) {
      const x = (d.dead[i] + .5) * S2, y = (d.dead[i + 1] + .5) * S2, r = S2 * 1.1;
      g.strokeStyle = causeColor[d.dead[i + 2]] || '#ff2d2d';
      g.beginPath(); g.moveTo(x - r, y - r); g.lineTo(x + r, y + r); g.moveTo(x + r, y - r); g.lineTo(x - r, y + r); g.stroke();
    }
    g.globalAlpha = 1;
  }
  if (survAlpha > 0) {
    g.globalAlpha = Math.max(0, survAlpha);
    for (let i = 0; i < surv.x.length; i++) { g.fillStyle = cellColor(surv.c[i]); g.fillRect(surv.x[i] * S2, surv.y[i] * S2, S2, S2); }
    g.globalAlpha = 1;
  }
  // parent -> child lines
  if (t > TR_A) {
    const p = ease((t - TR_A) / (TR_B - TR_A)), fade = t > TR_B ? 1 - ease((t - TR_B) / (TR_END - TR_B)) : 1;
    g.lineWidth = 1;
    for (let i = 0; i < ch.x.length; i++) {
      g.strokeStyle = cellColor(ch.c[i]); g.globalAlpha = .55 * fade;
      ch.p[i].forEach((pi, k) => {
        const px = (surv.x[pi] + .5) * S2, py = (surv.y[pi] + .5) * S2, cx = (ch.x[i] + .5) * S2, cy = (ch.y[i] + .5) * S2;
        g.globalAlpha = (k ? .25 : .55) * fade;
        g.beginPath(); g.moveTo(px, py); g.lineTo(px + (cx - px) * p, py + (cy - py) * p); g.stroke();
      });
    }
    g.globalAlpha = 1;
  }
  // children pop in
  if (t > TR_B) {
    const k = ease((t - TR_B) / 0.6), size = S2 * (1 + 1.6 * (1 - k));
    for (let i = 0; i < ch.x.length; i++) {
      const cx = (ch.x[i] + .5) * S2, cy = (ch.y[i] + .5) * S2;
      g.fillStyle = cellColor(ch.c[i]); g.fillRect(ch.x[i] * S2, ch.y[i] * S2, S2, S2);
      if (k < 1) { g.strokeStyle = '#111'; g.lineWidth = 1.5; g.strokeRect(cx - size / 2, cy - size / 2, size, size); }
    }
  }
}

/* where the previous generation died: little dark-red translucent spots */
function drawPrevDeaths() {
  const g = prevCanvas.getContext('2d'); g.clearRect(0, 0, prevCanvas.width, prevCanvas.height);
  const s = stats[stats.length - 1]; if (!s) return;
  const size = Math.max(2, Math.round(S * .6)), off = (S - size) / 2;
  g.fillStyle = 'rgba(120,0,0,0.5)';
  for (let i = 0; i < s.deaths.length; i += 3) g.fillRect(s.deaths[i] * S + off, s.deaths[i + 1] * S + off, size, size);
}

/* death spots */
const causeColor = {}; 
function drawSpots() {
  const g = spotCanvas.getContext('2d'); g.clearRect(0, 0, spotCanvas.width, spotCanvas.height);
  const mode = $('#spot-mode').value, byCause = $('#t-cause').checked;
  const from = mode === 'last' ? stats.length - 1 : mode === 'recent' ? stats.length - 10 : 0;
  for (let k = Math.max(0, from); k < stats.length; k++) paintDeaths(g, stats[k].deaths, byCause);
}
function paintDeaths(g, d, byCause) {
  for (let i = 0; i < d.length; i += 3) {
    g.fillStyle = byCause ? causeColor[d[i + 2]] + '40' : 'rgba(255,45,45,0.22)';
    g.fillRect(d[i] * S, d[i + 1] * S, S, S);
  }
}

/* polling loop */
async function loop() {
  tickBusy = true;
  while (document.body.dataset.view === 'run') {
    const t0 = performance.now();
    try {
      const f = await api('frame' + ($('#t-pher').checked ? '?pher=1' : ''));
      if (!f.active) break;
      if (f.tver !== lastTver) {
        lastTver = f.tver;
        const tr = await api('terrain');
        if (tr.data) { map.terrain = Uint8Array.from(atob(tr.data), c => c.charCodeAt(0)); drawTerrain(); }
      }
      if (f.trid !== lastTrid) {
        lastTrid = f.trid;
        if ($('#t-trans').checked) { const d = await api('transition'); if (d.survivors) trAnim = { d, t0: performance.now() }; }
      }
      lastFrame = f; updateChips(f); renderWorld();
      if (f.n_stats > stats.length) await pullStats();
      await updateBrain(f);
      const done = f.status === 'extinct' || f.status === 'finished';
      if (done && !artShown) { artShown = true; openArt().catch(console.error); }
      const ban = $('#banner'); ban.hidden = !done; if (done) ban.textContent = f.message + ' Press “Settings” to start another run.';
      $('#btn-play').textContent = f.paused ? 'Resume' : 'Pause'; $('#btn-play').disabled = done;
    } catch (e) { console.error(e); }
    await new Promise(r => setTimeout(r, Math.max(10, 60 - (performance.now() - t0))));
  }
  tickBusy = false;
}
async function pullStats() {
  if (statsBusy) return; statsBusy = true;
  try {
    while (true) {
      const r = await api('stats?since=' + stats.length);
      if (!r.stats.length) break;
      for (const s of r.stats) { stats.push(s); if ($('#spot-mode').value === 'all' || true) paintIncremental(s); }
      if (stats.length >= r.total) break;
    }
    deathChart.setData(stats); divChart.setData(stats);
    const last = stats[stats.length - 1];
    if (last) showCauses(last);
    if ($('#spot-mode').value !== 'all') drawSpots();
    drawPrevDeaths();
  } finally { statsBusy = false; }
}
function paintIncremental(s) { if ($('#spot-mode').value === 'all') paintDeaths(spotCanvas.getContext('2d'), s.deaths, $('#t-cause').checked); }
function showCauses(s) {
  const box = $('#cause-chips'); box.innerHTML = '';
  box.append(h('span', { class: 'chip' }, `Gen ${s.gen + 1} deaths:`, h('b', {}, `${s.pop - s.survivors} / ${s.pop}`)));
  for (const r of SCHEMA.rules) if (s.causes[r.id]) box.append(h('span', { class: 'chip' }, h('i', { style: `background:${r.color}` }), r.name, h('b', {}, s.causes[r.id])));
}
function updateChips(f) {
  const last = stats[stats.length - 1];
  const el = $('#run-chips'); el.innerHTML = '';
  const add = (l, v) => el.append(h('span', { class: 'chip' }, l, h('b', {}, v)));
  add('Generation', f.gen + 1 + (cfg.max_gens ? ' / ' + cfg.max_gens : ''));
  el.append(h('span', { class: 'chip' }, 'Step', h('b', {}, `${f.step}/${f.steps}`), h('span', { class: 'progress' }, h('i', { style: `width:${100 * f.step / f.steps}%` }))));
  add('Alive', `${f.alive} / ${f.n}`);
  if (last) { add('Last death rate', last.death_rate.toFixed(1) + '%'); add('Diversity', last.diversity.toFixed(1) + '%'); }
}

/* ============================================================ run controls */
const speedFromSlider = () => { const v = +$('#speed').value / 100; return v >= 1 ? SCHEMA.max_speed : Math.round(4 * Math.pow(400, v)); };
const sliderFromSpeed = sp => sp >= SCHEMA.max_speed ? 100 : Math.round(100 * Math.log(sp / 4) / Math.log(400));
function updateSpeedLabel() { const s = speedFromSlider(); $('#speed-v').textContent = s >= SCHEMA.max_speed ? 'max' : s + ' steps/s'; }

function bindRunUI() {
  SCHEMA.rules.forEach((r, i) => causeColor[i] = r.color);
  $('#btn-start').onclick = startRun;
  $('#btn-art').onclick = () => openArt().catch(console.error);
  $('#art-close').onclick = () => $('#art-modal').hidden = true;
  $('#btn-new').onclick = async () => { Hands.stop(); await api('control', { action: 'stop' }); document.body.dataset.view = 'setup'; $('#run-chips').innerHTML = ''; clearInterval(brainPlay); };
  $('#btn-play').onclick = async () => { const paused = lastFrame && lastFrame.paused; await api('control', { action: paused ? 'resume' : 'pause' }); };
  $('#speed').oninput = async () => { updateSpeedLabel(); await api('control', { action: 'speed', value: speedFromSlider() }); };
  updateSpeedLabel();
  $('#t-spots').onchange = renderWorld;
  $('#spot-mode').onchange = () => { drawSpots(); renderWorld(); };
  $('#t-cause').onchange = () => { drawSpots(); renderWorld(); };
  $('#t-cells').onchange = renderWorld;
  $('#t-prev').onchange = () => { drawPrevDeaths(); renderWorld(); };
  $('#t-trans').onchange = async e => { trAnim = null; $('#trans-note').hidden = true; await api('control', { action: 'transition', value: e.target.checked }); };
  $('#hand-mouse').onclick = () => toggleHand('mouse');
  $('#hand-cam').onclick = () => toggleHand('webcam');
  Hands.onStatus = (t, alert) => { const el = $('#hand-status'); el.textContent = t; el.classList.toggle('alert', !!alert); };
  world = $('#world');
  world.addEventListener('mousemove', e => { const r = world.getBoundingClientRect(); Hands.mouseAt((e.clientX - r.left) / r.width * map.w, (e.clientY - r.top) / r.height * map.h); });
  world.addEventListener('mouseleave', () => Hands.mouseAt(null));
  $('#t-pher').onchange = renderWorld;
  $('#clear-spots').onclick = () => { stats.forEach(s => s.deaths = []); spotCanvas.getContext('2d').clearRect(0, 0, spotCanvas.width, spotCanvas.height); renderWorld(); };
  world = $('#world');
  world.addEventListener('click', async e => {
    const r = world.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * map.w - .5, y = (e.clientY - r.top) / r.height * map.h - .5;
    const res = await api('select', { x, y });
    if (res.id == null) { selected = null; return; }
    selected = { id: res.id, gen: lastFrame.gen }; setBrainMode('cell');
  });
  // brain controls
  $('#brain-mode').querySelectorAll('button').forEach(b => b.onclick = () => setBrainMode(b.dataset.m));
  $('#brain-gen').oninput = e => { brainLive = false; brainGen = +e.target.value; clearInterval(brainPlay); brainPlay = null; $('#brain-play').textContent = 'Play'; updateBrain(lastFrame, true); };
  $('#brain-live').onclick = () => { brainLive = true; updateBrain(lastFrame, true); };
  $('#brain-play').onclick = () => {
    if (brainPlay) { clearInterval(brainPlay); brainPlay = null; $('#brain-play').textContent = 'Play'; return; }
    brainLive = false; if (brainGen >= brainGens - 1) brainGen = 0; $('#brain-play').textContent = 'Stop';
    brainPlay = setInterval(() => { if (brainGen >= brainGens - 1) { clearInterval(brainPlay); brainPlay = null; $('#brain-play').textContent = 'Play'; return; } brainGen++; updateBrain(lastFrame, true); }, 120);
  };
  $('#brain-min').oninput = e => { $('#brain-min-v').textContent = e.target.value + '%'; brainView.set({ minFreq: e.target.value / 100 }); };
  $('#brain-hide').onchange = e => brainView.set({ hideUnused: e.target.checked });
  document.addEventListener('keydown', e => { if (e.code === 'Space' && document.body.dataset.view === 'run' && e.target.tagName !== 'INPUT') { e.preventDefault(); $('#btn-play').click(); } });
}

async function toggleHand(kind) {
  const next = Hands.source === kind ? 'off' : kind;
  try { await Hands.setSource(next); } catch (e) {}
  syncHandButtons();
}
function syncHandButtons() {
  $('#hand-cam').classList.toggle('on', Hands.source === 'webcam');
  $('#hand-mouse').classList.toggle('on', Hands.source === 'mouse');
  if (Hands.source === 'off') Hands.onStatus(cfg.rules.hands && cfg.rules.hands.enabled ? 'The Hands rule is on: switch on the webcam or mouse so cells have a hand to react to.' : '', cfg.rules.hands && cfg.rules.hands.enabled);
}

function setBrainMode(m) {
  brainMode = m;
  $('#brain-mode').querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.m === m));
  $('#brain-controls').style.display = m === 'pop' ? '' : 'none';
  if (brainView) brainView.set({ cellMode: m === 'cell', activation: null, fired: null });
  $('#world-hint').textContent = m === 'cell' ? 'Showing the brain of the ringed cell (neuron glow = live activation).' : 'Click a cell to inspect its brain.';
}
async function updateBrain(f, force) {
  if (!f) return;
  if (brainMode === 'cell') {
    if (!selected) { brainView.set({ edges: [], cellMode: true }); $('#brain-sub').textContent = 'Click any cell on the map to see its individual brain.'; return; }
    if (selected.gen !== f.gen) { selected = null; $('#brain-sub').textContent = 'That cell’s generation has ended. Click another cell.'; brainView.set({ edges: [], activation: null }); return; }
    const b = await api('brain?cell=' + selected.id);
    if (b.gone) { selected = null; return; }
    selected.pos = [b.x, b.y];
    $('#brain-sub').innerHTML = `Cell #${selected.id} ${b.alive ? '' : '(dead)'}: every connection is fully opaque because it belongs to just this one genome.`;
    brainView.set({ edges: b.edges, activation: b.activation, fired: b.fired, cellMode: true, minFreq: 0, off: b.off || [] });
    return;
  }
  brainView.set({ cellMode: false, activation: null, fired: null, minFreq: $('#brain-min').value / 100 });
  const latest = f.gen;                       // brain index == generation index
  brainGens = latest + 1;
  const sl = $('#brain-gen'); sl.max = latest;
  if (brainLive) brainGen = latest;
  sl.value = brainGen;
  $('#brain-gen-v').textContent = 'gen ' + (brainGen + 1);
  $('#brain-live').style.opacity = brainLive ? .5 : 1;
  if (!brainCache[brainGen] || (brainGen === latest && brainCache[brainGen].stale !== false && brainCache[brainGen].forGen !== latest) || force) {
    const b = await api('brain?gen=' + brainGen); b.forGen = latest; brainCache[brainGen] = b;
  }
  const b = brainCache[brainGen];
  $('#brain-sub').textContent = `Population of generation ${brainGen + 1}: ${b.edges.length} distinct working connections across all cells.`;
  brainView.set({ edges: b.edges, nInner: b.n_inner, off: b.off || [] });
}

init();
