/* Hands as part of the world: a webcam (MediaPipe hand tracking) or the mouse paints a mask over the map,
   which is sent to the server so the "Hands" mortality rule and the "Hand nearby" sense can use it. */
const MP_VERSION = '0.10.14';
const MP_CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VERSION}`;
const MP_MODEL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

const Hands = {
  source: 'off', active: false, w: 0, h: 0, mask: null, canvas: null, ctx: null,
  video: null, stream: null, landmarker: null, raf: 0, lastSend: 0, lastNonEmpty: false, onStatus: () => {},

  init(w, h) {
    this.w = w; this.h = h;
    this.canvas = document.createElement('canvas'); this.canvas.width = w; this.canvas.height = h;
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });
    this.mask = new Uint8Array(w * h);
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
      this.active = true; this.onStatus('Show your hands to the camera.');
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
    this.landmarker = await mod.HandLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: model }, runningMode: 'VIDEO', numHands: 2 });
  },

  loop() {
    if (this.source !== 'webcam') return;
    const v = this.video;
    if (v.readyState >= 2 && v.videoWidth) {
      const res = this.landmarker.detectForVideo(v, performance.now());
      this.apply(res, v.videoWidth / v.videoHeight, true);
    }
    this.raf = requestAnimationFrame(() => this.loop());
  },

  /* Turn detected landmarks into a filled silhouette. The camera view is centre-cropped to a square and mirrored. */
  apply(res, aspect, mirror) {
    const g = this.ctx, W = this.w, H = this.h;
    g.clearRect(0, 0, W, H);
    const lw = Math.max(2, W * 0.03);
    g.fillStyle = g.strokeStyle = '#ff6a00'; g.lineWidth = lw; g.lineJoin = g.lineCap = 'round';
    const hands = (res && res.landmarks) || [];
    for (const lm of hands) {
      const pts = lm.map(p => {
        let sx = (p.x - 0.5) * Math.max(aspect, 1) + 0.5, sy = (p.y - 0.5) * Math.max(1 / aspect, 1) + 0.5;
        if (mirror) sx = 1 - sx;
        return [sx * W, sy * H];
      });
      // palm as a polygon, each finger as a thick stroked chain of bones
      g.beginPath(); [0, 1, 5, 9, 13, 17].forEach((k, n) => n ? g.lineTo(...pts[k]) : g.moveTo(...pts[k])); g.closePath(); g.fill(); g.stroke();
      for (const chain of [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]]) {
        g.beginPath(); chain.forEach((k, n) => n ? g.lineTo(...pts[k]) : g.moveTo(...pts[k])); g.stroke();
      }
    }
    this.commit();
  },

  mouseAt(mx, my) {    // map coordinates, or null when the mouse leaves
    if (!this.active || this.source !== 'mouse') return;
    const g = this.ctx; g.clearRect(0, 0, this.w, this.h);
    if (mx != null) { g.fillStyle = '#ff6a00'; g.beginPath(); g.arc(mx, my, this.w * 0.07, 0, Math.PI * 2); g.fill(); }
    this.commit();
  },

  commit() {
    const d = this.ctx.getImageData(0, 0, this.w, this.h).data, m = this.mask; let any = false;
    for (let i = 0, n = this.w * this.h; i < n; i++) { const on = d[i * 4 + 3] > 110 ? 1 : 0; m[i] = on; if (on) any = true; }
    this.any = any;
    const now = performance.now();
    if ((any || this.lastNonEmpty) && now - this.lastSend > 90) { this.send(); this.lastSend = now; this.lastNonEmpty = any; }
  },

  send() {
    // server layout is index = x * h + y, our mask is row-major (y * w + x)
    const out = new Uint8Array(this.w * this.h);
    for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) out[x * this.h + y] = this.mask[y * this.w + x];
    api('hands', { w: this.w, h: this.h, data: b64(out) }).catch(() => {});
  },

  stop() {
    cancelAnimationFrame(this.raf);
    if (this.stream) this.stream.getTracks().forEach(t => t.stop());
    this.stream = null; this.active = false;
    const v = $('#cam'); if (v) { v.hidden = true; v.srcObject = null; }
    if (this.ctx) { this.ctx.clearRect(0, 0, this.w, this.h); this.mask.fill(0); this.any = false; if (this.lastNonEmpty) { this.send(); this.lastNonEmpty = false; } }
  },
};
