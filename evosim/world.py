"""Maps (walls), selection zones (hazard / safe pixels) and distance fields.

Terrain codes stored in a (W, H) uint8 array indexed [x, y]:
    0 open, 1 wall, 2 hazard, 3 safe
"""
import numpy as np

OPEN, WALL, HAZARD, SAFE = 0, 1, 2, 3
FAR = 999.0


def _coords(w, h):
    """Normalised coordinates in [-1, 1] for every pixel, as (x, y) arrays of shape (w, h)."""
    x = np.linspace(-1, 1, w)[:, None] * np.ones((1, h))
    y = np.linspace(-1, 1, h)[None, :] * np.ones((w, 1))
    return x, y


# ---------------------------------------------------------------- map shapes
def _shape_square(w, h, rng):
    return np.zeros((w, h), bool)


def _shape_circle(w, h, rng):
    x, y = _coords(w, h)
    return x ** 2 + y ** 2 > 1


def _shape_ring(w, h, rng):
    x, y = _coords(w, h)
    r2 = x ** 2 + y ** 2
    return (r2 > 1) | (r2 < 0.3 ** 2)


def _shape_diamond(w, h, rng):
    x, y = _coords(w, h)
    return np.abs(x) + np.abs(y) > 1


def _shape_cross(w, h, rng):
    x, y = _coords(w, h)
    return (np.abs(x) > 0.33) & (np.abs(y) > 0.33)


def _shape_chambers(w, h, rng):
    """Two rooms joined by a narrow doorway."""
    x, y = _coords(w, h)
    wall = (np.abs(x) < 0.04) & (np.abs(y) > 0.14)
    return wall


def _shape_hourglass(w, h, rng):
    x, y = _coords(w, h)
    return np.abs(x) > (0.15 + 0.85 * np.abs(y))


def _shape_obstacles(w, h, rng):
    wall = np.zeros((w, h), bool)
    r = np.random.default_rng(7)  # fixed layout so the preview is stable
    for _ in range(max(4, w * h // 1400)):
        bw, bh = r.integers(3, max(4, w // 8)), r.integers(3, max(4, h // 8))
        bx, by = r.integers(0, w - bw), r.integers(0, h - bh)
        wall[bx:bx + bw, by:by + bh] = True
    return wall


def _shape_islands(w, h, rng):
    x, y = _coords(w, h)
    open_ = np.zeros((w, h), bool)
    for cx, cy, r in [(-0.5, -0.5, 0.38), (0.5, -0.45, 0.33), (0.0, 0.5, 0.42), (-0.62, 0.55, 0.2), (0.7, 0.45, 0.22)]:
        open_ |= (x - cx) ** 2 + (y - cy) ** 2 < r ** 2
    # land bridges
    open_ |= (np.abs(y + 0.48) < 0.05) & (np.abs(x) < 0.55)
    open_ |= (np.abs(x - 0.0) < 0.05) & (y > -0.3) & (y < 0.2)
    return ~open_


def _shape_spiral(w, h, rng):
    x, y = _coords(w, h)
    r = np.sqrt(x ** 2 + y ** 2)
    theta = np.arctan2(y, x)
    turns = 2.5
    phase = (r * turns - theta / (2 * np.pi)) % 1.0
    return ((phase > 0.62) | (r > 1)) & ~((r < 0.1))


SHAPES = {
    "square": ("Square", _shape_square),
    "circle": ("Circle", _shape_circle),
    "ring": ("Ring / donut", _shape_ring),
    "diamond": ("Diamond", _shape_diamond),
    "cross": ("Plus / cross", _shape_cross),
    "chambers": ("Two chambers + door", _shape_chambers),
    "hourglass": ("Hourglass", _shape_hourglass),
    "obstacles": ("Obstacle field", _shape_obstacles),
    "islands": ("Islands & bridges", _shape_islands),
    "spiral": ("Spiral", _shape_spiral),
}


# ---------------------------------------------------------- selection zones
def _zone(kind, w, h, rng):
    """Return (hazard_mask, safe_mask) for a named zone preset."""
    x, y = _coords(w, h)
    none = np.zeros((w, h), bool)
    hz, sf = none.copy(), none.copy()
    if kind == "safe_right":
        sf = x > 0.0
    elif kind == "safe_left":
        sf = x < 0.0
    elif kind == "safe_top":
        sf = y < -0.5
    elif kind == "safe_bottom":
        sf = y > 0.5
    elif kind == "safe_center":
        sf = x ** 2 + y ** 2 < 0.35 ** 2
    elif kind == "safe_corners":
        sf = (np.abs(x) > 0.7) & (np.abs(y) > 0.7)
    elif kind == "safe_edges":
        sf = (np.abs(x) > 0.8) | (np.abs(y) > 0.8)
    elif kind == "safe_corner":
        sf = (x > 0.5) & (y < -0.5)
    elif kind == "hazard_center":
        hz = x ** 2 + y ** 2 < 0.4 ** 2
    elif kind == "hazard_stripe":
        hz = np.abs(x) < 0.12
    elif kind == "hazard_diagonal":
        hz = np.abs(x - y) < 0.18
    elif kind == "hazard_edges":
        hz = (np.abs(x) > 0.94) | (np.abs(y) > 0.94)
    elif kind == "hazard_spots":
        r = np.random.default_rng(11)
        for _ in range(9):
            cx, cy = r.uniform(-0.8, 0.8, 2)
            hz |= (x - cx) ** 2 + (y - cy) ** 2 < r.uniform(0.08, 0.18) ** 2
    return hz, sf


ZONES = {
    "none": "None (no painted zones)",
    "safe_right": "Safe: right half",
    "safe_left": "Safe: left half",
    "safe_top": "Safe: top strip",
    "safe_bottom": "Safe: bottom strip",
    "safe_center": "Safe: center disc",
    "safe_corners": "Safe: four corners",
    "safe_corner": "Safe: top-right corner",
    "safe_edges": "Safe: edge band",
    "hazard_center": "Hazard: center disc",
    "hazard_stripe": "Hazard: vertical stripe",
    "hazard_diagonal": "Hazard: diagonal stripe",
    "hazard_edges": "Hazard: map edges",
    "hazard_spots": "Hazard: random spots",
}


def build_terrain(shape="square", zone="none", w=128, h=128):
    """Generate a terrain grid from a map shape and a zone preset."""
    w, h = int(w), int(h)
    rng = np.random.default_rng(0)
    wall = SHAPES.get(shape, SHAPES["square"])[1](w, h, rng)
    hz, sf = _zone(zone, w, h, rng)
    t = np.zeros((w, h), np.uint8)
    t[sf] = SAFE
    t[hz] = HAZARD
    t[wall] = WALL
    return t


# ------------------------------------------------------------ distance field
def distance_to(mask, edge_is_source=False):
    """Approximate Euclidean distance (chamfer 1 / sqrt2) from every pixel to the nearest True pixel.

    Returns float32 (w, h). Pixels where no source exists get FAR.
    """
    w, h = mask.shape
    if edge_is_source:
        pad = np.ones((w + 2, h + 2), bool)
        pad[1:-1, 1:-1] = mask
        return distance_to(pad)[1:-1, 1:-1]
    if not mask.any():
        return np.full((w, h), FAR, np.float32)
    d = np.where(mask, 0.0, FAR).astype(np.float64)
    s2 = 2 ** 0.5
    rows = d.tolist()
    for x in range(w):
        row = rows[x]
        prev = rows[x - 1] if x > 0 else None
        for y in range(h):
            v = row[y]
            if prev is not None:
                a = prev[y] + 1
                if a < v:
                    v = a
                if y > 0:
                    a = prev[y - 1] + s2
                    if a < v:
                        v = a
                if y < h - 1:
                    a = prev[y + 1] + s2
                    if a < v:
                        v = a
            if y > 0:
                a = row[y - 1] + 1
                if a < v:
                    v = a
            row[y] = v
    for x in range(w - 1, -1, -1):
        row = rows[x]
        nxt = rows[x + 1] if x < w - 1 else None
        for y in range(h - 1, -1, -1):
            v = row[y]
            if nxt is not None:
                a = nxt[y] + 1
                if a < v:
                    v = a
                if y > 0:
                    a = nxt[y - 1] + s2
                    if a < v:
                        v = a
                if y < h - 1:
                    a = nxt[y + 1] + s2
                    if a < v:
                        v = a
            if y < h - 1:
                a = row[y + 1] + 1
                if a < v:
                    v = a
            row[y] = v
    return np.array(rows, np.float32)


SPAWNS = {
    "anywhere": "Anywhere open",
    "center": "Center of the map",
    "left": "Left third",
    "bottom": "Bottom strip",
    "edges": "Along the edges",
}


def reachable_region(terrain):
    """Open cells (4-connected, the way cells actually move) that a cell could walk to a safe pixel from.

    If the map has safe pixels, that is every landmass containing one; otherwise the largest landmass.
    """
    from collections import deque
    w, h = terrain.shape
    open_ = (terrain != WALL).tolist()
    label = [[0] * h for _ in range(w)]
    sizes = [0]
    for sx in range(w):
        for sy in range(h):
            if open_[sx][sy] and not label[sx][sy]:
                n = len(sizes)
                label[sx][sy] = n
                size, q = 0, deque([(sx, sy)])
                while q:
                    x, y = q.popleft()
                    size += 1
                    for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= a < w and 0 <= b < h and open_[a][b] and not label[a][b]:
                            label[a][b] = n
                            q.append((a, b))
                sizes.append(size)
    lab = np.array(label)
    keep = set(lab[terrain == SAFE].tolist()) - {0}
    if not keep:
        keep = {int(np.argmax(sizes))}
    return np.isin(lab, list(keep))


def spawn_mask(kind, terrain):
    w, h = terrain.shape
    x, y = _coords(w, h)
    if kind == "center":
        m = x ** 2 + y ** 2 < 0.45 ** 2
    elif kind == "left":
        m = x < -0.33
    elif kind == "bottom":
        m = y > 0.5
    elif kind == "edges":
        m = (np.abs(x) > 0.75) | (np.abs(y) > 0.75)
    else:
        m = np.ones((w, h), bool)
    land = reachable_region(terrain) & (terrain != HAZARD)
    ok = m & land
    if ok.sum() < 20:  # preset collides with the map; fall back to anywhere reachable
        ok = land
    return ok
