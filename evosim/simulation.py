"""Vectorised evolution simulation."""
import numpy as np

from . import genome as gn
from . import world
from .rules import RULES, RuleSet

PATH_CELLS, PATH_SAMPLES, PATH_MAX_GENS = 100, 50, 160  # artwork recording limits
PAD = 6  # neighbourhood lookup radius (also the padding around the occupancy grid)

SETTINGS = [
    # key, label, group, min, max, step, default, hint
    ("population", "Population size", "Population", 10, 2000, 10, 100, "Cells alive at the start of every generation."),
    ("steps", "Generation length (steps)", "Population", 20, 1000, 10, 200, "How many steps the cells get to act before selection."),
    ("max_gens", "Generations to run (0 = forever)", "Population", 0, 10000, 10, 500, ""),
    ("n_genes", "Genes per genome", "Genetics", 1, 100, 1, 6, "Each gene wires one connection in the brain."),
    ("n_inner", "Inner neurons", "Genetics", 0, 16, 1, 2, "Hidden neurons available to the brain."),
    ("mutation_rate", "Mutation rate (per hex digit)", "Genetics", 0, 0.1, 0.0005, 0.005, "Chance that each of a gene's 8 hex digits is re-rolled in every child."),
    ("pher_decay", "Pheromone persistence", "World", 0.5, 0.99, 0.01, 0.9, "Share of pheromone left after each step. Higher = longer-lasting trails."),
]

DEFAULTS = {s[0]: s[6] for s in SETTINGS}
DEFAULTS.update({
    "mode": "asexual", "partners": 1, "crossover": "gene", "offspring": "equal",
    "spawn": "anywhere", "seed": None, "rules": {}, "hazard_shuffle": False,
    "disabled_sensors": [], "disabled_inner": [], "disabled_actions": [],
})
LIMITS = {s[0]: (s[3], s[4]) for s in SETTINGS}


def normalize_config(raw):
    cfg = dict(DEFAULTS)
    for k, (lo, hi) in LIMITS.items():
        if k in (raw or {}):
            try:
                v = float(raw[k])
            except (TypeError, ValueError):
                continue
            v = min(max(v, lo), hi)
            cfg[k] = v if isinstance(DEFAULTS[k], float) else int(v)
    r = raw or {}
    if r.get("mode") in ("sexual", "asexual"):
        cfg["mode"] = r["mode"]
    if r.get("crossover") in ("gene", "nucleotide"):
        cfg["crossover"] = r["crossover"]
    if r.get("offspring") in ("equal", "random"):
        cfg["offspring"] = r["offspring"]
    if r.get("spawn") in world.SPAWNS:
        cfg["spawn"] = r["spawn"]
    try:
        cfg["partners"] = min(max(int(r.get("partners", 1)), 1), 9)
    except (TypeError, ValueError):
        pass
    if r.get("seed") not in (None, ""):
        try:
            cfg["seed"] = int(r["seed"])
        except (TypeError, ValueError):
            pass
    cfg["rules"] = r.get("rules") or {}
    cfg["hazard_shuffle"] = bool(r.get("hazard_shuffle", False))
    cfg["disabled_sensors"] = [k for k in (r.get("disabled_sensors") or []) if k in gn.SENSOR_IDX]
    cfg["disabled_actions"] = [k for k in (r.get("disabled_actions") or []) if k in gn.ACTION_IDX]
    cfg["disabled_inner"] = sorted({int(i) for i in (r.get("disabled_inner") or []) if str(i).lstrip("-").isdigit()})
    return cfg


# neighbour offsets sorted by Chebyshev ring (1..PAD)
_oy, _ox = np.meshgrid(np.arange(-PAD, PAD + 1), np.arange(-PAD, PAD + 1))
_ox, _oy = _ox.ravel(), _oy.ravel()
_keep = (_ox != 0) | (_oy != 0)
OFF_X, OFF_Y = _ox[_keep], _oy[_keep]
OFF_RING = np.maximum(np.abs(OFF_X), np.abs(OFF_Y))
OFF_R2 = OFF_RING <= 2


class Simulation:
    def __init__(self, cfg, terrain):
        self.cfg = cfg
        self.terrain = terrain.astype(np.uint8)
        self.w, self.h = self.terrain.shape
        self.rng = np.random.default_rng(cfg["seed"])
        self.steps = cfg["steps"]
        self.n_inner = cfg["n_inner"]
        self.rules = RuleSet(cfg["rules"], self.steps)
        self.enabled = {
            "sensors": [k not in cfg["disabled_sensors"] for k, _, _ in gn.SENSORS],
            "inner": [i not in cfg["disabled_inner"] for i in range(self.n_inner)],
            "actions": [k not in cfg["disabled_actions"] for k, _, _ in gn.ACTIONS],
        }
        S_, I_ = gn.N_SENSORS, self.n_inner
        self.off_nodes = ([i for i, on in enumerate(self.enabled["sensors"]) if not on] +
                          [S_ + i for i, on in enumerate(self.enabled["inner"]) if not on] +
                          [S_ + I_ + i for i, on in enumerate(self.enabled["actions"]) if not on])

        # distance fields
        wall = self.terrain == world.WALL
        self.d_wall = world.distance_to(wall, edge_is_source=True)
        self.has_hazard = bool((self.terrain == world.HAZARD).any())
        self.has_safe = bool((self.terrain == world.SAFE).any())
        self.d_hazard = world.distance_to(self.terrain == world.HAZARD)
        self.d_safe = world.distance_to(self.terrain == world.SAFE)

        self.wall = wall
        self.hand = None            # raw hand mask from the webcam / mouse, (w, h) bool
        self.hand_zone = None       # hand mask grown by the rule's reach (None while no hand is visible)
        self.transition = {}
        self.transition_id = 0
        self.pher = np.zeros((self.w, self.h), np.float32)
        self.shuffle = bool(cfg["hazard_shuffle"]) and self.has_hazard
        self.tver = 0  # bumped whenever the hazard layout changes
        if self.shuffle:
            self.hazard0 = self.terrain == world.HAZARD
            self.terrain = np.where(self.hazard0, world.OPEN, self.terrain).astype(np.uint8)
        self.spawn_ok = world.spawn_mask(cfg["spawn"], self.terrain)
        self.spawn_cells = np.argwhere(self.spawn_ok)
        self.n = int(min(cfg["population"], len(self.spawn_cells)))
        if self.shuffle:
            self._shuffle_hazards()

        self.occp = np.zeros((self.w + 2 * PAD, self.h + 2 * PAD), np.int32)
        self.occp[...] = -1
        self.occp[PAD:-PAD, PAD:-PAD] = np.where(wall, -1, 0)

        # movement recording for the end-of-run artwork
        self.path_stride = 1
        self.paths = {}
        self.last_path = None
        self.gen = 0
        self.status = "ready"  # ready | running | extinct | finished
        self.stats = []
        self.brains = []
        self.message = ""
        self.G = gn.random_genomes(self.rng, self.n, cfg["n_genes"])
        self._begin_generation()

    # ------------------------------------------------------------- generation
    def _shuffle_hazards(self):
        """Slide the whole hazard pattern to a new random spot (wrapping round the map)."""
        shift = (int(self.rng.integers(0, self.w)), int(self.rng.integers(0, self.h)))
        mask = np.roll(self.hazard0, shift, axis=(0, 1)) & ~self.wall
        self.terrain = np.where(self.wall, world.WALL, np.where(mask, world.HAZARD, np.where(self.terrain == world.SAFE, world.SAFE, world.OPEN))).astype(np.uint8)
        self.d_hazard = world.distance_to(mask)
        self.tver += 1
        self.spawn_cells = np.argwhere(self.spawn_ok)   # cells may spawn inside hazards: they only die if they stay

    def _begin_generation(self):
        if self.shuffle and self.gen > 0:
            self._shuffle_hazards()
        n, G = self.n, self.G
        self.colors = gn.genome_colors(G)
        W, P = gn.decode(G, self.n_inner, self.enabled)
        F = gn.functional_mask(P, self.n_inner)
        self.W, self.F = W, F
        S, I = gn.N_SENSORS, self.n_inner
        self.Wsi = np.ascontiguousarray(W[:, :S, S:S + I])
        self.Wii = np.ascontiguousarray(W[:, S:S + I, S:S + I])
        self.Wsa = np.ascontiguousarray(W[:, :S, S + I:])
        self.Wia = np.ascontiguousarray(W[:, S:S + I, S + I:])
        self.brains.append(self._aggregate(F, W))

        # place cells
        self.occp[PAD:-PAD, PAD:-PAD] = np.where(self.terrain == world.WALL, -1, 0)
        pick = self.rng.choice(len(self.spawn_cells), size=n, replace=False)
        pos = self.spawn_cells[pick]
        self.x, self.y = pos[:, 0].astype(np.int32), pos[:, 1].astype(np.int32)
        self.sx, self.sy = self.x.copy(), self.y.copy()
        self.occp[self.x + PAD, self.y + PAD] = np.arange(1, n + 1)

        self.dx = self.rng.integers(-1, 2, n).astype(np.int32)
        self.dy = self.rng.integers(-1, 2, n).astype(np.int32)
        zero = (self.dx == 0) & (self.dy == 0)
        self.dx[zero] = 1
        self.alive = np.ones(n, bool)
        self.cause = np.full(n, -1, np.int32)
        self.traveled = np.zeros(n, np.int32)
        self.resp = np.zeros(n)
        self.osc_delay = np.full(n, 2, np.int32)
        self.inner = np.zeros((n, I))
        self.act = np.zeros((n, gn.N_ACTIONS))
        self.sens = np.zeros((n, gn.N_SENSORS))
        self.age = 0
        self.pher[:] = 0
        self.path_idx = self.rng.choice(n, size=min(n, PATH_CELLS), replace=False)
        self.path_every = max(1, self.steps // PATH_SAMPLES)
        self.path_buf = []
        self._record_path()
        self.death_log = []   # (x, y, cause) rows
        self.cause_counts = {}

    def _record_path(self):
        i = self.path_idx
        pos = np.stack([self.x[i], self.y[i]], axis=1).astype(np.int16)
        pos[~self.alive[i]] = -1
        self.path_buf.append(pos)

    def _store_path(self):
        arr = np.stack(self.path_buf)  # (T, k, 2)
        self.last_path = (self.gen, arr)
        if self.gen % self.path_stride == 0:
            self.paths[self.gen] = arr
        if len(self.paths) > PATH_MAX_GENS:
            self.path_stride *= 2
            self.paths = {g: a for g, a in self.paths.items() if g % self.path_stride == 0}

    def _aggregate(self, F, W):
        n = F.shape[0]
        cnt = F.sum(axis=0)
        wsum = (W * F).sum(axis=0)
        src, dst = np.nonzero(cnt)
        edges = [[int(s), int(d), round(float(cnt[s, d]) / n, 4), round(float(wsum[s, d] / cnt[s, d]), 3)]
                 for s, d in zip(src, dst)]
        edges.sort(key=lambda e: -e[2])
        return edges

    # ------------------------------------------------------------------- step
    def _sense(self, ia):
        x, y = self.x[ia], self.y[ia]
        dx, dy = self.dx[ia], self.dy[ia]
        n = len(ia)
        S = np.empty((n, gn.N_SENSORS))
        occp = self.occp
        K = gn.SENSOR_IDX
        S[:, K["Age"]] = self.age / self.steps
        S[:, K["Rnd"]] = self.rng.random(n)
        left = occp[x - dy + PAD, y + dx + PAD] != 0
        right = occp[x + dy + PAD, y - dx + PAD] != 0
        S[:, K["Blr"]] = left.astype(float) + right - 1.0
        S[:, K["Osc"]] = (self.age % self.osc_delay[ia] == 0)
        fx, fy = x + dx + PAD, y + dy + PAD
        S[:, K["Bfd"]] = occp[fx, fy] != 0
        hits = occp[x[:, None] + PAD + OFF_X[None, :], y[:, None] + PAD + OFF_Y[None, :]] > 0
        S[:, K["Pop"]] = hits[:, OFF_R2].sum(axis=1) / OFF_R2.sum()
        S[:, K["LMx"]], S[:, K["LMy"]] = dx, dy
        # kinship of the cell straight ahead
        other = occp[fx, fy] - 1
        kin = np.zeros(n)
        has = other >= 0
        if has.any():
            kin[has] = gn.similarity(self.G[ia[has]], self.G[other[has]]) * 2 - 1
        S[:, K["Gen"]] = kin
        S[:, K["Lx"]] = x / max(self.w - 1, 1)
        S[:, K["Ly"]] = y / max(self.h - 1, 1)
        S[:, K["BD"]] = np.clip(self.d_wall[x, y] / (min(self.w, self.h) / 2), 0, 1)
        S[:, K["Bs"]] = 1
        ring = np.where(hits, OFF_RING[None, :], PAD + 1).min(axis=1)
        S[:, K["Nn"]] = np.where(ring > PAD, 1.0, (ring - 1) / PAD)
        S[:, K["Trv"]] = np.clip(self.traveled[ia] / self.steps, 0, 1)
        S[:, K["Sml"]] = np.clip(self.pher[x, y] / 2.0, 0, 1)
        return S

    def set_hands(self, mask):
        """Update the hand mask (bool (w, h)); an empty mask means no hand is visible."""
        mask = np.asarray(mask, bool)
        if mask.shape != (self.w, self.h) or not mask.any():
            self.hand, self.hand_zone = None, None
            return
        self.hand = mask
        reach = 0
        for rid, c in self.rules.active:
            if rid == "hands":
                reach = int(c["radius"])
        zone = mask.copy()
        for _ in range(reach):
            q = np.pad(zone, 1)
            zone = (q[1:-1, 1:-1] | q[:-2, 1:-1] | q[2:, 1:-1] | q[1:-1, :-2] | q[1:-1, 2:] |
                    q[:-2, :-2] | q[:-2, 2:] | q[2:, :-2] | q[2:, 2:])
        self.hand_zone = zone

    def _think(self, ia, sens):
        inner_prev = self.inner[ia]
        if self.n_inner:
            pre = (sens[:, None, :] @ self.Wsi[ia])[:, 0, :] + (inner_prev[:, None, :] @ self.Wii[ia])[:, 0, :]
            inner = np.tanh(pre)
        else:
            inner = inner_prev
        act = np.tanh((sens[:, None, :] @ self.Wsa[ia])[:, 0, :] +
                      ((inner[:, None, :] @ self.Wia[ia])[:, 0, :] if self.n_inner else 0))
        self.inner[ia] = inner
        self.act[ia] = act
        self.sens[ia] = sens
        return act

    def _record_deaths(self, idx, rule_index):
        if len(idx) == 0:
            return
        idx = idx[self.alive[idx]]
        if len(idx) == 0:
            return
        self.alive[idx] = False
        self.cause[idx] = rule_index
        self.occp[self.x[idx] + PAD, self.y[idx] + PAD] = 0
        rid = RULES[rule_index]["id"]
        self.cause_counts[rid] = self.cause_counts.get(rid, 0) + len(idx)
        self.death_log.append(np.stack([self.x[idx], self.y[idx], np.full(len(idx), rule_index)], axis=1))

    def step(self):
        """Advance every living cell by one step."""
        ia = np.flatnonzero(self.alive)
        if len(ia):
            sens = self._sense(ia)
            act = self._think(ia, sens)
            fired = act > (0.5 * 0.75 ** self.resp[ia])[:, None]
            self._apply(ia, fired)
            self._diffuse_pheromone()
        self.age += 1
        if self.age % self.path_every == 0:
            self._record_path()

    def _diffuse_pheromone(self):
        p = self.pher
        if p.max() < 1e-3:
            p[:] = 0
            return
        q = np.pad(p, 1)
        near = (q[:-2, :-2] + q[:-2, 1:-1] + q[:-2, 2:] + q[1:-1, :-2] + q[1:-1, 2:] +
                q[2:, :-2] + q[2:, 1:-1] + q[2:, 2:]) / 8.0
        p[:] = np.minimum((0.7 * p + 0.3 * near) * self.cfg["pher_decay"], 5.0)
        p[self.wall] = 0

    def _apply(self, ia, f):
        a = gn.ACTION_IDX
        f = f.astype(np.int32)
        spray = ia[f[:, a["Spr"]] > 0]
        if len(spray):
            np.add.at(self.pher, (self.x[spray], self.y[spray]), 1.0)
        self.resp[ia] = np.clip(self.resp[ia] + f[:, a["R+"]] - f[:, a["R-"]], -3, 3)
        self.osc_delay[ia] = np.clip(self.osc_delay[ia] + f[:, a["O+"]] - f[:, a["O-"]], 2, 40)
        dx, dy = self.dx[ia], self.dy[ia]
        rx = self.rng.integers(-1, 2, len(ia))
        ry = self.rng.integers(-1, 2, len(ia))
        mx = (f[:, a["Mfd"]] * dx + f[:, a["Mrn"]] * rx - f[:, a["Mrv"]] * dx + f[:, a["Mrt"]] * dy
              - f[:, a["Mlt"]] * dy + f[:, a["MXf"]] - f[:, a["MXr"]])
        my = (f[:, a["Mfd"]] * dy + f[:, a["Mrn"]] * ry - f[:, a["Mrv"]] * dy - f[:, a["Mrt"]] * dx
              + f[:, a["Mlt"]] * dx + f[:, a["MYf"]] - f[:, a["MYr"]])
        mx, my = np.sign(mx), np.sign(my)
        movers = np.flatnonzero((mx != 0) | (my != 0))
        if len(movers) == 0:
            return
        movers = movers[self.rng.permutation(len(movers))]  # fair conflict resolution
        ids = ia[movers].tolist()
        mxl, myl = mx[movers].tolist(), my[movers].tolist()
        xs, ys = self.x[ids].tolist(), self.y[ids].tolist()
        occp = self.occp
        for k, i in enumerate(ids):
            cx, cy = xs[k], ys[k]
            ox, oy = cx, cy
            sx, sy = mxl[k], myl[k]
            if sx and occp[cx + sx + PAD, cy + PAD] == 0:
                occp[cx + PAD, cy + PAD] = 0
                cx += sx
                occp[cx + PAD, cy + PAD] = i + 1
            if sy and occp[cx + PAD, cy + sy + PAD] == 0:
                occp[cx + PAD, cy + PAD] = 0
                cy += sy
                occp[cx + PAD, cy + PAD] = i + 1
            if cx != ox or cy != oy:
                self.x[i], self.y[i] = cx, cy
                self.dx[i], self.dy[i] = (cx > ox) - (cx < ox), (cy > oy) - (cy < oy)
                self.traveled[i] += 1

    # --------------------------------------------------------- end of generation
    def end_generation(self):
        """Apply end-of-generation selection, record stats, breed the next generation."""
        n0 = self.n
        ia = np.flatnonzero(self.alive)
        self._store_path()
        claimed = set()
        for rule_index, idx in self.rules.end(self, ia, self.rng):
            idx = np.array([i for i in idx.tolist() if i not in claimed], dtype=np.int64)
            claimed.update(idx.tolist())
            self._record_deaths(idx, rule_index)
        survivors = np.flatnonzero(self.alive)
        deaths = (np.concatenate(self.death_log) if self.death_log else np.zeros((0, 3), np.int64))
        s = {
            "gen": self.gen, "pop": n0, "survivors": int(len(survivors)),
            "death_rate": round(100.0 * (n0 - len(survivors)) / n0, 2),
            "diversity": round(gn.diversity(self.G), 2),
            "causes": dict(self.cause_counts),
            "deaths": deaths.astype(int).ravel().tolist(),
        }
        self.stats.append(s)

        if len(survivors) == 0:
            self.status, self.message = "extinct", f"Everyone died in generation {self.gen + 1}."
            return s
        if self.cfg["max_gens"] and self.gen + 1 >= self.cfg["max_gens"]:
            self.status, self.message = "finished", f"Finished {self.gen + 1} generations."
            return s

        old = {"x": self.x[survivors].tolist(), "y": self.y[survivors].tolist(), "c": self.colors[survivors].tolist()}
        old_gen = self.gen
        self.G = self._breed(self.G[survivors])
        self.gen += 1
        self._begin_generation()
        self.transition = {
            "gen": old_gen, "survivors": old, "dead": s["deaths"],
            "children": {"x": self.x.tolist(), "y": self.y.tolist(), "c": self.colors.tolist(),
                         "p": self._pick.tolist()},   # indices into `survivors`
        }
        self.transition_id += 1
        return s

    def _breed(self, surv):
        cfg, rng = self.cfg, self.rng
        k = 1 if cfg["mode"] == "asexual" else 1 + cfg["partners"]
        s = len(surv)
        first = np.arange(self.n) % s if cfg["offspring"] == "equal" else rng.integers(0, s, self.n)
        if cfg["offspring"] == "equal":
            first = rng.permutation(first)
        pick = np.concatenate([first[:, None], rng.integers(0, s, (self.n, k - 1))], axis=1)
        self._pick = pick
        child = gn.crossover(rng, surv[pick], cfg["crossover"])
        return gn.mutate(rng, child, cfg["mutation_rate"])

    def advance(self):
        """One simulation step; closes the generation when its time is up. Returns True if a generation ended."""
        self.status = "running" if self.status == "ready" else self.status
        self.step()
        if self.age >= self.steps:
            self.end_generation()
            return True
        return False

    # -------------------------------------------------------------- snapshots
    def frame(self, pher=False):
        ia = np.flatnonzero(self.alive)
        out = {
            "gen": self.gen, "step": self.age, "steps": self.steps, "alive": int(len(ia)), "n": self.n, "tver": self.tver,
            "trid": self.transition_id, "hands": self.hand is not None,
            "x": self.x[ia].tolist(), "y": self.y[ia].tolist(), "c": self.colors[ia].tolist(),
        }
        if pher:
            import base64
            out["pher"] = base64.b64encode(np.clip(self.pher / 2.0 * 255, 0, 255).astype(np.uint8).tobytes()).decode()
        return out

    def art(self):
        """Recorded cell movement (sampled generations) for the end-of-run artwork."""
        import base64
        paths = dict(self.paths)
        if self.last_path is not None:
            paths[self.last_path[0]] = self.last_path[1]
        gens = sorted(paths)
        return {
            "w": self.w, "h": self.h, "total": len(self.stats), "status": self.status,
            "terrain": base64.b64encode(self.terrain.tobytes()).decode(),
            "gens": [{"g": g, "t": int(paths[g].shape[0]), "k": int(paths[g].shape[1]),
                      "d": base64.b64encode(paths[g].astype("<i2").tobytes()).decode()} for g in gens],
        }

    def nearest_cell(self, px, py):
        ia = np.flatnonzero(self.alive)
        if len(ia) == 0:
            return None
        d = (self.x[ia] - px) ** 2 + (self.y[ia] - py) ** 2
        j = int(np.argmin(d))
        return int(ia[j]) if d[j] <= 36 else None

    def cell_brain(self, i):
        if i is None or not (0 <= i < self.n):
            return None
        F, W = self.F[i], self.W[i]
        src, dst = np.nonzero(F)
        edges = [[int(s), int(d), 1.0, round(float(W[s, d]), 3)] for s, d in zip(src, dst)]
        S, I = gn.N_SENSORS, self.n_inner
        return {
            "edges": edges, "alive": bool(self.alive[i]), "x": int(self.x[i]), "y": int(self.y[i]),
            "color": int(self.colors[i]), "off": self.off_nodes,
            "activation": self.sens[i].tolist() + self.inner[i].tolist() + self.act[i].tolist(),
            "fired": (self.act[i] > 0.5 * 0.75 ** self.resp[i]).tolist(),
        }
