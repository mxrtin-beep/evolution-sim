"""Ready-made selection scenarios shown in the setup screen."""
from . import rules as R


def _rules(**enabled):
    base = R.defaults()
    for rid, params in enabled.items():
        base[rid].update(params)
        base[rid]["enabled"] = True
    return base


SCENARIOS = [
    {"id": "right", "name": "Escape to the right",
     "desc": "Only cells that end the generation on the right half survive. Evolves fast, a good first run.",
     "shape": "square", "zone": "safe_right", "spawn": "anywhere",
     "rules": _rules(safe={"radius": 0})},
    {"id": "classic", "name": "Classic (original project)",
     "desc": "The original hard-coded rules: stay away from the edges and don't be a loner.",
     "shape": "square", "zone": "none", "spawn": "anywhere",
     "rules": _rules(walls={"radius": 3}, neighbors={"radius": 2, "min": 1, "max": 0})},
    {"id": "stripe", "name": "Mind the stripe",
     "desc": "A deadly vertical stripe splits the map. Anyone still in or next to it when the generation ends is gone.",
     "shape": "square", "zone": "hazard_stripe", "spawn": "anywhere",
     "rules": _rules(hazard={"radius": 1}, travel={"min": 30, "max": 0})},
    {"id": "island", "name": "Reach the far island",
     "desc": "Spawn on the left of an archipelago; only the top-right island is safe.",
     "shape": "islands", "zone": "safe_corner", "spawn": "left",
     "rules": _rules(safe={"radius": 4})},
    {"id": "course", "name": "Obstacle course",
     "desc": "Wander through a field of walls from the left to the safe right side.",
     "shape": "obstacles", "zone": "safe_right", "spawn": "left",
     "rules": _rules(safe={"radius": 0})},
    {"id": "social", "name": "Herd instinct",
     "desc": "Cells need 3-12 neighbours within 5 px. Lonely or overcrowded cells die.",
     "shape": "circle", "zone": "none", "spawn": "anywhere",
     "rules": _rules(neighbors={"radius": 5, "min": 3, "max": 12}, random={"chance": 5})},
    {"id": "distance", "name": "Social distancing",
     "desc": "A small, crowded map where anyone with more than 2 neighbours within 6 px dies. Cells must spread out.",
     "shape": "square", "zone": "none", "spawn": "anywhere", "size": [48, 48],
     "rules": _rules(neighbors={"radius": 6, "min": 0, "max": 2})},
    {"id": "fortress", "name": "Fortress",
     "desc": "Two chambers joined by a narrow doorway. Only the right chamber is safe, so cells born on the left must find the door.",
     "shape": "chambers", "zone": "safe_right", "spawn": "anywhere",
     "rules": _rules(safe={"radius": 0})},
    {"id": "marathon", "name": "Marathon",
     "desc": "Stay off the walls, travel at least 80 steps and end up 25 px from where you started.",
     "shape": "ring", "zone": "none", "spawn": "edges",
     "rules": _rules(walls={"radius": 2}, travel={"min": 80, "max": 0},
                     displacement={"min": 25, "max": 0})},
]
