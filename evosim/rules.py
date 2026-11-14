"""Mortality rules. Each rule can kill cells during the generation, at its end, or both.

A cell dies as soon as *any* enabled rule says so; the first rule to claim it gets the blame
(that is what the "cause of death" colours / counters show).
"""
import numpy as np

WHEN = {"key": "when", "label": "Applies", "type": "select",
        "options": [["step", "Any time during the run"], ["end", "Only at end of generation"]],
        "default": "end"}


def _num(key, label, lo, hi, step, default, hint=""):
    return {"key": key, "label": label, "type": "number", "min": lo, "max": hi, "step": step,
            "default": default, "hint": hint}


RULES = [
    {"id": "hazard", "name": "Hazard pixels", "color": "#ff2d2d",
     "desc": "Cells die when they are within R pixels of a red hazard pixel.",
     "params": [_num("radius", "Kill distance R (px)", 0, 40, 1, 2), dict(WHEN, default="step")]},
    {"id": "safe", "name": "Safe zone", "color": "#00c34e",
     "desc": "At the end of the generation, cells that are further than R pixels from a green safe pixel die.",
     "params": [_num("radius", "Allowed distance R (px)", 0, 60, 1, 0)]},
    {"id": "walls", "name": "Wall / edge proximity", "color": "#ff9500",
     "desc": "Cells die if they are within R pixels of a wall or the map edge.",
     "params": [_num("radius", "Kill distance R (px)", 0, 40, 1, 3), WHEN]},
    {"id": "neighbors", "name": "Neighbours in range", "color": "#1f5bff",
     "desc": "Counts other cells within R pixels at the end of the generation. Too few (loners) "
             "or too many (overcrowding) means death.",
     "params": [_num("radius", "Radius R (px)", 1, 40, 1, 3),
                _num("min", "Minimum neighbours", 0, 50, 1, 1),
                _num("max", "Maximum neighbours (0 = no limit)", 0, 200, 1, 0)]},
    {"id": "travel", "name": "Distance travelled", "color": "#a63dff",
     "desc": "Total steps moved over the generation. Under the minimum = lazy; "
             "over the maximum = ran out of energy (dies the moment it exceeds it).",
     "params": [_num("min", "Minimum steps moved", 0, 2000, 1, 0),
                _num("max", "Energy budget: max steps moved (0 = no limit)", 0, 2000, 1, 0)]},
    {"id": "displacement", "name": "Net displacement", "color": "#00b8d9",
     "desc": "Straight-line distance between where the cell spawned and where it ends up.",
     "params": [_num("min", "Must end at least (px) from spawn", 0, 300, 1, 10),
                _num("max", "Must stay within (px) of spawn (0 = no limit)", 0, 300, 1, 0)]},
    {"id": "random", "name": "Random death", "color": "#ff2fa0",
     "desc": "Pure bad luck: every cell has the same chance of dying, regardless of its brain.",
     "params": [_num("chance", "Chance of dying (%)", 0, 100, 0.5, 10), dict(WHEN, default="end")]},
]
RULE_INDEX = {r["id"]: i for i, r in enumerate(RULES)}


def defaults():
    out = {}
    for r in RULES:
        out[r["id"]] = {"enabled": False, **{p["key"]: p["default"] for p in r["params"]}}
    return out


class RuleSet:
    """Evaluates the enabled rules against a simulation `ctx` (see Simulation)."""

    def __init__(self, cfg_rules, steps):
        self.steps = max(1, int(steps))
        base = defaults()
        self.active = []
        for r in RULES:
            c = {**base[r["id"]], **(cfg_rules or {}).get(r["id"], {})}
            if c.get("enabled"):
                self.active.append((r["id"], c))

    def _timing(self, rid, c):
        return c.get("when", "end")

    # --------------------------------------------------------------- per step
    def step(self, ctx, ia, rng):
        """Return list of (rule_index, subset_of_ia) deaths that happen right now."""
        out = []
        x, y = ctx.x[ia], ctx.y[ia]
        for rid, c in self.active:
            hit = None
            if rid == "hazard" and c["when"] == "step" and ctx.has_hazard:
                hit = ctx.d_hazard[x, y] <= float(c["radius"])
            elif rid == "walls" and c["when"] == "step":
                hit = ctx.d_wall[x, y] <= float(c["radius"])
            elif rid == "random" and c["when"] == "step":
                p = float(c["chance"]) / 100.0
                p_step = 1 - (1 - p) ** (1.0 / self.steps)
                hit = rng.random(len(ia)) < p_step
            elif rid == "travel" and float(c["max"]) > 0:
                hit = ctx.traveled[ia] > float(c["max"])
            if hit is not None and hit.any():
                out.append((RULE_INDEX[rid], ia[hit]))
        return out

    # ------------------------------------------------------------- end of gen
    def end(self, ctx, ia, rng):
        out = []
        x, y = ctx.x[ia], ctx.y[ia]
        for rid, c in self.active:
            hit = None
            if rid == "hazard" and c["when"] == "end" and ctx.has_hazard:
                hit = ctx.d_hazard[x, y] <= float(c["radius"])
            elif rid == "safe" and ctx.has_safe:
                hit = ctx.d_safe[x, y] > float(c["radius"])
            elif rid == "walls" and c["when"] == "end":
                hit = ctx.d_wall[x, y] <= float(c["radius"])
            elif rid == "neighbors":
                hit = self._neighbors(ctx, ia, c)
            elif rid == "travel" and float(c["min"]) > 0:
                hit = ctx.traveled[ia] < float(c["min"])
            elif rid == "displacement":
                d = np.hypot(x - ctx.sx[ia], y - ctx.sy[ia])
                hit = d < float(c["min"])
                if float(c["max"]) > 0:
                    hit |= d > float(c["max"])
            elif rid == "random" and c["when"] == "end":
                hit = rng.random(len(ia)) < float(c["chance"]) / 100.0
            if hit is not None and hit.any():
                out.append((RULE_INDEX[rid], ia[hit]))
        return out

    @staticmethod
    def _neighbors(ctx, ia, c):
        n = len(ia)
        if n == 0:
            return None
        x = ctx.x[ia].astype(np.float32)
        y = ctx.y[ia].astype(np.float32)
        r2 = float(c["radius"]) ** 2
        counts = np.zeros(n, np.int32)
        for s in range(0, n, 512):  # chunk to bound memory for big populations
            dx = x[s:s + 512, None] - x[None, :]
            dy = y[s:s + 512, None] - y[None, :]
            counts[s:s + 512] = ((dx * dx + dy * dy) <= r2).sum(axis=1) - 1  # minus self
        hit = counts < int(c["min"])
        if int(c["max"]) > 0:
            hit |= counts > int(c["max"])
        return hit
