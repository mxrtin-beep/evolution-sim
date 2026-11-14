"""Tiny dependency-free HTTP server: serves the web UI and a JSON API driving the simulation."""
import argparse
import base64
import json
import mimetypes
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np

from . import genome as gn
from . import rules as R
from . import world
from .scenarios import SCENARIOS
from .simulation import SETTINGS, Simulation, normalize_config

WEB = Path(__file__).resolve().parent.parent / "web"
MAX_SPEED = 2000  # slider value meaning "as fast as possible"


class Runner:
    """Owns the Simulation and a background thread that advances it."""

    def __init__(self):
        self.lock = threading.RLock()
        self.sim = None
        self.paused = False
        self.speed = 60.0
        self.generation = 0  # bumped on every (re)start so old threads exit
        self.terrain = None

    def start(self, cfg, terrain):
        with self.lock:
            self.generation += 1
            self.sim = Simulation(cfg, terrain)
            self.terrain = terrain
            self.paused = False
            gen_id = self.generation
        threading.Thread(target=self._loop, args=(gen_id,), daemon=True).start()

    def stop(self):
        with self.lock:
            self.generation += 1
            self.sim = None

    def _loop(self, gen_id):
        while True:
            with self.lock:
                if gen_id != self.generation or self.sim is None:
                    return
                sim = self.sim
                idle = self.paused or sim.status in ("extinct", "finished")
                if not idle:
                    sim.advance()
                speed = self.speed
            if idle:
                time.sleep(0.05)
            elif speed >= MAX_SPEED:
                time.sleep(0.0003)
            else:
                time.sleep(1.0 / max(speed, 1.0))


RUNNER = Runner()


def schema():
    return {
        "settings": [dict(zip(["key", "label", "group", "min", "max", "step", "default", "hint"], s)) for s in SETTINGS],
        "rules": R.RULES,
        "shapes": [{"id": k, "name": v[0]} for k, v in world.SHAPES.items()],
        "zones": [{"id": k, "name": v} for k, v in world.ZONES.items()],
        "spawns": [{"id": k, "name": v} for k, v in world.SPAWNS.items()],
        "scenarios": SCENARIOS,
        "sensors": [{"key": k, "name": n, "desc": d} for k, n, d in gn.SENSORS],
        "actions": [{"key": k, "name": n, "desc": d} for k, n, d in gn.ACTIONS],
        "max_speed": MAX_SPEED,
    }


def b64_terrain(t):
    return base64.b64encode(np.ascontiguousarray(t, np.uint8).tobytes()).decode()


class Handler(BaseHTTPRequestHandler):
    server_version = "EvoSim"

    def log_message(self, *a):  # quiet
        pass

    # ---- helpers
    def _json(self, obj, code=200):
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (WEB / rel).resolve()
        if WEB not in f.parents or not f.is_file():
            self.send_error(404)
            return
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/schema":
                return self._json(schema())
            if u.path == "/api/map":
                w = min(max(int(q.get("w", 128)), 16), 256)
                h = min(max(int(q.get("h", 128)), 16), 256)
                t = world.build_terrain(q.get("shape", "square"), q.get("zone", "none"), w, h)
                return self._json({"w": w, "h": h, "data": b64_terrain(t)})
            if u.path == "/api/frame":
                return self._frame(q.get("pher") == "1")
            if u.path == "/api/stats":
                return self._stats(int(q.get("since", 0)))
            if u.path == "/api/terrain":
                with RUNNER.lock:
                    sim = RUNNER.sim
                    return self._json({"data": b64_terrain(sim.terrain)} if sim else {"error": "no run"})
            if u.path == "/api/art":
                with RUNNER.lock:
                    return self._json(RUNNER.sim.art() if RUNNER.sim else {"error": "no run"})
            if u.path == "/api/brain":
                return self._brain(q)
            if u.path.startswith("/api/"):
                return self._json({"error": "unknown endpoint"}, 404)
            return self._static(u.path)
        except (ValueError, KeyError) as e:
            return self._json({"error": str(e)}, 400)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = self._body()
            if u.path == "/api/start":
                return self._start(body)
            if u.path == "/api/control":
                return self._control(body)
            if u.path == "/api/select":
                with RUNNER.lock:
                    sim = RUNNER.sim
                    i = sim.nearest_cell(float(body["x"]), float(body["y"])) if sim else None
                return self._json({"id": i})
            return self._json({"error": "unknown endpoint"}, 404)
        except (ValueError, KeyError, TypeError) as e:
            return self._json({"error": str(e)}, 400)

    def _start(self, body):
        w, h = int(body["w"]), int(body["h"])
        if not (16 <= w <= 256 and 16 <= h <= 256):
            raise ValueError("map size must be between 16 and 256")
        raw = base64.b64decode(body["terrain"])
        if len(raw) != w * h:
            raise ValueError("terrain size mismatch")
        terrain = np.clip(np.frombuffer(raw, np.uint8), 0, 3).reshape(w, h).copy()
        cfg = normalize_config(body.get("config"))
        if (terrain != world.WALL).sum() < 20:
            raise ValueError("the map has almost no open space")
        RUNNER.speed = float(body.get("speed", RUNNER.speed))
        RUNNER.start(cfg, terrain)
        return self._json({"ok": True, "n": RUNNER.sim.n, "requested": cfg["population"]})

    def _control(self, body):
        act = body.get("action")
        if act == "pause":
            RUNNER.paused = True
        elif act == "resume":
            RUNNER.paused = False
        elif act == "stop":
            RUNNER.stop()
        elif act == "speed":
            RUNNER.speed = min(max(float(body["value"]), 1), MAX_SPEED)
        return self._json({"ok": True})

    def _frame(self, pher=False):
        with RUNNER.lock:
            sim = RUNNER.sim
            if sim is None:
                return self._json({"active": False})
            f = sim.frame(pher)
            f.update(active=True, status=sim.status, paused=RUNNER.paused, speed=RUNNER.speed,
                     message=sim.message, n_stats=len(sim.stats), w=sim.w, h=sim.h)
            return self._json(f)

    def _stats(self, since):
        with RUNNER.lock:
            sim = RUNNER.sim
            if sim is None:
                return self._json({"stats": [], "total": 0})
            chunk = sim.stats[since:since + 150]
            return self._json({"stats": chunk, "total": len(sim.stats), "since": since})

    def _brain(self, q):
        with RUNNER.lock:
            sim = RUNNER.sim
            if sim is None:
                return self._json({"edges": []})
            if "cell" in q:
                b = sim.cell_brain(int(q["cell"]))
                return self._json(b or {"edges": [], "gone": True})
            g = int(q.get("gen", len(sim.brains) - 1))
            g = min(max(g, 0), len(sim.brains) - 1)
            return self._json({"gen": g, "gens": len(sim.brains), "edges": sim.brains[g], "n_inner": sim.n_inner})


def serve(host="127.0.0.1", port=8000, open_browser=True):
    server = None
    for p in range(port, port + 20):
        try:
            server = ThreadingHTTPServer((host, p), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit("Could not find a free port.")
    server.daemon_threads = True
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"Evolution Sim running at {url}  (Ctrl+C to quit)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        RUNNER.stop()
        server.server_close()


def main():
    ap = argparse.ArgumentParser(description="Evolution Sim web interface")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    serve(a.host, a.port, not a.no_browser)
