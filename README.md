# 🧬 Evolution Sim

A from-scratch artificial-life simulator: hundreds of cells, each controlled by its own tiny neural network encoded in a genome of hex genes, live, move and reproduce on a 2D map. No backprop, no labels: behaviour emerges purely from **selection pressure** and **random mutation**. Inspired by [David Miller's "I programmed some creatures. They evolved."](https://www.youtube.com/watch?v=N3tRFayqVtk)

<p align="center"><img src="docs/run.png" alt="Evolution Sim running" width="100%"></p>

## Run it

```bash
pip install -r requirements.txt   # just numpy
python main.py                    # opens http://localhost:8000
```

Options: `--port 8080`, `--host 0.0.0.0`, `--no-browser`. Run the tests with `python -m unittest discover -s tests`.

## The interface

**1. Setup** (before the run)

<p align="center"><img src="docs/setup.png" alt="Setup screen" width="80%"></p>

- **Scenarios**: one-click presets (Escape to the right, Classic original rules, Mind the stripe, Herd instinct, ...).
- **Population & time**: population size, generation length (steps), number of generations, seed.
- **Genetics**: genes per genome, inner neurons, mutation rate.
- **Reproduction** (asexual by default): asexual (clones) or sexual with 1-9 partners per child; gene-level or digit-level crossover; equal or random breeding.
- **World**: 10 map shapes (square, circle, ring, diamond, cross, two chambers, hourglass, obstacle field, islands, spiral), any size, a spawn area, and zone presets. Paint your own walls / hazards / safe zones on the preview.
- **Mortality conditions** (combine any): hazard pixels within R px, safe zone, wall/edge proximity, neighbours in range (too few *or* too many), distance travelled (laziness / energy budget), net displacement from spawn, and random death. A cell dies as soon as any enabled rule says so.

**2. During the run**

- **Live world**, one pixel per cell in its own genome colour, with a speed slider (up to "max"), pause (`Space`), and click-a-cell to inspect it.
- **Death spots** toggle: translucent dots where cells died (all generations / last 10 / last one), optionally coloured by cause of death.
- **Live charts** of death rate (% dying per generation) and genetic diversity, with hover read-outs. *Distinct genes* is the % of gene slots in the population holding a unique value; *genomes unlike the most common one* is the % of cells whose genome differs from the most common genome.
- **Brain evolution**: one brain drawn for the whole population. Every connection's opacity is the share of cells carrying it, so common wiring is solid and rare wiring fades; blue excites, red inhibits. Scrub or replay through the generations to watch the brain evolve, or select a single cell to see its own brain with live neuron activations.

**3. The final artwork**

When a run ends (or any time via *Final art*) you get a downloadable PNG with nothing but the artwork: the paths walked by a sample of cells in every generation, drawn oldest first from blue (first generation) to orange (last). Random wandering in early generations gives way to the straight, purposeful lines of an evolved strategy.

<p align="center"><img src="docs/art.png" alt="Generated artwork" width="60%"></p>

## How it works

| File | Role |
|---|---|
| `evosim/genome.py` | Genes are 32-bit ints: source (sensor/inner), sink (inner/action), signed weight. Decoding, mutation, crossover, pruning of non-functional connections. |
| `evosim/simulation.py` | Vectorised numpy simulation: sense → think (batched tanh network) → act → selection → breeding. |
| `evosim/rules.py` | The mortality rules (data-driven; the UI is generated from this list). |
| `evosim/world.py` | Map shapes, zone presets, distance fields. |
| `evosim/scenarios.py` | Preset scenarios. |
| `evosim/server.py` | Dependency-free HTTP server and JSON API. |
| `web/` | The interface (plain JS and canvas, no build step). |

Each cell senses 17 things (age, noise, blockage, crowding, kinship, position, wall / hazard / safe-zone distance, nearest neighbour, distance walked, ...) and chooses among 13 actions (move in 9 ways, tune its own responsiveness and oscillator).

### Changes from the original version
- pygame/matplotlib/networkx replaced by the browser interface; only `numpy` is required.
- Brain weights are now signed (the original only produced positive weights, so cells could never inhibit anything).
- Simulation is vectorised across the population (roughly 20x faster).
- Pixel-style flat interface (Helvetica, off-white, no gradients or shadows) instead of pygame windows.
- The hard-coded selection in `Environment.enact_selection_pressure()` is now configurable rules.
