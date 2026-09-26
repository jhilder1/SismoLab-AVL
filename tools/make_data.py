"""
Regenerate the JSON test files in data/ (Sections 12 and 16).

Run from the project root:  python tools/make_data.py

Topology files are produced by operating a real Scenario and saving it, so
heights, balance factors and priorities are exact; the inconsistent files are
copies with one deliberate defect each.
"""

import copy
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from domain.models import Epicenter, Report, SeismicEvent, Zone, parse_time  # noqa: E402
from domain.scenario import Scenario  # noqa: E402
from domain.storage import FORMAT_INSERTIONS, write_json_file  # noqa: E402

INSERTIONS = os.path.join(ROOT, "data", "insertions")
TOPOLOGIES = os.path.join(ROOT, "data", "topologies")

CLOCK = "2026-09-12T00:00:00Z"

# Same geometry and stations as main.py.
ZONES = [
    {"name": "Norte", "x_min": 0, "x_max": 500, "y_min": 500, "y_max": 1000, "is_populated": True},
    {"name": "Centro", "x_min": 200, "x_max": 800, "y_min": 200, "y_max": 800, "is_populated": True},
    {"name": "Sur", "x_min": 0, "x_max": 500, "y_min": 0, "y_max": 500, "is_populated": False},
    {"name": "Costa", "x_min": 500, "x_max": 1000, "y_min": 0, "y_max": 500, "is_populated": True},
]
STATIONS = [
    {"station_id": "EST-001", "name": "Estacion Norte"},
    {"station_id": "EST-002", "name": "Estacion Centro"},
    {"station_id": "EST-003", "name": "Estacion Sur"},
    {"station_id": "EST-004", "name": "Estacion Costa"},
]


def event(event_id, magnitude, depth, x, y, time, station="EST-001"):
    return {"event_id": event_id, "magnitude": magnitude, "depth_km": depth,
            "epicenter": {"x": x, "y": y}, "occurrence_time": time,
            "station_id": station}


# 16 events covering the limit and tie cases of Section 16:
#   M = 4.5 and H = 30.0 in a populated zone -> P3; same data outside -> P2;
#   M = 6.0 -> P3 anywhere; an epicenter on the Sur/Costa border (x = 500,
#   Sur unpopulated, Costa populated) counts as populated;
#   equal priority and magnitude -> ordered by id.
EVENTS = [
    event(120, 4.5, 30.0, 300, 300, "2026-09-07T10:00:00Z"),            # P3 limit
    event(115, 4.5, 30.0, 100, 100, "2026-09-07T10:05:00Z", "EST-003"), # P2 outside
    event(130, 6.0, 300.0, 100, 150, "2026-09-07T10:10:00Z", "EST-003"),  # P3 by M
    event(118, 4.8, 20.0, 500, 100, "2026-09-07T10:15:00Z", "EST-004"),   # border -> P3
    event(140, 3.2, 12.0, 150, 120, "2026-09-07T11:00:00Z", "EST-003"),
    event(141, 3.2, 14.0, 160, 130, "2026-09-07T11:05:00Z", "EST-003"),   # tie with 140
    event(142, 3.2, 16.0, 170, 140, "2026-09-07T11:10:00Z", "EST-003"),   # tie with 140
    event(150, 5.6, 25.0, 600, 600, "2026-09-08T10:00:00Z", "EST-002"),
    event(151, 4.2, 25.0, 610, 605, "2026-09-08T10:20:00Z", "EST-002"),
    event(160, 2.1, 5.0, 50, 50, "2026-09-05T08:00:00Z", "EST-003"),      # old, low
    event(161, 1.8, 5.0, 60, 40, "2026-09-05T09:00:00Z", "EST-003"),      # old, low
    event(162, 2.4, 6.0, 70, 60, "2026-09-05T10:00:00Z", "EST-003"),      # old, low
    event(170, 4.8, 70.0, 700, 300, "2026-09-09T12:00:00Z", "EST-004"),   # P2
    event(180, 7.1, 10.0, 450, 700, "2026-09-10T06:00:00Z"),
    event(181, 0.5, 2.0, 900, 900, "2026-09-10T07:00:00Z", "EST-004"),
    event(182, -1.2, 1.0, 950, 950, "2026-09-10T08:00:00Z", "EST-004"),
]


def insertion_file(events, description):
    return {"format": FORMAT_INSERTIONS, "description": description,
            "clock": CLOCK, "zones": ZONES, "stations": STATIONS, "events": events}


def key_of(entry):
    zones = [Zone.from_dict(z) for z in ZONES]
    ev = SeismicEvent(entry["event_id"], entry["magnitude"], entry["depth_km"],
                      Epicenter(entry["epicenter"]["x"], entry["epicenter"]["y"]),
                      parse_time(entry["occurrence_time"]), entry["station_id"], zones)
    return ev.build_key().to_tuple()


def save(folder, name, data):
    os.makedirs(folder, exist_ok=True)
    write_json_file(os.path.join(folder, name), data)
    print("  ", os.path.relpath(os.path.join(folder, name), ROOT))


def node_of(data, event_id):
    return next(n for n in data["active_tree"]["nodes"] if n["event_id"] == event_id)


def main():
    print("Insertion files:")
    ascending = sorted(EVENTS, key=key_of)
    mixed = EVENTS[:]
    random.Random(16).shuffle(mixed)
    save(INSERTIONS, "ascendente.json", insertion_file(
        ascending, "Same events sorted by ascending key K: the BST degenerates into a list"))
    save(INSERTIONS, "mezclado.json", insertion_file(
        mixed, "Same events in a fixed mixed order"))
    repeated = mixed + [dict(mixed[3], magnitude=2.0)]
    save(INSERTIONS, "invalido-id-repetido.json", insertion_file(
        repeated, f"Id {mixed[3]['event_id']} appears twice: the whole file must be rejected"))

    print("Topology files:")
    # normal: balanced tree with history, deleted id, reviewed event and queue.
    sc = Scenario()
    sc.load_insertions_file(os.path.join(INSERTIONS, "mezclado.json"))
    sc.mark_reviewed(180)
    sc.correct_event(170, magnitude=6.2, depth_km=15.0)  # Section 16: P2 -> P3
    sc.delete_event(181)
    sc.archive_largest_eligible()                         # old low-priority branch
    sc.enqueue_report(Report(170, 1, "EST-002", 4.8, 70.0, Epicenter(700, 300),
                             parse_time("2026-09-09T12:00:00Z")))  # older revision
    sc.enqueue_report(Report(190, 1, "EST-001", 5.0, 10.0, Epicenter(250, 250),
                             parse_time("2026-09-11T09:00:00Z")))  # new event
    normal = sc.snapshot()
    save(TOPOLOGIES, "normal.json", normal)

    # stress: ascending insertions with rotations postponed (|bf| > 2).
    sc = Scenario()
    sc.load_insertions_file(os.path.join(INSERTIONS, "mezclado.json"))
    sc.toggle_stress()
    for i, magnitude in enumerate((7.2, 7.4, 7.6, 7.8, 8.0, 8.2), start=200):
        sc.create_event(i, magnitude, 10.0, 450, 650,
                        parse_time("2026-09-11T00:00:00Z"), "EST-001")
    stress = sc.snapshot()
    save(TOPOLOGIES, "estres.json", stress)

    unbalanced_normal = copy.deepcopy(stress)
    unbalanced_normal["mode"] = "normal"
    save(TOPOLOGIES, "desbalanceado-modo-normal.json", unbalanced_normal)

    # Wrong global order only: the leftmost node (smallest key) gets the largest
    # key, so it sits on the wrong side of every ancestor. Its stored key and
    # priority stay coherent with the new magnitude, so only the order fails.
    broken_order = copy.deepcopy(normal)
    node = node_of(broken_order, broken_order["active_tree"]["root"])
    while node["left"] is not None:
        node = node_of(broken_order, node["left"])
    node["event"]["magnitude"] = 9.9
    node["event"]["priority"] = 3
    node["key"] = [3, 9.9, node["event_id"]]
    del broken_order["bst"]  # rebuilt from the AVL, so only the order problem shows
    save(TOPOLOGIES, "inconsistente-orden.json", broken_order)

    # Wrong metadata: a height, a balance factor and a stored priority.
    broken_meta = copy.deepcopy(normal)
    root_id = broken_meta["active_tree"]["root"]
    node_of(broken_meta, root_id)["height"] += 2
    leaf = next(n for n in broken_meta["active_tree"]["nodes"]
                if n["left"] is None and n["right"] is None)
    leaf["balance_factor"] = 1
    other = next(n for n in broken_meta["active_tree"]["nodes"]
                 if n["event_id"] not in (root_id, leaf["event_id"]))
    other["event"]["priority"] = 1 if other["event"]["priority"] != 1 else 2
    other["key"][0] = other["event"]["priority"]
    save(TOPOLOGIES, "inconsistente-metadatos.json", broken_meta)

    # Invalid references: a link to a missing id and a node with two parents.
    broken_links = copy.deepcopy(normal)
    nodes = broken_links["active_tree"]["nodes"]
    leaves = [n for n in nodes if n["left"] is None and n["right"] is None]
    leaves[0]["left"] = 999999
    leaves[1]["right"] = broken_links["active_tree"]["root"]
    save(TOPOLOGIES, "invalido-referencias.json", broken_links)


if __name__ == "__main__":
    main()
