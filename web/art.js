/* End-of-run artwork: the paths every cell walked, every generation overlaid, oldest first.
   Colour runs from the first generation (blue) to the last (orange). */
const ART_ANCHORS = [[31, 91, 255], [166, 61, 255], [255, 47, 160], [255, 45, 45], [255, 149, 0]];
function artColor(t) {
  const f = Math.min(Math.max(t, 0), 1) * (ART_ANCHORS.length - 1), i = Math.min(Math.floor(f), ART_ANCHORS.length - 2), k = f - i;
  return ART_ANCHORS[i].map((v, c) => Math.round(v + (ART_ANCHORS[i + 1][c] - v) * k));
}
function renderArt(canvas, d) {
  const W = 1600, sc = W / d.w, H = Math.round(d.h * sc);
  canvas.width = W; canvas.height = H;
  const g = canvas.getContext('2d');
  g.fillStyle = '#f1eee5'; g.fillRect(0, 0, W, H);
  // walls as pale pixels so the shape of the world is still readable
  const terr = Uint8Array.from(atob(d.terrain), c => c.charCodeAt(0));
  g.fillStyle = '#dedacc';
  for (let x = 0; x < d.w; x++) for (let y = 0; y < d.h; y++) if (terr[x * d.h + y] === 1) g.fillRect(Math.floor(x * sc), Math.floor(y * sc), Math.ceil(sc), Math.ceil(sc));

  const n = d.gens.length, alpha = Math.min(0.7, Math.max(0.06, 5 / n));
  g.lineWidth = Math.max(1.2, sc * 0.14); g.lineJoin = 'miter'; g.lineCap = 'square';
  d.gens.forEach((gen, gi) => {
    const bin = atob(gen.d), u = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    const a = new Int16Array(u.buffer), T = gen.t, K = gen.k;   // a[(t*K+k)*2 + {0,1}]
    const [r, gg, b] = artColor(n === 1 ? 0 : gi / (n - 1));
    g.strokeStyle = `rgba(${r},${gg},${b},${alpha})`;
    for (let k = 0; k < K; k++) {
      g.beginPath(); let pen = false;
      for (let t = 0; t < T; t++) {
        const x = a[(t * K + k) * 2], y = a[(t * K + k) * 2 + 1];
        if (x < 0) { pen = false; continue; }
        const px = (x + .5) * sc, py = (y + .5) * sc;
        pen ? g.lineTo(px, py) : g.moveTo(px, py); pen = true;
      }
      g.stroke();
    }
  });
}

async function openArt() {
  const d = await api('art'); if (d.error || !d.gens.length) return;
  const cv = $('#art-canvas'); renderArt(cv, d);
  $('#art-modal').hidden = false;
  $('#art-dl').onclick = () => { const a = document.createElement('a'); a.download = 'evolution-art.png'; a.href = cv.toDataURL('image/png'); a.click(); };
}
