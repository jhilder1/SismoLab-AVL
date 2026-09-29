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

DATA_DIR = os.path.join(ROOT, "data")

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


def save(folder, name, data, verbose=True):
    os.makedirs(folder, exist_ok=True)
    write_json_file(os.path.join(folder, name), data)
    if verbose:
        print("  ", os.path.join(os.path.basename(folder), name))


def node_of(data, event_id):
    return next(n for n in data["active_tree"]["nodes"] if n["event_id"] == event_id)


def main(out_dir=DATA_DIR, verbose=True):
    """Write every test file under out_dir (tests regenerate into a temp folder
    and compare byte by byte with data/ to prove the files are reproducible)."""
    INSERTIONS = os.path.join(out_dir, "insertions")
    TOPOLOGIES = os.path.join(out_dir, "topologies")

    def put(folder, name, data):
        save(folder, name, data, verbose)

    if verbose:
        print("Insertion files:")
    ascending = sorted(EVENTS, key=key_of)
    mixed = EVENTS[:]
    random.Random(16).shuffle(mixed)
    put(INSERTIONS, "ascendente.json", insertion_file(
        ascending, "Same events sorted by ascending key K: the BST degenerates into a list"))
    put(INSERTIONS, "mezclado.json", insertion_file(
        mixed, "Same events in a fixed mixed order"))
    repeated = mixed + [dict(mixed[3], magnitude=2.0)]
    put(INSERTIONS, "invalido-id-repetido.json", insertion_file(
        repeated, f"Id {mixed[3]['event_id']} appears twice: the whole file must be rejected"))

    if verbose:
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
    put(TOPOLOGIES, "normal.json", normal)

    # prueba_carga: 20 real events for manual/demo testing (Sections 11-12).
    sc = Scenario()
    demo_events = [
        event(1001, 7.2, 15.0, 350.0, 620.0, "2026-06-01T08:15:00Z", "EST-001"),
        event(1002, 6.5, 25.0, 480.0, 590.0, "2026-06-02T14:30:00Z", "EST-002"),
        event(1003, 4.8, 22.0, 400.0, 550.0, "2026-06-03T09:00:00Z", "EST-001"),
        event(1004, 3.2,  8.0, 150.0, 200.0, "2026-06-04T11:45:00Z", "EST-003"),
        event(1005, 5.5, 28.0, 720.0, 180.0, "2026-06-05T16:20:00Z", "EST-004"),
        event(1006, 6.9, 10.0, 600.0, 300.0, "2026-06-06T07:00:00Z", "EST-004"),
        event(1007, 4.1, 50.0, 250.0, 750.0, "2026-06-07T12:10:00Z", "EST-001"),
        event(1008, 3.8, 35.0, 800.0, 450.0, "2026-06-08T18:55:00Z", "EST-004"),
        event(1009, 5.9, 18.0, 510.0, 510.0, "2026-06-09T03:40:00Z", "EST-002"),
        event(1010, 7.8,  5.0, 300.0, 700.0, "2026-06-10T21:00:00Z", "EST-001"),
        event(1011, 4.5, 30.0, 680.0, 250.0, "2026-06-11T10:30:00Z", "EST-004"),
        event(1012, 2.9, 12.0, 100.0, 400.0, "2026-06-12T06:15:00Z", "EST-003"),
        event(1013, 6.2, 42.0, 450.0, 450.0, "2026-06-13T14:00:00Z", "EST-002"),
        event(1014, 5.1, 20.0, 560.0, 640.0, "2026-06-14T09:45:00Z", "EST-001"),
        event(1015, 3.5, 65.0, 200.0, 100.0, "2026-06-15T22:30:00Z", "EST-003"),
        event(1016, 4.6, 27.0, 390.0, 580.0, "2026-06-16T11:00:00Z", "EST-002"),
        event(1017, 8.1,  8.0, 330.0, 660.0, "2026-06-17T04:20:00Z", "EST-001"),
        event(1018, 3.0, 90.0, 900.0, 100.0, "2026-06-18T17:10:00Z", "EST-004"),
        event(1019, 5.7, 33.0, 470.0, 470.0, "2026-06-19T08:00:00Z", "EST-002"),
        event(1020, 4.3, 16.0, 620.0, 380.0, "2026-06-20T13:50:00Z", "EST-004"),
    ]
    demo_clock = "2026-06-30T23:59:00Z"
    demo_params = {"W_hours": 48.0, "R_km": 40.0, "L_depth": 3, "T_archive_hours": 72.0}
    put(INSERTIONS, "prueba_carga_inserciones.json", {
        "format": FORMAT_INSERTIONS,
        "description": "20 eventos de prueba con variedad de magnitudes, prioridades y zonas",
        "clock": demo_clock,
        "zones": ZONES,
        "stations": STATIONS,
        "parameters": demo_params,
        "events": demo_events,
    })
    # Topology: same 20 events loaded through the live AVL, then snapshot.
    sc.zones = [Zone.from_dict(z) for z in ZONES]
    from domain.models import Station as _Station
    sc.stations = {s["station_id"]: _Station.from_dict(s) for s in STATIONS}
    sc.clock = parse_time(demo_clock)
    sc.W_hours = demo_params["W_hours"]
    sc.R_km = demo_params["R_km"]
    sc.L_depth = demo_params["L_depth"]
    sc.T_archive_hours = demo_params["T_archive_hours"]
    for e in demo_events:
        sc.create_event(e["event_id"], e["magnitude"], e["depth_km"],
                        e["epicenter"]["x"], e["epicenter"]["y"],
                        parse_time(e["occurrence_time"]), e["station_id"])
    sc.undo_stack._stack.clear()
    put(TOPOLOGIES, "prueba_carga_topologia.json", sc.snapshot())

    # stress: ascending insertions with rotations postponed (|bf| > 2).
    sc = Scenario()
    sc.load_insertions_file(os.path.join(INSERTIONS, "mezclado.json"))
    sc.toggle_stress()
    for i, magnitude in enumerate((7.2, 7.4, 7.6, 7.8, 8.0, 8.2), start=200):
        sc.create_event(i, magnitude, 10.0, 450, 650,
                        parse_time("2026-09-11T00:00:00Z"), "EST-001")
    stress = sc.snapshot()
    put(TOPOLOGIES, "estres.json", stress)

    unbalanced_normal = copy.deepcopy(stress)
    unbalanced_normal["mode"] = "normal"
    put(TOPOLOGIES, "desbalanceado-modo-normal.json", unbalanced_normal)

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
    put(TOPOLOGIES, "inconsistente-orden.json", broken_order)

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
    put(TOPOLOGIES, "inconsistente-metadatos.json", broken_meta)

    # Invalid references: a link to a missing id and a node with two parents.
    broken_links = copy.deepcopy(normal)
    nodes = broken_links["active_tree"]["nodes"]
    leaves = [n for n in nodes if n["left"] is None and n["right"] is None]
    leaves[0]["left"] = 999999
    leaves[1]["right"] = broken_links["active_tree"]["root"]
    put(TOPOLOGIES, "invalido-referencias.json", broken_links)


if __name__ == "__main__":
    main()
