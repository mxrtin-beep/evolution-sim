"""Genomes are (N, n_genes) uint32 arrays; each 32-bit gene wires one neural connection.

Gene layout (same as the original project):
    bit 31      source type  (0 = sensory neuron, 1 = inner neuron)
    bits 24-30  source id    (modulo number of candidate sources)
    bit 23      sink type    (0 = inner neuron, 1 = action neuron)
    bits 16-22  sink id      (modulo number of candidate sinks)
    bits 0-15   weight       (mapped to [-4, 4))
"""
import numpy as np

# (key, short label, full name, description)
SENSORS = [
    ("Age", "Age", "How far through the generation the cell is (0-1)."),
    ("Rnd", "Random", "Fresh random noise each step."),
    ("Blr", "Side blocked", "Whether the left / right neighbours are blocked (-1 free ... +1 both blocked)."),
    ("Osc", "Oscillator", "Square-wave clock; its period is tunable by actions."),
    ("Bfd", "Front blocked", "1 if the square in front is a wall, edge or another cell."),
    ("Pop", "Crowding", "Share of the 5x5 neighbourhood occupied by other cells."),
    ("LMx", "Heading X", "Horizontal component of the last movement."),
    ("LMy", "Heading Y", "Vertical component of the last movement."),
    ("Gen", "Kinship ahead", "Genetic similarity of the cell in front (-1 stranger ... +1 clone, 0 = nobody)."),
    ("Lx", "X position", "Horizontal position on the map (0-1)."),
    ("Ly", "Y position", "Vertical position on the map (0-1)."),
    ("BD", "Wall distance", "Distance to the nearest wall or map edge."),
    ("Bs", "Bias", "Always on."),
    ("Hz", "Hazard distance", "Distance to the nearest hazard pixel (1 = far or none)."),
    ("Sz", "Safe distance", "Distance to the nearest safe-zone pixel (0 = inside / none)."),
    ("Nn", "Nearest cell", "Distance to the closest other cell (1 = nobody within 6 px)."),
    ("Trv", "Distance walked", "Total distance travelled so far, relative to the generation length."),
    ("Sml", "Smell", "Pheromone concentration where the cell stands. It fades and spreads, so it works as a trail."),
    ("Hnd", "Hand nearby", "Your hand, seen through the webcam or mouse: 1 = under it, fading to 0 about 6 px away."),
]

ACTIONS = [
    ("R+", "More responsive", "Lower every neuron's firing threshold."),
    ("R-", "Less responsive", "Raise every neuron's firing threshold."),
    ("O+", "Slow oscillator", "Lengthen the oscillator's period."),
    ("O-", "Fast oscillator", "Shorten the oscillator's period."),
    ("Mfd", "Move forward", "Keep going in the current heading."),
    ("Mrn", "Move random", "Step in a random direction."),
    ("Mrv", "Move reverse", "Turn around."),
    ("Mrt", "Turn right", "Step to the right of the heading."),
    ("Mlt", "Turn left", "Step to the left of the heading."),
    ("MXf", "Move east", "Step +X."),
    ("MXr", "Move west", "Step -X."),
    ("MYf", "Move south", "Step +Y."),
    ("MYr", "Move north", "Step -Y."),
    ("Spr", "Spray pheromone", "Leave pheromone on the current square; every cell can smell it."),
]

N_SENSORS = len(SENSORS)
N_ACTIONS = len(ACTIONS)
SENSOR_IDX = {k: i for i, (k, _, _) in enumerate(SENSORS)}
ACTION_IDX = {k: i for i, (k, _, _) in enumerate(ACTIONS)}

U32 = np.uint32


def random_genomes(rng, n, n_genes):
    return rng.integers(0, 2 ** 32, size=(n, n_genes), dtype=np.uint64).astype(U32)


def mutate(rng, genomes, rate):
    """Replace each hex digit with a random one with probability `rate`."""
    if rate <= 0 or genomes.size == 0:
        return genomes
    out = genomes.copy()
    for k in range(8):
        mask = rng.random(out.shape) < rate
        if not mask.any():
            continue
        new = rng.integers(0, 16, size=out.shape).astype(U32)
        shift = U32(4 * k)
        cleared = out & ~(U32(0xF) << shift)
        out = np.where(mask, cleared | (new << shift), out).astype(U32)
    return out


def crossover(rng, parents, mode):
    """parents: (N, k, n_genes). Returns (N, n_genes) child genomes.

    mode 'gene': each whole gene comes from one random parent.
    mode 'nucleotide': each hex digit comes from a random parent.
    """
    n, k, g = parents.shape
    if k == 1:
        return parents[:, 0, :].copy()
    rows = np.arange(n)[:, None]
    cols = np.arange(g)[None, :]
    if mode == "nucleotide":
        child = np.zeros((n, g), U32)
        for d in range(8):
            pick = rng.integers(0, k, size=(n, g))
            digit = (parents[rows, pick, cols] >> U32(4 * d)) & U32(0xF)
            child |= digit << U32(4 * d)
        return child
    pick = rng.integers(0, k, size=(n, g))
    return parents[rows, pick, cols]


def _pick(options, ids):
    """options[ids % len(options)], or zeros if there are no options."""
    if len(options) == 0:
        return np.zeros_like(ids)
    return np.asarray(options)[ids % len(options)]


def decode(genomes, n_inner, enabled=None):
    """Decode genomes into weight tensors.

    Node numbering: sensors [0, S), inner [S, S+I), actions [S+I, S+I+A).
    `enabled` optionally switches neurons off: {"sensors": [bool]*S, "inner": [bool]*I, "actions": [bool]*A}.
    Genes are remapped onto the neurons that remain, so switching a neuron off wastes no genes.
    Returns (W, P): W[n, src, dst] summed signed weights, P[n, src, dst] bool presence.
    """
    n, g = genomes.shape
    S, I, A = N_SENSORS, n_inner, N_ACTIONS
    m = S + I + A
    src_t = ((genomes >> U32(31)) & U32(1)).astype(np.int64)
    src_id = ((genomes >> U32(24)) & U32(0x7F)).astype(np.int64)
    dst_t = ((genomes >> U32(23)) & U32(1)).astype(np.int64)
    dst_id = ((genomes >> U32(16)) & U32(0x7F)).astype(np.int64)
    weight = (genomes & U32(0xFFFF)).astype(np.float64)
    weight = (weight - 32768.0) / 8192.0

    en_s = np.flatnonzero(enabled["sensors"]) if enabled else np.arange(S)
    en_i = np.flatnonzero(enabled["inner"][:I]) if enabled else np.arange(I)
    en_a = np.flatnonzero(enabled["actions"]) if enabled else np.arange(A)
    W = np.zeros((n, m, m), np.float64)
    P = np.zeros((n, m, m), bool)
    if len(en_s) + len(en_i) == 0 or len(en_i) + len(en_a) == 0:
        return W, P                                  # nothing can be wired up
    src_t = np.where(len(en_i) == 0, 0, np.where(len(en_s) == 0, 1, src_t))
    dst_t = np.where(len(en_i) == 0, 1, np.where(len(en_a) == 0, 0, dst_t))
    src = np.where(src_t == 0, _pick(en_s, src_id), S + _pick(en_i, src_id))
    dst = np.where(dst_t == 0, S + _pick(en_i, dst_id), S + I + _pick(en_a, dst_id))
    rows = np.repeat(np.arange(n), g)
    np.add.at(W, (rows, src.ravel(), dst.ravel()), weight.ravel())
    P[rows, src.ravel(), dst.ravel()] = True
    return W, P


def functional_mask(P, n_inner):
    """Edges that can influence an action: driven by a sensor and leading to an action."""
    n, m, _ = P.shape
    S, I = N_SENSORS, n_inner
    Pf = P.astype(np.float32)
    driven = np.zeros((n, m), bool)
    driven[:, :S] = True
    for _ in range(I + 1):
        driven |= np.einsum("ni,nij->nj", driven.astype(np.float32), Pf) > 0
    useful = np.zeros((n, m), bool)
    useful[:, S + I:] = True
    for _ in range(I + 1):
        useful |= np.einsum("nij,nj->ni", Pf, useful.astype(np.float32)) > 0
    return P & driven[:, :, None] & useful[:, None, :]


def genome_colors(genomes):
    """A stable RGB colour per genome, taken from the top byte of its first three genes."""
    g = genomes.shape[1]
    cols = [(genomes[:, i % g] >> U32(24)).astype(np.int64) for i in range(3)]
    return cols[0] << 16 | cols[1] << 8 | cols[2]


def similarity(a, b):
    """Fraction of identical hex digits between two aligned genome arrays (n, g)."""
    x = a ^ b
    same = np.zeros(x.shape[0], np.int64)
    for k in range(8):
        same += (((x >> U32(4 * k)) & U32(0xF)) == 0).sum(axis=1)
    return same / (8.0 * x.shape[1])


def diversity(genomes):
    """Percent of gene slots holding a distinct gene value (original project's metric)."""
    if genomes.size == 0:
        return 0.0
    return 100.0 * len(np.unique(genomes)) / genomes.size


def percent_off_mode(genomes):
    """Percent of cells whose genome differs from the most common genome."""
    if len(genomes) == 0:
        return 0.0
    _, counts = np.unique(genomes, axis=0, return_counts=True)
    return 100.0 * (1 - counts.max() / len(genomes))
