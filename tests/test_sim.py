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

    def test_pheromone_spray_and_smell(self):
        t = world.build_terrain("square", "none", 40, 40)
        sim = Simulation(normalize_config({"seed": 5, "population": 50, "steps": 20}), t)
        ia = np.flatnonzero(sim.alive)
        fired = np.zeros((len(ia), gn.N_ACTIONS), bool)
        fired[:, gn.ACTION_IDX["Spr"]] = True
        sim._apply(ia, fired)
        self.assertGreater(sim.pher.sum(), 0)
        smell = sim._sense(ia)[:, gn.SENSOR_IDX["Sml"]]
        self.assertTrue((smell > 0).all())
        sim.pher[:] = 0
        for _ in range(60):
            sim._diffuse_pheromone()
        self.assertEqual(float(sim.pher.max()), 0.0)
        self.assertIn("pher", sim.frame(pher=True))

    def test_spawn_only_on_land_connected_to_safe_zone(self):
        t = world.build_terrain("islands", "safe_corner", 128, 128)
        reach = world.reachable_region(t)
        self.assertLess(reach.sum(), (t != world.WALL).sum())      # some land is cut off
        self.assertTrue(reach[t == world.SAFE].all())
        sim = Simulation(normalize_config({"spawn": "left", "population": 200}), t)
        self.assertTrue(reach[sim.spawn_cells[:, 0], sim.spawn_cells[:, 1]].all())

    def test_moving_hazards_and_alarm_pheromone(self):
        t = world.build_terrain("square", "hazard_spots", 48, 48)
        rules = defaults()
        rules["hazard"].update(enabled=True, radius=1)
        sim = Simulation(normalize_config({"seed": 3, "steps": 10, "hazard_shuffle": True, "death_pher": 2, "rules": rules}), t)
        n_haz, v0, first = int((sim.terrain == world.HAZARD).sum()), sim.tver, sim.terrain.copy()
        while sim.gen < 2:
            sim.advance()
        self.assertGreater(sim.tver, v0)
        self.assertEqual(int((sim.terrain == world.HAZARD).sum()), n_haz)
        self.assertFalse((sim.terrain == first).all())

    def test_hands_rule(self):
        t = world.build_terrain("square", "none", 40, 40)
        rules = defaults()
        rules["hands"].update(enabled=True, mode="inside", radius=1, when="step")
        sim = Simulation(normalize_config({"seed": 3, "steps": 10, "population": 60, "rules": rules}), t)
        self.assertIsNone(sim.hand_zone)                                        # no hand yet
        mask = np.zeros((40, 40), bool)
        mask[:20, :] = True                                                    # left half is a hand
        sim.set_hands(mask)
        sim.advance()
        self.assertFalse((sim.alive & (sim.x < 19)).any())                       # cells under the hand died
        sim.set_hands(np.zeros((40, 40), bool))
        self.assertIsNone(sim.hand_zone)

    def test_outside_hand_rule_pauses_without_hand(self):
        t = world.build_terrain("square", "none", 40, 40)
        rules = defaults()
        rules["hands"].update(enabled=True, mode="outside", radius=0)
        sim = run({"seed": 3, "steps": 5, "population": 50, "rules": rules}, t, 1)
        self.assertEqual(sim.stats[0]["survivors"], 50)

    def test_transition_payload(self):
        t = world.build_terrain("square", "none", 40, 40)
        sim = run({"seed": 2, "steps": 6, "population": 40, "mode": "sexual", "partners": 2,
                   "rules": {"random": {"enabled": True, "chance": 50}}}, t, 1)
        tr = sim.transition
        self.assertEqual(len(tr["children"]["x"]), 40)
        self.assertEqual(len(tr["survivors"]["x"]), sim.stats[0]["survivors"])
        self.assertEqual(len(tr["children"]["p"][0]), 3)
        self.assertLess(max(max(p) for p in tr["children"]["p"]), len(tr["survivors"]["x"]))

    def test_disabled_neurons_are_never_wired(self):
        t = world.build_terrain("square", "safe_right", 40, 40)
        cfg = {"seed": 6, "steps": 10, "population": 60, "n_inner": 3, "n_genes": 12,
               "disabled_sensors": ["Rnd", "Lx"], "disabled_inner": [1], "disabled_actions": ["Mfd", "Mrn"],
               "rules": {"safe": {"enabled": True}}}
        sim = run(cfg, t, 2)
        off = set(sim.off_nodes)
        self.assertEqual(len(off), 5)
        for edges in sim.brains:
            for s, d, _, _ in edges:
                self.assertNotIn(s, off)
                self.assertNotIn(d, off)
        # genes are remapped, so disabling neurons still leaves the brains fully wired
        self.assertGreater(sum(len(e) for e in sim.brains), 0)

    def test_disabling_everything_is_safe(self):
        t = world.build_terrain("square", "none", 40, 40)
        cfg = {"seed": 1, "steps": 5, "population": 20, "n_inner": 2,
               "disabled_sensors": [k for k, _, _ in gn.SENSORS], "disabled_inner": [0, 1]}
        sim = run(cfg, t, 1)
        self.assertEqual(sum(len(e) for e in sim.brains), 0)

    def test_default_decode_unchanged_by_enabled_masks(self):
        rng = np.random.default_rng(0)
        g = gn.random_genomes(rng, 30, 10)
        W1, P1 = gn.decode(g, 4)
        on = {"sensors": [True] * gn.N_SENSORS, "inner": [True] * 4, "actions": [True] * gn.N_ACTIONS}
        W2, P2 = gn.decode(g, 4, on)
        self.assertTrue((P1 == P2).all() and np.allclose(W1, W2))

    def test_art_payload(self):
        t = world.build_terrain("square", "none", 32, 32)
        sim = run({"seed": 2, "population": 30, "steps": 5}, t, 1)
        art = sim.art()
        self.assertEqual(art["w"], 32)
        self.assertEqual(len(art["gens"]), 1)
        self.assertGreater(art["gens"][0]["t"], 1)


class HazardTimingTests(unittest.TestCase):
    def test_hazard_only_kills_at_end_and_spawning_inside_is_fine(self):
        t = world.build_terrain("square", "none", 40, 40)
        t[:20, :] = world.HAZARD                            # left half hazard
        rules = defaults()
        rules["hazard"].update(enabled=True, radius=0)
        sim = Simulation(normalize_config({"seed": 3, "steps": 20, "population": 80, "rules": rules}), t)
        self.assertTrue((sim.x < 20).any())                 # some cells spawn inside the hazard
        for _ in range(19):                                 # ...and survive while the generation runs
            sim.advance()
        self.assertEqual(int(sim.alive.sum()), 80)
        sim.advance()                                       # generation ends
        s = sim.stats[0]
        self.assertGreater(s["causes"].get("hazard", 0), 0)
        self.assertEqual(s["survivors"], 80 - s["causes"]["hazard"])

    def test_removed_senses_are_gone(self):
        keys = {k for k, _, _ in gn.SENSORS}
        self.assertFalse(keys & {"Hz", "Sz", "Hnd"})


if __name__ == "__main__":
    unittest.main()
