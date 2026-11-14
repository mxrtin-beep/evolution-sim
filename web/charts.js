/* Minimal dependency-free line chart with hover read-out. */
class LineChart {
  constructor(canvas, series, opts = {}) {
    this.c = canvas; this.series = series; this.opts = opts; this.data = []; this.hover = -1;
    canvas.addEventListener('mousemove', e => {
      const r = canvas.getBoundingClientRect(); this.mouseX = e.clientX - r.left; this.draw();
    });
    canvas.addEventListener('mouseleave', () => { this.mouseX = null; this.draw(); });
    new ResizeObserver(() => this.draw()).observe(canvas);
  }
  setData(rows) { this.data = rows; this.draw(); }
  draw() {
    const c = this.c, dpr = window.devicePixelRatio || 1;
    const W = c.clientWidth, H = c.clientHeight;
    if (!W || !H) return;
    if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const L = 40, R = 10, T = 8, B = 22, pw = W - L - R, ph = H - T - B;
    const n = this.data.length;
    let ymax = 0;
    for (const row of this.data) for (const s of this.series) ymax = Math.max(ymax, row[s.key] || 0);
    ymax = this.opts.yMax || niceCeil(Math.max(ymax, 5));
    g.font = '11px system-ui'; g.fillStyle = '#8a96b2'; g.strokeStyle = '#26314a'; g.lineWidth = 1;
    g.textAlign = 'right'; g.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const v = ymax * i / 4, y = T + ph - ph * i / 4;
      g.beginPath(); g.moveTo(L, y + .5); g.lineTo(W - R, y + .5); g.stroke();
      g.fillText(fmt(v) + '%', L - 6, y);
    }
    if (n === 0) { g.textAlign = 'center'; g.fillText('waiting for the first generation to finish…', W / 2, H / 2); return; }
    const X = i => L + (n === 1 ? pw / 2 : pw * i / (n - 1));
    const Y = v => T + ph - ph * Math.min(v / ymax, 1);
    g.textAlign = 'center'; g.textBaseline = 'top';
    const tickN = Math.min(6, n);
    for (let k = 0; k < tickN; k++) { const i = tickN === 1 ? 0 : Math.round((n - 1) * k / (tickN - 1)); g.fillText(String(this.data[i].gen + 1), X(i), H - B + 6); }
    for (const [si, s] of this.series.entries()) {
      g.beginPath();
      this.data.forEach((row, i) => { const x = X(i), y = Y(row[s.key] || 0); i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.strokeStyle = s.color; g.lineWidth = s.width || 2; g.setLineDash(s.dash || []); g.lineJoin = 'round'; g.stroke(); g.setLineDash([]);
      if (si === 0) {
        g.lineTo(X(n - 1), T + ph); g.lineTo(X(0), T + ph); g.closePath();
        const gr = g.createLinearGradient(0, T, 0, T + ph); gr.addColorStop(0, s.color + '44'); gr.addColorStop(1, s.color + '00');
        g.fillStyle = gr; g.fill();
      }
    }
    // legend
    g.textAlign = 'left'; g.textBaseline = 'middle'; let lx = L + 8;
    for (const s of this.series) { g.fillStyle = s.color; g.fillRect(lx, T + 5, 12, 3); g.fillStyle = '#c3cce0'; g.fillText(s.label, lx + 17, T + 6); lx += 28 + g.measureText(s.label).width; }
    // hover
    if (this.mouseX != null) {
      const i = Math.max(0, Math.min(n - 1, Math.round((this.mouseX - L) / pw * (n - 1))));
      const x = X(i), row = this.data[i];
      g.strokeStyle = '#ffffff55'; g.beginPath(); g.moveTo(x + .5, T); g.lineTo(x + .5, T + ph); g.stroke();
      const lines = ['Generation ' + (row.gen + 1), ...this.series.map(s => s.label + ': ' + fmt(row[s.key]) + '%')];
      const bw = Math.max(...lines.map(l => g.measureText(l).width)) + 16, bh = lines.length * 15 + 8;
      const bx = x + 12 + bw > W ? x - 12 - bw : x + 12, by = T + 18;
      g.fillStyle = '#0b1020ee'; g.strokeStyle = '#26314a'; g.beginPath(); g.roundRect(bx, by, bw, bh, 6); g.fill(); g.stroke();
      g.fillStyle = '#e6ebf5'; g.textAlign = 'left'; g.textBaseline = 'top';
      lines.forEach((l, k) => g.fillText(l, bx + 8, by + 6 + k * 15));
      this.series.forEach(s => { g.fillStyle = s.color; g.beginPath(); g.arc(x, Y(row[s.key] || 0), 3.5, 0, 7); g.fill(); });
    }
  }
}
function niceCeil(v) { const p = Math.pow(10, Math.floor(Math.log10(v))); for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p; return 10 * p; }
function fmt(v) { v = +v || 0; return v >= 10 ? v.toFixed(0) : v.toFixed(1); }
