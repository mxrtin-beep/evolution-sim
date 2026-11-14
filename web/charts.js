/* Minimal flat line chart with hover read-out. */
const FONT = '"Helvetica Neue",Helvetica,Arial,sans-serif';
class LineChart {
  constructor(canvas, series, opts = {}) {
    this.c = canvas; this.series = series; this.opts = opts; this.data = [];
    canvas.addEventListener('mousemove', e => { this.mouseX = e.clientX - canvas.getBoundingClientRect().left; this.draw(); });
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
    const L = 40, R = 10, T = 22, B = 22, pw = W - L - R, ph = H - T - B, n = this.data.length;
    let ymax = 0;
    for (const row of this.data) for (const s of this.series) ymax = Math.max(ymax, row[s.key] || 0);
    ymax = this.opts.yMax || niceCeil(Math.max(ymax, 5));
    g.font = '11px ' + FONT; g.fillStyle = '#111'; g.strokeStyle = '#d9d5c8'; g.lineWidth = 1;
    g.textAlign = 'right'; g.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const v = ymax * i / 4, y = Math.round(T + ph - ph * i / 4) + .5;
      g.beginPath(); g.moveTo(L, y); g.lineTo(W - R, y); g.stroke(); g.fillText(fmt(v) + '%', L - 6, y);
    }
    g.strokeStyle = '#111'; g.lineWidth = 2; g.beginPath(); g.moveTo(L, T); g.lineTo(L, T + ph); g.lineTo(W - R, T + ph); g.stroke();
    // legend
    g.textAlign = 'left'; g.textBaseline = 'middle'; let lx = L;
    for (const s of this.series) { g.fillStyle = s.color; g.fillRect(lx, 6, 12, 8); g.fillStyle = '#111'; g.fillText(s.label, lx + 17, 10); lx += 34 + g.measureText(s.label).width; }
    if (n === 0) { g.textAlign = 'center'; g.fillStyle = '#6a6a62'; g.fillText('waiting for the first generation to finish…', W / 2, H / 2); return; }
    const X = i => L + (n === 1 ? pw / 2 : pw * i / (n - 1)), Y = v => T + ph - ph * Math.min(v / ymax, 1);
    g.textAlign = 'center'; g.textBaseline = 'top'; g.fillStyle = '#111';
    const tickN = Math.min(6, n);
    for (let k = 0; k < tickN; k++) { const i = tickN === 1 ? 0 : Math.round((n - 1) * k / (tickN - 1)); g.fillText(String(this.data[i].gen + 1), X(i), H - B + 6); }
    for (const s of this.series) {
      g.beginPath();
      this.data.forEach((row, i) => { const x = X(i), y = Y(row[s.key] || 0); i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.strokeStyle = s.color; g.lineWidth = s.width || 2.5; g.setLineDash(s.dash || []); g.lineJoin = 'miter'; g.stroke(); g.setLineDash([]);
    }
    if (this.mouseX != null) {
      const i = Math.max(0, Math.min(n - 1, Math.round((this.mouseX - L) / pw * (n - 1)))), x = X(i), row = this.data[i];
      g.strokeStyle = '#111'; g.lineWidth = 1; g.beginPath(); g.moveTo(x + .5, T); g.lineTo(x + .5, T + ph); g.stroke();
      const lines = ['Generation ' + (row.gen + 1), ...this.series.map(s => s.label + ': ' + fmt(row[s.key]) + '%')];
      g.font = '11px ' + FONT;
      const bw = Math.max(...lines.map(l => g.measureText(l).width)) + 16, bh = lines.length * 15 + 8;
      const bx = x + 10 + bw > W ? x - 10 - bw : x + 10, by = T + 6;
      g.fillStyle = '#fbfaf5'; g.fillRect(bx, by, bw, bh); g.strokeStyle = '#111'; g.lineWidth = 2; g.strokeRect(bx, by, bw, bh);
      g.fillStyle = '#111'; g.textAlign = 'left'; g.textBaseline = 'top';
      lines.forEach((l, k) => g.fillText(l, bx + 8, by + 6 + k * 15));
      this.series.forEach(s => { g.fillStyle = s.color; g.fillRect(x - 3, Y(row[s.key] || 0) - 3, 7, 7); });
    }
  }
}
function niceCeil(v) { const p = Math.pow(10, Math.floor(Math.log10(v))); for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p; return 10 * p; }
function fmt(v) { v = +v || 0; return v >= 10 ? v.toFixed(0) : v.toFixed(1); }
