/* Renders a neural network: sensory neurons -> inner neurons -> actions.
   Edge opacity encodes how common a connection is across the population. */
class BrainView {
  constructor(canvas, tip, schema) {
    this.c = canvas; this.tip = tip;
    this.sensors = schema.sensors; this.actions = schema.actions;
    this.edges = []; this.nInner = 4; this.minFreq = 0.03; this.hideUnused = false;
    this.activation = null; this.fired = null; this.cellMode = false; this.hoverNode = -1; this.cellColor = null;
    canvas.addEventListener('mousemove', e => this.onMove(e));
    canvas.addEventListener('mouseleave', () => { this.hoverNode = -1; tip.style.display = 'none'; this.draw(); });
    new ResizeObserver(() => this.draw()).observe(canvas);
  }
  set(data) { Object.assign(this, data); this.draw(); }

  nodeInfo(i) {
    const S = this.sensors.length, I = this.nInner;
    if (i < S) return { kind: 'sensor', ...this.sensors[i] };
    if (i < S + I) return { kind: 'inner', key: 'N' + (i - S + 1), name: 'Inner neuron ' + (i - S + 1), desc: 'Hidden neuron: mixes signals before they reach the actions.' };
    return { kind: 'action', ...this.actions[i - S - I] };
  }
  layout() {
    const W = this.c.clientWidth, H = this.c.clientHeight, S = this.sensors.length, A = this.actions.length, I = this.nInner;
    const top = 44, bot = 18, span = H - top - bot, pos = [];
    const sx = Math.min(135, W * .27), ax = W - sx, ix = W / 2;
    for (let i = 0; i < S; i++) pos.push({ x: sx, y: top + span * (i + .5) / S, r: Math.min(8, span / S * .36) });
    for (let j = 0; j < I; j++) pos.push({ x: ix, y: top + span * (j + .5) / I, r: Math.min(13, span / Math.max(I, 1) * .3) });
    for (let k = 0; k < A; k++) pos.push({ x: ax, y: top + span * (k + .5) / A, r: Math.min(8, span / A * .36) });
    return { W, H, pos, sx, ax, ix, top, bot };
  }
  onMove(e) {
    const r = this.c.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    const { pos } = this.layout(); let best = -1, bd = 15 * 15;
    pos.forEach((p, i) => { const d = (p.x - mx) ** 2 + (p.y - my) ** 2; if (d < bd) { bd = d; best = i; } });
    if (best !== this.hoverNode) { this.hoverNode = best; this.draw(); }
    if (best < 0) { this.tip.style.display = 'none'; return; }
    const n = this.nodeInfo(best);
    let extra = '';
    if (this.activation) extra = `<div class="muted">activation ${(+this.activation[best]).toFixed(2)}</div>`;
    this.tip.innerHTML = `<b>${n.name}</b>${n.desc}${extra}`;
    this.tip.style.display = 'block';
    const p = pos[best];
    this.tip.style.left = Math.min(p.x + 18, this.c.clientWidth - 250) + 'px'; this.tip.style.top = Math.max(4, p.y - 20) + 'px';
  }
  draw() {
    const c = this.c, dpr = window.devicePixelRatio || 1;
    const L = this.layout(); if (!L.W || !L.H) return;
    if (c.width !== Math.round(L.W * dpr) || c.height !== Math.round(L.H * dpr)) { c.width = Math.round(L.W * dpr); c.height = Math.round(L.H * dpr); }
    const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, L.W, L.H);
    const { pos } = L, S = this.sensors.length, I = this.nInner, M = pos.length;

    // column headers + soft lanes
    g.font = '600 10.5px system-ui'; g.textAlign = 'center'; g.fillStyle = '#6b7896'; g.textBaseline = 'middle';
    [['SENSES', L.sx], ['INNER NEURONS', L.ix], ['ACTIONS', L.ax]].forEach(([t, x]) => g.fillText(t.split('').join(String.fromCharCode(8202)), x, 18));

    const edges = this.edges.filter(e => e[2] >= this.minFreq && e[0] < M && e[1] < M);
    const part = new Array(M).fill(0);
    for (const e of edges) { part[e[0]] = Math.max(part[e[0]], e[2]); part[e[1]] = Math.max(part[e[1]], e[2]); }
    const hov = this.hoverNode;

    edges.slice().sort((a, b) => a[2] - b[2]).forEach(([s, d, f, w]) => {
      const a = pos[s], b = pos[d];
      const incident = hov < 0 || s === hov || d === hov;
      let alpha = (0.07 + 0.93 * Math.pow(f, 1.1)) * (incident ? 1 : 0.12);
      if (hov >= 0 && incident) alpha = Math.min(1, alpha + .25);
      const width = 0.8 + 2.6 * Math.min(Math.abs(w) / 4, 1);
      g.strokeStyle = (w >= 0 ? 'rgba(96,165,250,' : 'rgba(248,113,113,') + alpha + ')';
      g.fillStyle = g.strokeStyle; g.lineWidth = width; g.lineCap = 'round';
      this.edge(g, a, b, s === d, d >= S + I || s < S);
    });

    // nodes
    pos.forEach((p, i) => {
      const n = this.nodeInfo(i), used = part[i] > 0;
      if (this.hideUnused && !used && !this.cellMode) return;
      const base = { sensor: [52, 211, 153], inner: [167, 139, 250], action: [251, 191, 36] }[n.kind];
      let act = this.activation ? Math.min(1, Math.abs(this.activation[i])) : 0;
      const dim = (used || this.cellMode && used) ? 1 : 0.28;
      g.globalAlpha = (hov >= 0 && hov !== i) ? Math.min(dim, 1) * 0.75 : dim;
      // halo scales with how common the neuron's connections are
      const halo = (used ? 0.25 + 0.75 * part[i] : 0) * 7 + act * 8;
      if (halo > 1) { const rg = g.createRadialGradient(p.x, p.y, p.r, p.x, p.y, p.r + halo); rg.addColorStop(0, `rgba(${base},.55)`); rg.addColorStop(1, `rgba(${base},0)`); g.fillStyle = rg; g.beginPath(); g.arc(p.x, p.y, p.r + halo, 0, 7); g.fill(); }
      const gr = g.createRadialGradient(p.x - p.r * .35, p.y - p.r * .4, p.r * .1, p.x, p.y, p.r);
      const lit = 0.55 + 0.45 * act;
      gr.addColorStop(0, `rgb(${base.map(v => Math.min(255, v * 0.5 + 140) | 0)})`);
      gr.addColorStop(.55, `rgb(${base.map(v => v * lit | 0)})`);
      gr.addColorStop(1, `rgb(${base.map(v => v * 0.55 * lit | 0)})`);
      g.fillStyle = gr; g.beginPath(); g.arc(p.x, p.y, p.r, 0, 7); g.fill();
      g.lineWidth = (this.fired && this.fired[i - S - I] ? 2.4 : 1.2);
      g.strokeStyle = this.fired && n.kind === 'action' && this.fired[i - S - I] ? '#fff' : `rgba(255,255,255,.35)`;
      g.stroke();
      if (n.kind === 'inner') { g.fillStyle = '#0b1020'; g.font = '700 11px system-ui'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(n.key.slice(1), p.x, p.y + .5); }
      g.globalAlpha = 1;
      if (n.kind !== 'inner') {
        g.font = '12px system-ui'; g.textBaseline = 'middle';
        g.fillStyle = (used ? '#e6ebf5' : '#5d6988'); if (hov === i) g.fillStyle = '#fff';
        if (n.kind === 'sensor') { g.textAlign = 'right'; g.fillText(n.name, p.x - p.r - 8, p.y); }
        else { g.textAlign = 'left'; g.fillText(n.name, p.x + p.r + 8, p.y); }
      }
    });
    if (!edges.length) { g.fillStyle = '#6b7896'; g.font = '13px system-ui'; g.textAlign = 'center'; g.fillText('No connections above the frequency filter', L.W / 2, L.H / 2); }
  }
  edge(g, a, b, self, horizontal) {
    g.beginPath();
    let ex, ey, ang;
    if (self) {            // recurrent self-loop on an inner neuron
      const r = a.r; g.arc(a.x + r * .9, a.y - r * 1.15, r * .9, 0.35 * Math.PI, 2.55 * Math.PI); g.stroke();
      ex = a.x + r * .45; ey = a.y - r * .2; ang = Math.PI * .85;
    } else if (a.x === b.x) { // inner -> other inner (same column): arc out to the right
      const sx = a.x + a.r, ex_ = b.x + b.r, bulge = 28 + Math.abs(b.y - a.y) * .25;
      g.moveTo(sx, a.y); g.bezierCurveTo(sx + bulge, a.y, ex_ + bulge, b.y, ex_, b.y); g.stroke();
      ex = ex_; ey = b.y; ang = Math.PI;
    } else {
      const x1 = a.x + a.r, x2 = b.x - b.r, dx = (x2 - x1) * .5;
      g.moveTo(x1, a.y); g.bezierCurveTo(x1 + dx, a.y, x2 - dx, b.y, x2, b.y); g.stroke();
      ex = x2; ey = b.y; ang = Math.atan2(0, 1) + Math.atan2(b.y - a.y, Math.abs(x2 - x1)) * .0; // tangent is horizontal at the sink
    }
    // arrow head
    const s = Math.max(4, g.lineWidth * 2.2);
    g.save(); g.translate(ex, ey);
    g.rotate(self ? ang : (a.x === b.x ? Math.PI : 0));
    g.beginPath(); g.moveTo(0, 0); g.lineTo(-s, -s * .55); g.lineTo(-s, s * .55); g.closePath(); g.fill(); g.restore();
  }
}
