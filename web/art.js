/* "Fossil record" artwork: every cell's footprint from every generation, hue-coded from first generation
   (blue) to last (gold), with death hot-spots, framed by the run's unique setup. */
function hashStr(s) { let x = 2166136261; for (let i = 0; i < s.length; i++) { x ^= s.charCodeAt(i); x = Math.imul(x, 16777619); } return (x >>> 0).toString(16).padStart(8, '0'); }
const u16 = b64 => { const bin = atob(b64), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new Uint16Array(u.buffer); };

function renderArt(canvas, d, info) {
  const W = 1400, MY = 150, mapH = Math.round((W - 160) * d.h / d.w), H = mapH + MY + 60 + 230;
  canvas.width = W; canvas.height = H;
  const g = canvas.getContext('2d');
  const bg = g.createRadialGradient(W / 2, H * .4, 50, W / 2, H * .4, H * .8); bg.addColorStop(0, '#12182b'); bg.addColorStop(1, '#04060c');
  g.fillStyle = bg; g.fillRect(0, 0, W, H);
  const mx = 80, my = MY, mw = W - 160;

  const trail = u16(d.trail), deaths = u16(d.deaths), terr = Uint8Array.from(atob(d.terrain), c => c.charCodeAt(0));
  const small = document.createElement('canvas'); small.width = d.w; small.height = d.h;
  const sg = small.getContext('2d'), img = sg.createImageData(d.w, d.h);
  const walls = document.createElement('canvas'); walls.width = d.w; walls.height = d.h;
  const wg = walls.getContext('2d'), wimg = wg.createImageData(d.w, d.h);
  const tots = [];
  for (let i = 0; i < d.w * d.h; i++) { const t = trail[i * 3] + trail[i * 3 + 1] + trail[i * 3 + 2]; if (t > 0) tots.push(t); }
  tots.sort((a, b) => a - b);
  const tmax = tots.length ? tots[Math.floor(tots.length * 0.985)] || 1 : 1;
  for (let x = 0; x < d.w; x++) for (let y = 0; y < d.h; y++) {
    const i = x * d.h + y, o = (y * d.w + x) * 4, r = trail[i * 3], gg = trail[i * 3 + 1], b = trail[i * 3 + 2];
    const tot = r + gg + b, mxc = Math.max(r, gg, b, 1);
    if (tot > 0) {
      const x = Math.min(tot / tmax, 1.4), br = Math.min(1, Math.pow(Math.log1p(6 * x) / Math.log1p(6), 2.4));
      const sat = v => Math.pow(v / mxc, 2.2);   // push colours apart so generations stay distinguishable
      img.data[o] = 255 * br * sat(r); img.data[o + 1] = 255 * br * sat(gg); img.data[o + 2] = 255 * br * sat(b); img.data[o + 3] = 255;
    }
    const t = terr[i];
    if (t === 1) { wimg.data[o] = 150; wimg.data[o + 1] = 170; wimg.data[o + 2] = 220; wimg.data[o + 3] = 46; }
    else if (t === 3) { wimg.data[o] = 60; wimg.data[o + 1] = 220; wimg.data[o + 2] = 140; wimg.data[o + 3] = 22; }
    else if (t === 2) { wimg.data[o] = 255; wimg.data[o + 1] = 70; wimg.data[o + 2] = 70; wimg.data[o + 3] = 30; }
  }
  sg.putImageData(img, 0, 0); wg.putImageData(wimg, 0, 0);

  g.save(); g.beginPath(); g.roundRect(mx - 14, my - 14, mw + 28, mapH + 28, 18); g.fillStyle = 'rgba(255,255,255,.025)'; g.fill();
  g.strokeStyle = 'rgba(160,180,230,.18)'; g.stroke(); g.clip();
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
  g.drawImage(walls, mx, my, mw, mapH);
  g.globalCompositeOperation = 'lighter';
  g.filter = 'blur(16px)'; g.globalAlpha = .7; g.drawImage(small, mx, my, mw, mapH);
  g.filter = 'blur(4px)'; g.globalAlpha = .5; g.drawImage(small, mx, my, mw, mapH);
  g.filter = 'none'; g.globalAlpha = 1; g.drawImage(small, mx, my, mw, mapH);
  // death hot-spots: little embers
  const sc = mw / d.w;
  for (let x = 0; x < d.w; x++) for (let y = 0; y < d.h; y++) {
    const v = deaths[x * d.h + y] / 65535; if (v < .04) continue;
    const r = sc * (.5 + 2.4 * Math.sqrt(v));
    const gr = g.createRadialGradient(mx + (x + .5) * sc, my + (y + .5) * sc, 0, mx + (x + .5) * sc, my + (y + .5) * sc, r);
    gr.addColorStop(0, `rgba(255,120,110,${.15 + .5 * v})`); gr.addColorStop(1, 'rgba(255,60,60,0)');
    g.fillStyle = gr; g.beginPath(); g.arc(mx + (x + .5) * sc, my + (y + .5) * sc, r, 0, 7); g.fill();
  }
  g.restore();

  // ---- caption
  const rules = info.rules.length ? info.rules.join(' · ') : 'no mortality rules';
  g.fillStyle = '#eef2ff'; g.font = '600 44px Georgia, serif'; g.textAlign = 'left'; g.textBaseline = 'alphabetic';
  g.fillText(info.title, mx, 70);
  g.font = '18px system-ui'; g.fillStyle = '#8a96b2'; g.fillText(`${d.gens} generations of footprints · ${info.map}`, mx, 96);
  const y0 = my + mapH + 60;
  g.font = '600 13px system-ui'; g.fillStyle = '#6ea8ff'; g.fillText('SETUP', mx, y0);
  g.font = '17px system-ui'; g.fillStyle = '#dbe3f5';
  info.lines.forEach((l, i) => g.fillText(l, mx, y0 + 28 + i * 25));
  g.fillStyle = '#9fb0d4'; wrap(g, 'Selection: ' + rules, mx, y0 + 28 + info.lines.length * 25 + 6, mw * .6, 24);

  // generation colour bar
  const bx = W - 80 - 330, by = y0 - 6;
  const lg = g.createLinearGradient(bx, 0, bx + 330, 0);
  for (let i = 0; i <= 10; i++) { const t = i / 10, hue = ((0.58 + 0.95 * t) % 1) * 360; lg.addColorStop(t, `hsl(${hue},85%,62%)`); }
  g.fillStyle = lg; g.beginPath(); g.roundRect(bx, by, 330, 10, 5); g.fill();
  g.font = '12px system-ui'; g.fillStyle = '#8a96b2'; g.textAlign = 'left'; g.fillText('first generation', bx, by + 30); g.textAlign = 'right'; g.fillText('last generation', bx + 330, by + 30);
  g.fillStyle = 'rgba(255,110,100,.9)'; g.beginPath(); g.arc(bx + 6, by + 56, 5, 0, 7); g.fill(); g.fillStyle = '#8a96b2'; g.textAlign = 'left'; g.fillText('where cells died', bx + 18, by + 60);

  // survival sparkline
  const sx = bx, sy = by + 86, sw = 330, sh = 60;
  g.fillStyle = '#6ea8ff'; g.font = '600 12px system-ui'; g.fillText('SURVIVAL RATE', sx, sy - 6);
  g.strokeStyle = 'rgba(255,255,255,.12)'; g.strokeRect(sx + .5, sy + .5, sw, sh);
  if (d.survival.length > 1) {
    g.beginPath(); d.survival.forEach((v, i) => { const x = sx + sw * i / (d.survival.length - 1), y = sy + sh - sh * v / 100; i ? g.lineTo(x, y) : g.moveTo(x, y); });
    g.strokeStyle = '#34d399'; g.lineWidth = 2; g.stroke();
  }
  g.textAlign = 'right'; g.fillStyle = '#5d6988'; g.font = '12px ui-monospace,monospace'; g.fillText('seed-print ' + info.print, W - 80, H - 28);
  g.textAlign = 'left'; g.fillText('evolution-sim', mx, H - 28);
}
function wrap(g, text, x, y, maxW, lh) {
  let line = '', yy = y;
  for (const w of text.split(' ')) { const t = line + w + ' '; if (g.measureText(t).width > maxW && line) { g.fillText(line, x, yy); line = w + ' '; yy += lh; } else line = t; }
  g.fillText(line, x, yy);
}

async function openArt() {
  const d = await api('art'); if (d.error) return;
  const sc = SCHEMA.scenarios.find(s => s.id === cfg.scenario);
  const shape = SCHEMA.shapes.find(s => s.id === map.shape)?.name || map.shape;
  const rules = SCHEMA.rules.filter(r => cfg.rules[r.id].enabled).map(r => {
    const p = r.params.filter(q => q.type === 'number' && cfg.rules[r.id][q.key]).map(q => cfg.rules[r.id][q.key]);
    return r.name + (p.length ? ` (${p.join('/')})` : '');
  });
  const mode = cfg.mode === 'sexual' ? `sexual, ${cfg.partners} partner${cfg.partners > 1 ? 's' : ''}, ${cfg.crossover} crossover` : 'asexual';
  const lines = [
    `${cfg.population} cells · ${cfg.steps} steps per generation · ${cfg.n_genes} genes · ${cfg.n_inner} inner neurons`,
    `mutation ${(cfg.mutation_rate * 100).toFixed(2)}% per digit · ${mode}`,
  ];
  const info = { title: sc && sc.id === cfg.scenario ? sc.name : 'Custom evolution', map: `${shape} ${map.w}×${map.h}`, rules, lines,
    print: hashStr(JSON.stringify([cfg, map.shape, map.zone, map.w, map.h])) };
  const cv = $('#art-canvas'); renderArt(cv, d, info);
  $('#art-modal').hidden = false;
  $('#art-dl').onclick = () => { const a = document.createElement('a'); a.download = `evolution-${info.print}.png`; a.href = cv.toDataURL('image/png'); a.click(); };
}
