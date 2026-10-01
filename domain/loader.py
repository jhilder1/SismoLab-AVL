"""
Loader — the two load modes of Section 12 and the report bursts of Section 8.

load_topology(sc, data)     Rebuild a saved scenario from its explicit links
                            (root, left, right) without re-inserting anything.
load_insertions(sc, data)   Insert a sequence of events, in file order, into a
                            balanced AVL and into a plain BST.
load_burst(sc, data)        Validate a burst of station reports to enqueue (Section 8).

The two loads work on a temporary scenario and return the new state as a dict.
The live scenario is only read (defaults, current mode); the caller swaps the
state in with apply_state, so a rejected file leaves the current scenario
untouched. load_burst only validates and builds the reports; the caller
enqueues them, so a rejected burst leaves the queue untouched too.
"""

from __future__ import annotations

from core.avl_tree import BSTNode
from domain.models import Epicenter, Priority, Report, SeismicEvent, Station, Zone, parse_time
from domain.storage import (
    FORMAT_BURST, FORMAT_INSERTIONS, FORMAT_SCENARIO, SCHEMA_VERSION,
    StateError, apply_state, scenario_to_dict,
)
from domain.validation import (
    check_event_data, check_order, check_stored_event, check_time, check_tree,
    is_int, is_number,
)

_METRIC_NAMES = ("events_created", "reports_processed", "corrections", "archives",
                 "archive_operations", "reports_discarded", "conflicts", "confirmations")
_ROTATION_NAMES = ("ll", "rr", "lr", "rl", "simple_left", "simple_right")


# =====================================================================
# Topology load
# =====================================================================

def load_topology(sc, data: dict) -> tuple[dict, dict]:
    """Validate a scenario file and rebuild it exactly. Returns (state, info).

    Required: format, clock and active_tree (root + nodes with links, height,
    balance_factor and event). Missing optional parts take documented defaults:
    zones/stations/parameters from the current scenario, empty history,
    deleted ids and queue, zero metrics, a BST with the same shape as the AVL,
    and associations recalculated with the deterministic policy.
    """
    _check_format(data, FORMAT_SCENARIO)
    problems: list[str] = []
    state = _with_defaults(sc, data)
    _check_scenario_fields(state, problems)
    if problems:
        raise StateError(problems)

    # Structure: unknown links, two positions, cycles, duplicated ids.
    tmp = type(sc)()
    apply_state(tmp, state)

    # Order by K, stored heights and balance factors, stored priorities.
    stored_nodes = {n["event_id"]: n for n in state["active_tree"]["nodes"]}
    tree_report = check_tree(tmp.avl, stored_nodes)
    problems += tree_report["order"] + tree_report["metadata"]
    _check_stored_priorities(tmp, stored_nodes, state["archived"], problems)
    _check_references(tmp, problems)
    if "bst" in data:
        _check_bst(tmp, problems)

    unbalanced = tree_report["unbalanced"]
    stress = state["mode"] == "stress" or sc.avl.stress_mode
    if unbalanced and not stress:
        problems += [f"Event {event_id} has balance factor {bf}" for event_id, bf in unbalanced]
        problems.append("The topology is ordered but unbalanced: it can only be loaded "
                        "with stress mode active")
    if problems:
        raise StateError(problems)

    tmp.avl.stress_mode = stress if unbalanced else state["mode"] == "stress"
    if "bst" not in data:
        tmp.bst.root = _clone_as_bst(tmp.avl.root)
        tmp.bst.size = tmp.avl.size
    if "associations" not in data:
        tmp.recalculate_all_associations()

    info = {
        "mode": "stress" if tmp.avl.stress_mode else "normal",
        "balanced": not unbalanced,
        "unbalanced_nodes": [{"event_id": e, "balance_factor": bf} for e, bf in unbalanced],
        "active": tmp.avl.size,
        "archived": len(tmp.archived),
        "root": tmp.avl.root.event_id if tmp.avl.root else None,
        "height": tmp.avl.height,
    }
    return scenario_to_dict(tmp), info


def _with_defaults(sc, data: dict) -> dict:
    """Copy of `data` where every optional section has its documented default."""
    state = dict(data)
    state.setdefault("schema_version", SCHEMA_VERSION)
    state.setdefault("mode", "normal")
    state.setdefault("zones", [z.to_dict() for z in sc.zones])
    state.setdefault("stations", [s.to_dict() for s in sc.stations.values()])
    parameters = {"W_hours": sc.W_hours, "R_km": sc.R_km,
                  "L_depth": sc.L_depth, "T_archive_hours": sc.T_archive_hours}
    if isinstance(data.get("parameters"), dict):
        parameters.update(data["parameters"])
    state["parameters"] = parameters
    state.setdefault("archived", [])
    state.setdefault("deleted_ids", [])
    state.setdefault("associations", [])
    state.setdefault("queue", {"reports": [], "total_enqueued": 0})
    state.setdefault("bst", {"root": None, "nodes": []})

    metrics = {name: 0 for name in _METRIC_NAMES}
    rotations = {name: 0 for name in _ROTATION_NAMES}
    if isinstance(data.get("metrics"), dict):
        metrics.update({k: v for k, v in data["metrics"].items() if k != "rotations"})
        if isinstance(data["metrics"].get("rotations"), dict):
            rotations.update(data["metrics"]["rotations"])
    metrics["rotations"] = rotations
    state["metrics"] = metrics
    return state


def _check_scenario_fields(state: dict, problems: list[str]) -> None:
    """Types, ranges and one-decimal rules before any structure is built."""
    if state["schema_version"] != SCHEMA_VERSION:
        problems.append(f"Unsupported schema_version {state['schema_version']!r}")
    clock = check_time(state.get("clock"), "clock", "Scenario", problems)
    if state["mode"] not in ("normal", "stress"):
        problems.append(f"mode must be 'normal' or 'stress', got {state['mode']!r}")
    _check_parameters(state["parameters"], problems)
    zones_ok = _check_zones(state["zones"], problems)
    station_ids = _check_stations(state["stations"], problems)

    tree = state.get("active_tree")
    if not isinstance(tree, dict) or not isinstance(tree.get("nodes"), list):
        problems.append("active_tree must be an object with 'root' and a 'nodes' list")
        return
    root = tree.get("root")
    if root is not None and not is_int(root):
        problems.append(f"active_tree.root must be an event id or null, got {root!r}")
    for position, node in enumerate(tree["nodes"]):
        where = f"Node #{position + 1}"
        if not isinstance(node, dict):
            problems.append(f"{where}: must be an object")
            continue
        if is_int(node.get("event_id")):
            where = f"Node {node['event_id']}"
        else:
            problems.append(f"{where}: event_id must be an integer")
        for side in ("left", "right"):
            if node.get(side) is not None and not is_int(node.get(side)):
                problems.append(f"{where}: {side} must be an event id or null")
            if side not in node:
                problems.append(f"{where}: missing '{side}' (use null for an empty link)")
        for field in ("height", "balance_factor"):
            if not is_int(node.get(field)):
                problems.append(f"{where}: {field} must be an integer")
        check_stored_event(node.get("event"), clock, station_ids, "active", where, problems)

    if not isinstance(state["archived"], list):
        problems.append("archived must be a list")
    else:
        for event in state["archived"]:
            event_id = event.get("event_id") if isinstance(event, dict) else "?"
            check_stored_event(event, clock, station_ids, "archived",
                               f"Archived event {event_id}", problems)

    deleted = state["deleted_ids"]
    if not isinstance(deleted, list) or not all(is_int(i) and 1 <= i <= 999999 for i in deleted):
        problems.append("deleted_ids must be a list of event ids")
    elif len(set(deleted)) != len(deleted):
        problems.append("deleted_ids contains repeated ids")

    queue = state["queue"]
    if not isinstance(queue, dict) or not isinstance(queue.get("reports"), list):
        problems.append("queue must be an object with a 'reports' list")
    else:
        queue.setdefault("total_enqueued", len(queue["reports"]))
        # Queued reports get the same checks as enqueue_report, so a file
        # cannot slip in data the program itself would never accept.
        for position, report in enumerate(queue["reports"], start=1):
            where = f"Queued report #{position}"
            check_event_data(report, clock, where, problems)
            if isinstance(report, dict):
                if not is_int(report.get("revision")) or report["revision"] < 1:
                    problems.append(f"{where}: revision must be a positive integer")
                if report.get("station_id") not in station_ids:
                    problems.append(f"{where}: unknown station {report.get('station_id')!r}")

    metrics = state["metrics"]
    counters = [metrics[n] for n in _METRIC_NAMES] + list(metrics["rotations"].values())
    if not all(is_int(c) and c >= 0 for c in counters):
        problems.append("metrics must be non-negative integers")
    if not zones_ok:
        problems.append("Zones are invalid, so priorities cannot be verified")


def _check_parameters(params: dict, problems: list[str]) -> None:
    for name in ("W_hours", "R_km", "T_archive_hours"):
        if not is_number(params.get(name)) or params[name] <= 0:
            problems.append(f"parameters.{name} must be a positive number")
    if not is_int(params.get("L_depth")) or params["L_depth"] < 0:
        problems.append("parameters.L_depth must be a non-negative integer")


def _check_zones(zones, problems: list[str]) -> bool:
    before = len(problems)
    if not isinstance(zones, list):
        problems.append("zones must be a list")
        return False
    for zone in zones:
        name = zone.get("name", "?") if isinstance(zone, dict) else "?"
        if not isinstance(zone, dict):
            problems.append("Each zone must be an object")
            continue
        bounds = [zone.get(k) for k in ("x_min", "x_max", "y_min", "y_max")]
        if not all(is_number(b) and 0 <= b <= 1000 for b in bounds):
            problems.append(f"Zone {name}: limits must be numbers between 0 and 1000")
        elif bounds[0] > bounds[1] or bounds[2] > bounds[3]:
            problems.append(f"Zone {name}: minimum limit is greater than maximum limit")
        if not isinstance(zone.get("is_populated"), bool):
            problems.append(f"Zone {name}: is_populated must be true or false")
    return len(problems) == before


def _check_stations(stations, problems: list[str]) -> set[str]:
    ids: set[str] = set()
    if not isinstance(stations, list):
        problems.append("stations must be a list")
        return ids
    for station in stations:
        station_id = station.get("station_id") if isinstance(station, dict) else None
        if not isinstance(station_id, str) or not station_id:
            problems.append("Each station needs a non-empty station_id")
        elif station_id in ids:
            problems.append(f"Station {station_id} is repeated")
        else:
            ids.add(station_id)
    return ids


def _check_stored_priorities(tmp, stored_nodes: dict, archived: list,
                             problems: list[str]) -> None:
    """Section 12: a stored priority (and key) must match the calculated one."""
    for event_id, node in stored_nodes.items():
        event = tmp.event_index.get(event_id)
        if event is None:
            continue
        stored = node["event"].get("priority")
        if stored is not None and stored != int(event.priority):
            problems.append(f"Event {event_id}: stored priority {stored}, "
                            f"calculated {int(event.priority)}")
        key = node.get("key")
        if key is not None and key != event.build_key().to_list():
            problems.append(f"Event {event_id}: stored key {key}, "
                            f"calculated {event.build_key().to_list()}")
    for data in archived:
        event = tmp.archived.get(data.get("event_id"))
        stored = data.get("priority")
        if event is not None and stored is not None and stored != int(event.priority):
            problems.append(f"Archived event {event.event_id}: stored priority {stored}, "
                            f"calculated {int(event.priority)}")


def _check_references(tmp, problems: list[str]) -> None:
    """Associations point to live identities and cannot form cycles (Section 7).

    A reference must be larger and strictly earlier, so following references
    always moves back in time: a cycle is impossible when this holds.
    """
    known = {**tmp.archived, **tmp.event_index}
    for event in known.values():
        ref_id = event.reference_event_id
        if ref_id is None:
            continue
        ref = known.get(ref_id)
        if ref is None:
            state = "deleted" if ref_id in tmp.deleted_ids else "unknown"
            problems.append(f"Event {event.event_id} references {state} event {ref_id}")
        elif not (ref.occurrence_time < event.occurrence_time
                  and ref.magnitude > event.magnitude):
            problems.append(f"Event {event.event_id} references event {ref_id}, which is "
                            f"not larger and earlier")


def _check_bst(tmp, problems: list[str]) -> None:
    """A stored BST must hold exactly the active keys, in global order."""
    bst_keys, stack = {}, [tmp.bst.root] if tmp.bst.root else []
    while stack:
        node = stack.pop()
        bst_keys[node.event_id] = node.key
        stack.extend(child for child in (node.left, node.right) if child)
    for event_id in sorted(bst_keys.keys() ^ tmp.event_index.keys()):
        where = "BST" if event_id in bst_keys else "AVL"
        problems.append(f"Event {event_id} is only in the {where}")
    for event_id, key in bst_keys.items():
        event = tmp.event_index.get(event_id)
        if event is not None and key != event.build_key():
            problems.append(f"BST node {event_id}: key {key}, calculated {event.build_key()}")
    problems.extend("BST: " + p for p in check_order(tmp.bst.root))


def _clone_as_bst(node):
    """BST with the same shape and keys as the given AVL subtree (iterative)."""
    if node is None:
        return None
    root = BSTNode(node.key)
    stack = [(node, root)]
    while stack:
        source, copy = stack.pop()
        for side in ("left", "right"):
            child = getattr(source, side)
            if child:
                child_copy = BSTNode(child.key)
                setattr(copy, side, child_copy)
                stack.append((child, child_copy))
    return root


# =====================================================================
# Insertion load
# =====================================================================

def load_insertions(sc, data: dict) -> tuple[dict, dict]:
    """Insert the file's events, in order, into a balanced AVL and a plain BST.

    File: {"format": "sismolab-insertions", "events": [...]} with optional
    clock, zones, stations and parameters (defaults: current scenario).
    Each event: event_id, magnitude, depth_km, epicenter {x, y},
    occurrence_time, station_id and optional revision (default 1).
    A repeated id invalidates the whole file (Section 12).
    Returns (state, comparison of both trees).
    """
    _check_format(data, FORMAT_INSERTIONS)
    problems: list[str] = []

    clock = sc.clock
    if "clock" in data:
        clock = check_time(data["clock"], "clock", "File", problems)
    zones_data = data.get("zones", [z.to_dict() for z in sc.zones])
    stations_data = data.get("stations", [s.to_dict() for s in sc.stations.values()])
    parameters = {"W_hours": sc.W_hours, "R_km": sc.R_km,
                  "L_depth": sc.L_depth, "T_archive_hours": sc.T_archive_hours}
    if isinstance(data.get("parameters"), dict):
        parameters.update(data["parameters"])
    _check_parameters(parameters, problems)
    _check_zones(zones_data, problems)
    station_ids = _check_stations(stations_data, problems)

    events = data.get("events")
    if not isinstance(events, list) or not events:
        problems.append("events must be a non-empty list")
        raise StateError(problems)

    first_position: dict[int, int] = {}
    for position, entry in enumerate(events, start=1):
        event_id = entry.get("event_id") if isinstance(entry, dict) else None
        where = f"Event #{position}" + (f" (id {event_id})" if is_int(event_id) else "")
        check_event_data(entry, clock, where, problems)
        if isinstance(entry, dict) and entry.get("station_id") not in station_ids:
            problems.append(f"{where}: unknown station {entry.get('station_id')!r}")
        if is_int(event_id):
            if event_id in first_position:
                problems.append(f"Id {event_id} is repeated at positions "
                                f"{first_position[event_id]} and {position}: "
                                f"the file is invalid")
            else:
                first_position[event_id] = position
    if problems:
        raise StateError(problems)

    tmp = type(sc)()
    tmp.zones = [Zone.from_dict(z) for z in zones_data]
    tmp.stations = {s["station_id"]: Station.from_dict(s) for s in stations_data}
    tmp.clock = clock
    tmp.W_hours = float(parameters["W_hours"])
    tmp.R_km = float(parameters["R_km"])
    tmp.L_depth = int(parameters["L_depth"])
    tmp.T_archive_hours = float(parameters["T_archive_hours"])

    # Same comparator and the same order for both trees; AVL always balanced.
    for entry in events:
        event = SeismicEvent(
            event_id=entry["event_id"], magnitude=entry["magnitude"],
            depth_km=entry["depth_km"],
            epicenter=Epicenter(entry["epicenter"]["x"], entry["epicenter"]["y"]),
            occurrence_time=parse_time(entry["occurrence_time"]),
            station_id=entry["station_id"], zones=tmp.zones,
            revision=entry.get("revision", 1),
        )
        tmp.avl.insert(event)
        tmp.bst.insert(event.build_key())
        tmp.event_index[event.event_id] = event
        tmp.total_events_created += 1
    tmp.recalculate_all_associations()

    return scenario_to_dict(tmp), compare_loaded_trees(tmp)


def compare_loaded_trees(sc) -> dict:
    """Root, height, maximum depth, leaves and search comparisons (Sections 11-12)."""
    keys = sc.avl.inorder()

    def describe(tree) -> dict:
        comparisons = [tree.search(key)[1] for key in keys]
        return {
            "root": str(tree.root.key) if tree.root else None,
            "root_id": tree.root.event_id if tree.root else None,
            "height": tree.height,
            "max_depth": tree.height,  # deepest node depth = tree height
            "leaves": tree.count_leaves(),
            "nodes": tree.size,
            "total_comparisons": sum(comparisons),
            "avg_comparisons": round(sum(comparisons) / len(keys), 2) if keys else 0.0,
            "max_comparisons": max(comparisons, default=0),
        }

    avl = sc.avl
    return {
        "events": len(keys),
        "avl": describe(avl),
        "bst": describe(sc.bst),
        "rotations": {"ll": avl.rotations_ll, "rr": avl.rotations_rr,
                      "lr": avl.rotations_lr, "rl": avl.rotations_rl,
                      "simple_left": avl.simple_turns_left,
                      "simple_right": avl.simple_turns_right},
        "by_priority": {p.name: sum(1 for e in sc.event_index.values() if e.priority == p)
                        for p in Priority},
    }


# =====================================================================
# Report burst (Section 8)
# =====================================================================

def load_burst(sc, data: dict) -> list[Report]:
    """Validate a burst of station reports for the current scenario.

    File: {"format": "sismolab-burst", "reports": [...]} with an optional
    description. Each report: event_id, revision, station_id, magnitude,
    depth_km, epicenter {x, y} and occurrence_time, checked like
    enqueue_report (ranges, one decimal, not after the clock, known station).
    Nothing is decided here: whether a report creates, confirms, corrects or
    is discarded depends on the scenario when its queue step runs. One bad
    report rejects the whole file, so the queue never holds half a burst.
    Returns the reports in file order, which is their receipt order.
    """
    _check_format(data, FORMAT_BURST)
    reports = data.get("reports")
    if not isinstance(reports, list) or not reports:
        raise StateError(["reports must be a non-empty list"])

    problems: list[str] = []
    for position, report in enumerate(reports, start=1):
        event_id = report.get("event_id") if isinstance(report, dict) else None
        where = f"Report #{position}" + (f" (id {event_id})" if is_int(event_id) else "")
        check_event_data(report, sc.clock, where, problems)
        if not isinstance(report, dict):
            continue
        if "revision" not in report:
            problems.append(f"{where}: missing revision")
        if report.get("station_id") not in sc.stations:
            problems.append(f"{where}: unknown station {report.get('station_id')!r}")
    if problems:
        raise StateError(problems)
    return [Report.from_dict(report) for report in reports]


def _check_format(data: dict, expected: str) -> None:
    found = data.get("format")
    if found == expected:
        return
    if found == FORMAT_INSERTIONS:
        raise StateError(["This file is an insertion sequence: use 'Cargar por inserciones'"])
    if found == FORMAT_SCENARIO:
        raise StateError(["This file is a saved scenario (topology): use 'Cargar escenario'"])
    if found == FORMAT_BURST:
        raise StateError(["This file is a report burst: use 'Cargar rafaga' in the Cola tab"])
    raise StateError([f"Unknown file format {found!r}: expected {expected!r}"])
