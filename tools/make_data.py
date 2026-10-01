"""
Regenerate the JSON test files in data/ (Sections 8, 12 and 16).

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

from domain.models import Epicenter, Report, SeismicEvent, Station, Zone, parse_time  # noqa: E402
from domain.scenario import Scenario  # noqa: E402
from domain.storage import FORMAT_BURST, FORMAT_INSERTIONS, write_json_file  # noqa: E402

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


def report(event_id, revision, station, magnitude, depth, x, y, time):
    return {"event_id": event_id, "revision": revision, "station_id": station,
            "magnitude": magnitude, "depth_km": depth, "epicenter": {"x": x, "y": y},
            "occurrence_time": time}


def burst_file(reports, description):
    return {"format": FORMAT_BURST, "description": description, "reports": reports}


def scenario_with(events):
    """A scenario with main.py's zones and stations, CLOCK as its clock and
    the given events created one by one (so heights, keys and associations
    come from the real operations)."""
    sc = Scenario()
    sc.zones = [Zone.from_dict(z) for z in ZONES]
    sc.stations = {s["station_id"]: Station.from_dict(s) for s in STATIONS}
    sc.clock = parse_time(CLOCK)
    for e in events:
        sc.create_event(e["event_id"], e["magnitude"], e["depth_km"],
                        e["epicenter"]["x"], e["epicenter"]["y"],
                        parse_time(e["occurrence_time"]), e["station_id"])
    return sc


def scenario_file(sc, description):
    """Snapshot of a scenario plus a description; the loader ignores the extra field."""
    return {**sc.snapshot(), "description": description}


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

    if verbose:
        print("Report bursts (Section 8):")
    write_bursts(lambda name, data: put(os.path.join(out_dir, "bursts"), name, data))

    if verbose:
        print("Section 16 cases:")
    write_section16_cases(lambda case, name, data: put(
        os.path.join(out_dir, "test_cases_section16", case), name, data))


# =====================================================================
# Report bursts (Section 8), all for topologies/normal.json
# =====================================================================

def write_bursts(put):
    """Section 8 asks for bursts "con altas, confirmaciones, reportes antiguos
    y correcciones que cambian la clave". They are meant for
    topologies/normal.json (clock 2026-09-12): its state decides each result."""
    t150 = "2026-09-08T10:00:00Z"
    put("rafaga-mixta.json", burst_file([
        report(300, 1, "EST-003", 5.2, 12.0, 320, 640, "2026-09-11T20:00:00Z"),  # new event
        report(150, 1, "EST-004", 5.6, 25.0, 600, 600, t150),    # confirms 150, adds EST-004
        report(300, 1, "EST-001", 5.2, 12.0, 320, 640, "2026-09-11T20:00:00Z"),  # confirms 300
        report(150, 2, "EST-002", 4.4, 25.0, 600, 600, t150),    # correction: (3, 5.6) -> (1, 4.4)
        report(150, 1, "EST-003", 5.6, 25.0, 600, 600, t150),    # older revision: discarded
        report(300, 1, "EST-001", 5.2, 12.0, 320, 640, "2026-09-11T20:00:00Z"),  # same again
        report(301, 3, "EST-004", 3.9, 8.0, 880, 120, "2026-09-11T21:30:00Z"),   # new, first rev 3
        report(120, 1, "EST-002", 4.6, 30.0, 300, 300, "2026-09-07T10:00:00Z"),  # same rev, other data
        report(118, 2, "EST-001", 6.4, 20.0, 500, 100, "2026-09-07T10:15:00Z"),  # (3, 4.8) -> (3, 6.4)
        report(181, 2, "EST-003", 0.6, 2.0, 900, 900, "2026-09-10T07:00:00Z"),   # deleted id
        report(141, 2, "EST-004", 4.9, 20.0, 160, 130, "2026-09-07T11:05:00Z"),  # reactivates 141
        report(142, 1, "EST-002", 3.2, 16.0, 170, 140, "2026-09-07T11:10:00Z"),  # confirms archived
    ], "Para topologies/normal.json. 12 reportes de 4 estaciones: altas (300, y 301 con "
       "revision inicial 3), confirmaciones (150, 300 y una repetida), una correccion que "
       "cambia la prioridad (150: 3 -> 1) y otra que solo cambia la magnitud (118), un "
       "reporte antiguo (150 rev 1), un conflicto (120), un ID eliminado (181), una "
       "reactivacion del historico (141) y una confirmacion de un archivado (142)."))

    # Eight new events reported by several stations at once: queue order is
    # receipt order, while each event's priority decides its place in the AVL.
    new_events = [(310, 6.3, 12.0, 260, 560), (311, 2.2, 40.0, 120, 90),
                  (312, 4.9, 45.0, 700, 650), (313, 7.4, 8.0, 420, 720),
                  (314, 3.1, 15.0, 900, 300), (315, 5.1, 22.0, 610, 420),
                  (316, 1.4, 5.0, 60, 380), (317, 6.8, 30.0, 330, 610)]
    stations = [s["station_id"] for s in STATIONS]
    reports = []
    for i, (event_id, magnitude, depth, x, y) in enumerate(new_events):
        time = f"2026-09-11T{10 + i:02d}:00:00Z"
        reports.append(report(event_id, 1, stations[i % 4], magnitude, depth, x, y, time))
        if i:  # the previous event, confirmed by two other stations
            prev_id, prev_m, prev_h, prev_x, prev_y = new_events[i - 1]
            prev_time = f"2026-09-11T{9 + i:02d}:00:00Z"
            for offset in (1, 2):
                reports.append(report(prev_id, 1, stations[(i - 1 + offset) % 4],
                                      prev_m, prev_h, prev_x, prev_y, prev_time))
    put("rafaga-altas-concurrentes.json", burst_file(
        reports, "Para topologies/normal.json. 8 eventos nuevos (310-317) reportados por "
                 "4 estaciones, cada uno confirmado despues por otras 2: el orden de la cola "
                 "es el de recepcion, no el de prioridad."))

    put("rafaga-invalida.json", burst_file([
        report(320, 1, "EST-001", 4.0, 10.0, 100, 100, "2026-09-11T08:00:00Z"),
        report(321, 1, "EST-999", 4.0, 10.0, 100, 100, "2026-09-11T08:00:00Z"),
        report(322, 1, "EST-002", 5.25, 10.0, 100, 100, "2026-09-11T08:00:00Z"),
        report(323, 1, "EST-003", 4.0, 10.0, 100, 100, "2026-09-13T08:00:00Z"),
    ], "Rechazada completa: estacion desconocida, magnitud con dos decimales y una "
       "ocurrencia posterior al reloj. La cola no cambia."))


# =====================================================================
# Section 16 cases: one folder per case, each file states its initial state
# =====================================================================

# Case 4: one insertion order per rebalancing case, three P1 events each.
ROTATION_ORDERS = {
    "ll": (3.0, 2.0, 1.0),
    "rr": (1.0, 2.0, 3.0),
    "lr": (3.0, 1.0, 2.0),
    "rl": (1.0, 3.0, 2.0),
}
# Seven insertions that trigger RR, LL, RL and LR once each, in that order.
ALL_FOUR_ORDER = (0.5, 1.5, 3.5, 3.0, 2.0, 2.5, 1.0)


def write_section16_cases(put):
    # 1. Limits and ties: priority of each boundary and the id tie-break.
    put("caso1-limites-empates", "inserciones.json", insertion_file([
        event(101, 4.5, 30.0, 600, 600, "2026-09-10T08:00:00Z"),    # M = 4.5, H = 30.0, populated
        event(102, 4.5, 30.1, 600, 600, "2026-09-10T08:10:00Z"),    # H just above 30
        event(103, 4.4, 10.0, 600, 600, "2026-09-10T08:20:00Z"),    # M just below 4.5
        event(104, 6.0, 300.0, 100, 150, "2026-09-10T08:30:00Z"),   # M = 6.0, unpopulated, deep
        event(105, 5.9, 300.0, 100, 150, "2026-09-10T08:40:00Z"),   # M just below 6.0
        event(106, 4.8, 20.0, 500, 100, "2026-09-10T08:50:00Z"),    # on the Sur/Costa border
        event(107, 4.8, 20.0, 499.9, 100, "2026-09-10T09:00:00Z"),  # just inside Sur
        event(110, 3.2, 12.0, 900, 900, "2026-09-10T09:10:00Z"),    # same P and M ...
        event(108, 3.2, 14.0, 910, 910, "2026-09-10T09:20:00Z"),    # ... inserted out of
        event(109, 3.2, 16.0, 920, 920, "2026-09-10T09:30:00Z"),    # ... id order
    ], "Caso 1 (seccion 16): limites de prioridad M = 4.5, M = 6.0 y H = 30.0, un epicentro "
       "en el borde de dos zonas (x = 500) y tres eventos con igual prioridad y magnitud."))

    # 2. Correction and older report: 200 goes from M 4.8 / H 70 (P2) to M 6.2 /
    #    H 15 (P3) by hand; then a revision 1 report arrives.
    sc = scenario_with([
        event(201, 3.1, 12.0, 120, 80, "2026-09-10T08:00:00Z"),
        event(202, 5.2, 40.0, 650, 650, "2026-09-10T09:00:00Z", "EST-002"),
        event(200, 4.8, 70.0, 300, 600, "2026-09-10T10:00:00Z"),
        event(203, 2.5, 8.0, 900, 900, "2026-09-10T11:00:00Z", "EST-004"),
        event(204, 6.6, 18.0, 700, 200, "2026-09-10T12:00:00Z", "EST-004"),
    ])
    put("caso2-correccion-reporte-antiguo", "escenario.json", scenario_file(
        sc, "Caso 2 (seccion 16): el evento 200 tiene M = 4.8 y H = 70.0 km (prioridad 2, "
            "revision 1). Corregirlo a M = 6.2 y H = 15.0 y despues cargar la rafaga."))
    put("caso2-correccion-reporte-antiguo", "rafaga-revision-antigua.json", burst_file(
        [report(200, 1, "EST-002", 4.8, 70.0, 300, 600, "2026-09-10T10:00:00Z")],
        "Caso 2: llega la revision 1 del evento 200 con sus datos originales. Despues de la "
        "correccion (revision 2) debe descartarse sin crear otro nodo ni revertir la correccion."))

    # 3. Late report: 5.6 at 10:00 and 4.2 at 10:20, then a 6.1 that occurred at 09:55.
    sc = scenario_with([
        event(301, 5.6, 25.0, 600, 600, "2026-09-10T10:00:00Z", "EST-002"),
        event(302, 4.2, 25.0, 610, 605, "2026-09-10T10:20:00Z", "EST-002"),
        event(305, 3.0, 10.0, 150, 150, "2026-09-09T22:00:00Z", "EST-003"),
    ])
    put("caso3-reporte-tardio", "escenario.json", scenario_file(
        sc, "Caso 3 (seccion 16): 301 (M 5.6, 10:00) y 302 (M 4.2, 10:20) a 11 km; 302 tiene "
            "a 301 como referencia. Despues se carga la rafaga con un reporte tardio."))
    put("caso3-reporte-tardio", "rafaga-reporte-tardio.json", burst_file(
        [report(303, 1, "EST-004", 6.1, 20.0, 605, 595, "2026-09-10T09:55:00Z")],
        "Caso 3: llega tarde el evento 303, M 6.1, ocurrido a las 09:55 cerca de 301 y 302. "
        "Pasa a ser candidato de ambos y la politica lo elige como su referencia."))

    # 4a. The four rebalancing cases, by insertion.
    for case, magnitudes in ROTATION_ORDERS.items():
        put("caso4-rotaciones-recuperacion", f"rotacion-{case}.json", insertion_file(
            [event(400 + i, m, 10.0, 100 + 10 * i, 100, "2026-09-10T08:00:00Z", "EST-003")
             for i, m in enumerate(magnitudes, start=1)],
            f"Caso 4: insertar M = {', '.join(map(str, magnitudes))} (misma prioridad) "
            f"provoca un caso {case.upper()} en el AVL; el BST queda sin balancear."))
    put("caso4-rotaciones-recuperacion", "rotaciones-cuatro-casos.json", insertion_file(
        [event(450 + i, m, 10.0, 100 + 10 * i, 100, "2026-09-10T08:00:00Z", "EST-003")
         for i, m in enumerate(ALL_FOUR_ORDER, start=1)],
        "Caso 4: siete inserciones que provocan un caso RR, LL, RL y LR, en ese orden."))

    # 4b. Degraded tree in stress mode, with associations, then recovery.
    base = scenario_with([
        event(410, 3.0, 10.0, 300, 600, "2026-09-11T20:00:00Z"),
        event(411, 4.0, 10.0, 305, 605, "2026-09-11T18:00:00Z"),
        event(412, 2.0, 10.0, 310, 600, "2026-09-11T21:00:00Z"),
        event(413, 3.5, 10.0, 300, 610, "2026-09-11T19:00:00Z"),
        event(414, 1.5, 10.0, 295, 600, "2026-09-11T22:00:00Z"),
    ])
    put("caso4-rotaciones-recuperacion", "base.json", scenario_file(
        base, "Caso 4: cinco eventos cercanos con asociaciones, en modo normal. Activar el "
              "modo estres y procesar rafaga-ascendente.json para degradar el arbol."))
    ascending = burst_file(
        [report(420 + n, 1, STATIONS[n % 4]["station_id"], m, 15.0, 300 + n, 600 + n,
                f"2026-09-11T{17 - 2 * n:02d}:00:00Z")
         for n, m in enumerate((6.0, 6.2, 6.4, 6.6, 6.8, 7.0, 7.2, 7.4))],
        "Caso 4: 8 altas con claves ascendentes (cada una mayor y anterior a las demas). "
        "En modo estres forman una cadena a la derecha con factores de balance hasta -7.")
    put("caso4-rotaciones-recuperacion", "rafaga-ascendente.json", ascending)
    base.toggle_stress()
    for entry in ascending["reports"]:
        base.report_queue.enqueue(Report.from_dict(entry))
    while not base.report_queue.is_empty():
        base.process_next_report()
    put("caso4-rotaciones-recuperacion", "estres-degradado.json", scenario_file(
        base, "Caso 4: resultado de base.json + rafaga-ascendente.json en modo estres "
              "(altura 9, factores hasta -7). Usar Recuperar Balance."))

    # 5. Mass archive: perfect 15-node AVL. Keys k1..k10 are LOW, k11..k15
    #    higher. k4 (604) is young, the other LOW events are older than T.
    #    Eligible: 602 {601-603} and 606 {605-607} tie in size and depth, so the
    #    larger root id wins; 609 alone has fewer nodes. Rejected LOW roots: 608
    #    (contains the young 604) and 610 (contains 611, MEDIUM).
    magnitudes = [1.0, 1.4, 1.8, 2.2, 2.6, 3.0, 3.4, 3.8, 4.0, 4.2, 4.6, 5.0, 5.5, 6.5, 7.0]
    level_order = [8, 4, 12, 2, 6, 10, 14, 1, 3, 5, 7, 9, 11, 13, 15]
    events = []
    for k in level_order:
        if k <= 10:   # LOW, in the unpopulated Sur zone
            time = "2026-09-11T00:00:00Z" if k == 4 else f"2026-09-0{(k % 5) + 1}T06:00:00Z"
            events.append(event(600 + k, magnitudes[k - 1], 50.0, 40 + 30 * k, 60, time, "EST-003"))
        else:         # MEDIUM (M < 6, H > 30) and HIGH (M >= 6)
            depth = 50.0 if k <= 13 else 10.0
            events.append(event(600 + k, magnitudes[k - 1], depth, 850, 850,
                                "2026-09-10T12:00:00Z", "EST-004"))
    put("caso5-archivo-masivo", "escenario.json", scenario_file(
        scenario_with(events),
        "Caso 5 (seccion 16): AVL de 15 nodos. Los 10 de menor clave tienen prioridad baja y, "
        "salvo 604, mas de 72 h. Usar Archivar rama de eventos antiguos."))


if __name__ == "__main__":
    main()
