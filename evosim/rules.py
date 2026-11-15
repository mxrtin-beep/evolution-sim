"""Mortality rules. Every cell lives through the whole generation; deaths are decided only at its end.

A cell dies if *any* enabled rule says so; the first rule to claim it gets the blame
(that is what the "cause of death" colours / counters show).
"""
import numpy as np


def _num(key, label, lo, hi, step, default, hint=""):
    return {"key": key, "label": label, "type": "number", "min": lo, "max": hi, "step": step,
            "default": default, "hint": hint}


RULES = [
    {"id": "hazard", "name": "Hazard pixels", "color": "#ff2d2d",
     "desc": "Cells within R pixels of a red hazard pixel die. Cells may spawn inside a hazard; "
             "they only die if they are still there when the generation ends.",
     "params": [_num("radius", "Kill distance R (px)", 0, 40, 1, 1)]},
    {"id": "safe", "name": "Safe zone", "color": "#00c34e",
     "desc": "Cells that are further than R pixels from a green safe pixel die.",
     "params": [_num("radius", "Allowed distance R (px)", 0, 60, 1, 0)]},
    {"id": "walls", "name": "Wall / edge proximity", "color": "#ff9500",
     "desc": "Cells within R pixels of a wall or the map edge die.",
     "params": [_num("radius", "Kill distance R (px)", 0, 40, 1, 3)]},
    {"id": "neighbors", "name": "Neighbours in range", "color": "#1f5bff",
     "desc": "Counts other cells within R pixels. Too few (loners) or too many (overcrowding) means death.",
     "params": [_num("radius", "Radius R (px)", 1, 40, 1, 3),
                _num("min", "Minimum neighbours", 0, 50, 1, 1),
                _num("max", "Maximum neighbours (0 = no limit)", 0, 200, 1, 0)]},
    {"id": "travel", "name": "Distance travelled", "color": "#a63dff",
     "desc": "Total steps moved over the generation. Under the minimum = lazy; "
             "over the maximum = burned too much energy.",
     "params": [_num("min", "Minimum steps moved", 0, 2000, 1, 0),
                _num("max", "Maximum steps moved (0 = no limit)", 0, 2000, 1, 0)]},
    {"id": "displacement", "name": "Net displacement", "color": "#00b8d9",
     "desc": "Straight-line distance between where the cell spawned and where it ends up.",
     "params": [_num("min", "Must end at least (px) from spawn", 0, 300, 1, 10),
                _num("max", "Must stay within (px) of spawn (0 = no limit)", 0, 300, 1, 0)]},
    {"id": "hands", "name": "Hands (webcam / mouse)", "color": "#ff6a00",
     "desc": "Your hands become part of the world. Cells either die if a hand covers them, or die unless "
             "a hand covers them. Switch on the webcam or mouse in the run screen; "
             "with no hand visible this rule pauses.",
     "params": [{"key": "mode", "label": "Cells die...", "type": "select",
                 "options": [["inside", "if under a hand"], ["outside", "unless under a hand"]],
                 "default": "inside"},
                _num("radius", "Hand reach R (px)", 0, 12, 1, 1)]},
    {"id": "random", "name": "Random death", "color": "#ff2fa0",
     "desc": "Pure bad luck: every cell has the same chance of dying, regardless of its brain.",
     "params": [_num("chance", "Chance of dying (%)", 0, 100, 0.5, 10)]},
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

    def end(self, ctx, ia, rng):
        """Return [(rule_index, cells_that_die)] for the cells `ia` still alive at the end of the generation."""
        out = []
        x, y = ctx.x[ia], ctx.y[ia]
        for rid, c in self.active:
            hit = None
            if rid == "hazard" and ctx.has_hazard:
                hit = ctx.d_hazard[x, y] <= float(c["radius"])
            elif rid == "safe" and ctx.has_safe:
                hit = ctx.d_safe[x, y] > float(c["radius"])
            elif rid == "walls":
                hit = ctx.d_wall[x, y] <= float(c["radius"])
            elif rid == "neighbors":
                hit = self._neighbors(ctx, ia, c)
            elif rid == "travel":
                hit = ctx.traveled[ia] < float(c["min"])
                if float(c["max"]) > 0:
                    hit |= ctx.traveled[ia] > float(c["max"])
            elif rid == "displacement":
                d = np.hypot(x - ctx.sx[ia], y - ctx.sy[ia])
                hit = d < float(c["min"])
                if float(c["max"]) > 0:
                    hit |= d > float(c["max"])
            elif rid == "hands" and ctx.hand_zone is not None:
                inside = ctx.hand_zone[x, y]
                hit = inside if c["mode"] == "inside" else ~inside
            elif rid == "random":
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
