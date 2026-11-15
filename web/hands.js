/* Hands as part of the world: a webcam (MediaPipe hand tracking) or the mouse paints a mask over the map,
   which is sent to the server so the "Hands" mortality rule and the "Hand nearby" sense can use it. */
const MP_VERSION = '0.10.14';
const MP_CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VERSION}`;
const MP_MODEL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

const WORK_W = 192;          // resolution used to find the real outline of the hand in the camera image
const Hands = {
  source: 'off', active: false, any: false, w: 0, h: 0, mask: null, canvas: null, ctx: null,
  video: null, stream: null, landmarker: null, timer: 0, lastSend: 0, lastHash: -1, cost: 20, calls: 0, sum: 0, onStatus: () => {},

  init(w, h) {
    this.w = w; this.h = h;
    this.canvas = document.createElement('canvas'); this.canvas.width = w; this.canvas.height = h;
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });
    this.mask = new Uint8Array(w * h);       // server layout: index = x * h + y
    this.work = document.createElement('canvas'); this.wctx = this.work.getContext('2d', { willReadFrequently: true });
    this.sk = document.createElement('canvas'); this.sctx = this.sk.getContext('2d', { willReadFrequently: true });
    this.mk = document.createElement('canvas'); this.mctx = this.mk.getContext('2d');
  },

  async setSource(src) {
    this.stop();
    this.source = src;
    if (src === 'off') return;
    if (src === 'mouse') { this.active = true; this.onStatus('Move the mouse over the map: it is a hand.'); return; }
    try {
      this.onStatus('Starting camera…');
      this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false });
      this.video = $('#cam'); this.video.srcObject = this.stream; await this.video.play(); this.video.hidden = false;
      this.onStatus('Loading hand-tracking model…');
      await this.loadLandmarker();
      this.active = true; this.calls = 0; this.sum = 0; this.onStatus('Show your hands to the camera.');
      this.loop();
    } catch (e) {
      console.error(e); this.stop(); this.source = 'off';
      this.onStatus('Webcam unavailable: ' + (e.message || e.name) + (this.landmarker === null && /import|fetch|load/i.test(String(e)) ? ' (the hand-tracking library loads from the internet)' : ''), true);
      throw e;
    }
  },

  async loadLandmarker() {
    if (this.landmarker) return;
    let base = MP_CDN, model = MP_MODEL;
    try { const r = await fetch('/vendor/mediapipe/vision_bundle.mjs', { method: 'HEAD' }); if (r.ok) { base = '/vendor/mediapipe'; model = '/vendor/mediapipe/hand_landmarker.task'; } } catch (e) {}
    const mod = await import(base + '/vision_bundle.mjs');
    const files = await mod.FilesetResolver.forVisionTasks(base + '/wasm');
    const make = delegate => mod.HandLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: model, delegate }, runningMode: 'VIDEO', numHands: 2 });
    this._make = make;
    try { this.landmarker = await make('GPU'); this.delegate = 'GPU'; }       // keeps the work off the main thread
    catch (e) { this.landmarker = await make('CPU'); this.delegate = 'CPU'; }
  },

  /* Track at a modest rate and never use more than ~half of the main thread, so the rest of the page stays smooth. */
  async loop() {
    if (this.source !== 'webcam') return;
    const v = this.video, t0 = performance.now();
    if (!document.hidden && v.readyState >= 2 && v.videoWidth && v.currentTime !== this.lastVT) {
      this.lastVT = v.currentTime;
      this.apply(this.landmarker.detectForVideo(v, t0), v, v.videoWidth / v.videoHeight, true);
      const dt = performance.now() - t0;
      this.calls++;
      if (this.calls === 1) this.cost = 40;                 // the first call includes model warm-up: ignore it
      else {
        this.cost = 0.8 * this.cost + 0.2 * dt; this.sum += dt;
        // some GPUs (or software rendering) are slower than the CPU: time two calls and fall back if so
        if (this.calls === 3 && this.delegate === 'GPU' && this.sum / 2 > 90) {
          try { this.landmarker.close(); this.landmarker = await this._make('CPU'); this.delegate = 'CPU'; this.cost = 40; this.calls = 0; this.sum = 0; }
          catch (e) { console.error('CPU fallback failed', e); }
        }
      }
    }
    if (this.source !== 'webcam') return;
    this.timer = setTimeout(() => this.loop(), Math.max(50, this.cost * 2));
  },

  /* Detected landmarks tell us where the hand is; the camera pixels tell us its true outline. */
  apply(res, src, aspect, mirror) {
    const hands = (res && res.landmarks) || [];
    const g = this.ctx, W = this.w, H = this.h;
    g.clearRect(0, 0, W, H);
    if (hands.length) {
      const ww = WORK_W, wh = Math.max(8, Math.round(WORK_W / aspect));
      for (const c of [this.work, this.sk, this.mk]) { if (c.width !== ww || c.height !== wh) { c.width = ww; c.height = wh; } }
      this.wctx.drawImage(src, 0, 0, ww, wh);
      let img = null;
      try { img = this.wctx.getImageData(0, 0, ww, wh); } catch (e) {}
      const out = new Uint8Array(ww * wh);
      for (const lm of hands) this.segment(img, ww, wh, lm, out);
      const md = this.mctx.createImageData(ww, wh);
      for (let i = 0; i < out.length; i++) if (out[i]) { md.data[i * 4] = 255; md.data[i * 4 + 1] = 106; md.data[i * 4 + 3] = 255; }
      this.mctx.putImageData(md, 0, 0);
      this._dbg = { out, ww, wh };
      // centre-crop to a square, optionally mirror, scale to the map
      const side = Math.min(ww, wh), cx = (ww - side) / 2, cy = (wh - side) / 2;
      g.save(); if (mirror) { g.translate(W, 0); g.scale(-1, 1); }
      g.imageSmoothingEnabled = true; g.drawImage(this.mk, cx, cy, side, side, 0, 0, W, H); g.restore();
    }
    this.commit();
  },

  /* Fill `out` with this hand's silhouette: skin-coloured pixels near the finger/palm skeleton. */
  segment(img, ww, wh, lm, out) {
    const pts = lm.map(p => [p.x * ww, p.y * wh]);
    const d = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    const scale = Math.max(d(pts[5], pts[17]), d(pts[0], pts[9]) * 0.6, 6);
    const chains = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]];
    const sk = this.sctx;
    const draw = (width, color) => {
      sk.strokeStyle = sk.fillStyle = color; sk.lineWidth = width; sk.lineJoin = sk.lineCap = 'round';
      sk.beginPath(); [0, 1, 5, 9, 13, 17].forEach((k, n) => n ? sk.lineTo(...pts[k]) : sk.moveTo(...pts[k])); sk.closePath(); sk.fill(); sk.stroke();
      for (const c of chains) { sk.beginPath(); c.forEach((k, n) => n ? sk.lineTo(...pts[k]) : sk.moveTo(...pts[k])); sk.stroke(); }
    };
    sk.clearRect(0, 0, ww, wh); sk.globalCompositeOperation = 'lighter';
    draw(scale * 0.62, '#f00');   // generous search area  (red channel)
    draw(scale * 0.24, '#0f0');   // thin core that is always part of the hand (green channel)
    sk.globalCompositeOperation = 'source-over';
    const skd = sk.getImageData(0, 0, ww, wh).data;

    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), pad = Math.ceil(scale * 0.7);
    const x0 = Math.max(0, Math.floor(Math.min(...xs)) - pad), x1 = Math.min(ww - 1, Math.ceil(Math.max(...xs)) + pad);
    const y0 = Math.max(0, Math.floor(Math.min(...ys)) - pad), y1 = Math.min(wh - 1, Math.ceil(Math.max(...ys)) + pad);

    // learn this person's skin colour from the palm
    let model = null;
    if (img) {
      const c = [0, 5, 9, 13, 17].reduce((a, k) => [a[0] + pts[k][0] / 5, a[1] + pts[k][1] / 5], [0, 0]);
      const spots = [c, ...[0, 5, 9, 13, 17].map(k => [(c[0] + pts[k][0]) / 2, (c[1] + pts[k][1]) / 2])];
      const r = Math.max(2, Math.round(scale * 0.07)), Y = [], Cr = [], Cb = [];
      for (const [sx, sy] of spots) for (let yy = Math.round(sy) - r; yy <= Math.round(sy) + r; yy++) for (let xx = Math.round(sx) - r; xx <= Math.round(sx) + r; xx++) {
        if (xx < 0 || yy < 0 || xx >= ww || yy >= wh) continue;
        const o = (yy * ww + xx) * 4, q = ycc(img.data[o], img.data[o + 1], img.data[o + 2]); Y.push(q[0]); Cr.push(q[1]); Cb.push(q[2]);
      }
      if (Y.length > 10) {
        const my = median(Y), mr = median(Cr), mb = median(Cb);
        model = { my, mr, mb, sy: Math.max(38, 3.2 * mad(Y, my)), sr: Math.max(7, 3 * mad(Cr, mr)), sb: Math.max(7, 3 * mad(Cb, mb)) };
      }
    }
    const bw = x1 - x0 + 1, bh = y1 - y0 + 1, loc = new Uint8Array(bw * bh);
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      const o = (y * ww + x) * 4;
      if (skd[o] < 90 && skd[o + 1] < 90) continue;
      let on = skd[o + 1] >= 90;            // core: always in
      if (!on && model) {
        const q = ycc(img.data[o], img.data[o + 1], img.data[o + 2]);
        const a = (q[1] - model.mr) / model.sr, b = (q[2] - model.mb) / model.sb, l = Math.abs(q[0] - model.my) / model.sy;
        on = a * a + b * b < 6.25 && l < 1;
      }
      if (on) loc[(y - y0) * bw + (x - x0)] = 1;
    }
    // close small gaps and drop speckle: 3x3 dilate, then erode
    const dil = morph(loc, bw, bh, true), ero = morph(dil, bw, bh, false);
    for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) if (ero[y * bw + x]) out[(y + y0) * ww + (x + x0)] = 1;
  },

  mouseAt(mx, my) {    // map coordinates, or null when the mouse leaves
    if (!this.active || this.source !== 'mouse') return;
    const g = this.ctx; g.clearRect(0, 0, this.w, this.h);
    if (mx != null) { g.fillStyle = '#ff6a00'; g.beginPath(); g.arc(mx, my, this.w * 0.07, 0, Math.PI * 2); g.fill(); }
    this.commit();
  },

  commit() {
    const d = this.ctx.getImageData(0, 0, this.w, this.h).data, m = this.mask, W = this.w, H = this.h;
    let any = false, hash = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const on = d[(y * W + x) * 4 + 3] > 110 ? 1 : 0; m[x * H + y] = on;
      if (on) { any = true; hash = (hash * 31 + x * H + y) | 0; }
    }
    this.any = any;
    const now = performance.now();
    if (hash !== this.lastHash && now - this.lastSend > 80) { this.send(); this.lastSend = now; this.lastHash = hash; }   // only when it changed
  },

  send() {
    fetch(`/api/hands_raw?w=${this.w}&h=${this.h}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: this.mask }).catch(() => {});
  },

  stop() {
    clearTimeout(this.timer);
    if (this.stream) this.stream.getTracks().forEach(t => t.stop());
    this.stream = null; this.active = false;
    const v = $('#cam'); if (v) { v.hidden = true; v.srcObject = null; }
    if (this.ctx) { this.ctx.clearRect(0, 0, this.w, this.h); this.commit(); }
  },
};

function ycc(r, g, b) { return [0.299 * r + 0.587 * g + 0.114 * b, 128 + 0.5 * r - 0.4187 * g - 0.0813 * b, 128 - 0.1687 * r - 0.3313 * g + 0.5 * b]; }
function median(a) { const s = a.slice().sort((x, y) => x - y); return s[s.length >> 1]; }
function mad(a, m) { return median(a.map(v => Math.abs(v - m))) * 1.4826; }
function morph(src, w, h, grow) {   // 3x3 dilate (grow) or erode
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let hit = grow ? 0 : 1;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const xx = x + dx, yy = y + dy, v = xx >= 0 && yy >= 0 && xx < w && yy < h ? src[yy * w + xx] : (grow ? 0 : 1);
      if (grow) hit |= v; else hit &= v;
    }
    out[y * w + x] = hit;
  }
  return out;
}
