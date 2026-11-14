import unittest

import numpy as np

from evosim import genome as gn
from evosim import world
from evosim.rules import RULES, defaults
from evosim.scenarios import SCENARIOS
from evosim.simulation import Simulation, normalize_config


def run(cfg, terrain, gens):
    sim = Simulation(normalize_config(cfg), terrain)
    done = 0
    while done < gens and sim.status in ("ready", "running"):
        done += sim.advance()
    return sim


class MapTests(unittest.TestCase):
    def test_all_shapes_and_zones_build_and_have_open_space(self):
        for shape in world.SHAPES:
            for zone in world.ZONES:
                t = world.build_terrain(shape, zone, 64, 48)
                self.assertEqual(t.shape, (64, 48))
                self.assertGreater((t != world.WALL).sum(), 100, shape)

    def test_distance_field(self):
        m = np.zeros((9, 9), bool)
        m[4, 4] = True
        d = world.distance_to(m)
        self.assertEqual(d[4, 4], 0)
        self.assertAlmostEqual(float(d[4, 8]), 4.0, places=4)


class GenomeTests(unittest.TestCase):
    def test_decode_and_functional(self):
        rng = np.random.default_rng(0)
        g = gn.random_genomes(rng, 50, 20)
        W, P = gn.decode(g, 4)
        F = gn.functional_mask(P, 4)
        self.assertTrue((F <= P).all())
        self.assertTrue(((W != 0) | ~P).all())

    def test_mutation_and_crossover(self):
        rng = np.random.default_rng(1)
        g = gn.random_genomes(rng, 30, 10)
        self.assertTrue((gn.mutate(rng, g, 0) == g).all())
        self.assertFalse((gn.mutate(rng, g, 0.5) == g).all())
        parents = np.stack([g[:10], g[10:20], g[20:30]], axis=1)
        for mode in ("gene", "nucleotide"):
            self.assertEqual(gn.crossover(rng, parents, mode).shape, (10, 10))


class SimulationTests(unittest.TestCase):
    def test_selection_pressure_evolves(self):
        cfg = {"seed": 4, "population": 200, "steps": 60, "rules": {"safe": {"enabled": True, "radius": 0}}}
        sim = run(cfg, world.build_terrain("square", "safe_right", 48, 48), 25)
        self.assertLess(np.mean([s["death_rate"] for s in sim.stats[-5:]]),
                        np.mean([s["death_rate"] for s in sim.stats[:3]]))

    def test_determinism(self):
        cfg = {"seed": 9, "population": 80, "steps": 30, "rules": {"random": {"enabled": True, "chance": 30}}}
        t = world.build_terrain("circle", "none", 40, 40)
        a, b = run(cfg, t, 3), run(cfg, t, 3)
        self.assertEqual([s["survivors"] for s in a.stats], [s["survivors"] for s in b.stats])

    def test_every_rule_and_scenario_runs(self):
        for r in RULES:
            rules = defaults()
            rules[r["id"]]["enabled"] = True
            t = world.build_terrain("square", "hazard_center", 40, 40)
            sim = run({"seed": 1, "population": 60, "steps": 20, "rules": rules}, t, 2)
            self.assertGreaterEqual(len(sim.stats), 1, r["id"])
        for s in SCENARIOS:
            t = world.build_terrain(s["shape"], s["zone"], 48, 48)
            sim = run({"seed": 1, "steps": 10, **s.get("settings", {}), "spawn": s["spawn"], "rules": s["rules"]}, t, 1)
            self.assertEqual(len(sim.stats), 1, s["id"])

    def test_reproduction_modes_keep_population(self):
        t = world.build_terrain("square", "none", 40, 40)
        for mode in ("asexual", "sexual"):
            sim = run({"seed": 2, "population": 70, "steps": 10, "mode": mode, "partners": 3,
                       "rules": {"random": {"enabled": True, "chance": 40}}}, t, 2)
            self.assertEqual(sim.n, 70)
            self.assertEqual(len(sim.G), 70)

    def test_extinction_stops(self):
        t = world.build_terrain("square", "none", 40, 40)
        sim = run({"seed": 2, "population": 30, "steps": 5, "rules": {"random": {"enabled": True, "chance": 100}}}, t, 3)
        self.assertEqual(sim.status, "extinct")

    def test_art_payload(self):
        t = world.build_terrain("square", "none", 32, 32)
        sim = run({"seed": 2, "population": 30, "steps": 5}, t, 1)
        self.assertEqual(sim.art()["w"], 32)


if __name__ == "__main__":
    unittest.main()
