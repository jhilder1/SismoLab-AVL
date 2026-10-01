"""
Storage — full scenario state as plain JSON-ready data (Sections 12 and 13).

One representation serves three purposes:
  * structural save / load of a scenario file (Section 12),
  * named versions that survive a restart (Section 13),
  * undo snapshots that restore the exact topology (Section 13).

scenario_to_dict(sc)   -> dict with only str/int/float/bool/None/list/dict.
                          Every value is a fresh copy, so later changes to the
                          scenario never alter a state that was already taken.
apply_state(sc, data)  -> rebuilds every structure from `data` and swaps it into
                          `sc` only when the whole rebuild succeeded (all or
                          nothing). The AVL and the BST are rebuilt from their
                          stored left/right links, never by re-inserting keys,
                          so the exact topology comes back.

The undo stack is not part of the state: Section 13 says versions do not need it.
"""

from __future__ import annotations

import json
import os

from core.avl_tree import AVLNode, AVLTree, BSTNode, BSTTree, TreeKey
from core.linear import ReportQueue
from domain.models import (
    Association, Report, SeismicEvent, Station, Zone,
    EventStatus, format_time, parse_time,
)

SCHEMA_VERSION = 1

# "format" tells the two load modes of Section 12 and a report burst apart.
FORMAT_SCENARIO = "sismolab-scenario"      # full state with explicit topology
FORMAT_INSERTIONS = "sismolab-insertions"  # plain sequence of events
FORMAT_BURST = "sismolab-burst"            # station reports to enqueue (Section 8)

# Scenario counters saved under "metrics" (attribute name -> JSON name).
_SCENARIO_METRICS = {
    "total_events_created": "events_created",
    "total_reports_processed": "reports_processed",
    "total_corrections": "corrections",
    "total_archives": "archives",                       # events archived (cumulative)
    "total_archive_operations": "archive_operations",   # mass-archive operations
    "total_reports_discarded": "reports_discarded",
    "total_conflicts": "conflicts",
    "total_confirmations": "confirmations",
}

# AVL rotation counters saved under "metrics.rotations" (Section 14).
_ROTATION_METRICS = {
    "rotations_ll": "ll",
    "rotations_rr": "rr",
    "rotations_lr": "lr",
    "rotations_rl": "rl",
    "simple_turns_left": "simple_left",
    "simple_turns_right": "simple_right",
}


class StateError(ValueError):
    """Raised when a state cannot be rebuilt. `problems` lists every cause found."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


# =====================================================================
# JSON files
# =====================================================================

def read_json_file(path: str) -> dict:
    """Read a JSON object; unreadable or malformed files raise StateError."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise StateError([f"Cannot read {path}: {exc.strerror}"]) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StateError([f"{os.path.basename(path)} is not valid JSON: {exc}"]) from exc
    if not isinstance(data, dict):
        raise StateError(["The JSON file must contain an object at the top level"])
    return data


def write_json_file(path: str, data: dict) -> None:
    """Write through a temporary file so a failed save never leaves half a file."""
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


# =====================================================================
# Scenario -> dict
# =====================================================================

def scenario_to_dict(sc) -> dict:
    """Capture the whole operational state of the scenario (Section 12 list)."""
    return {
        "format": FORMAT_SCENARIO,
        "schema_version": SCHEMA_VERSION,
        "clock": format_time(sc.clock),
        "mode": "stress" if sc.avl.stress_mode else "normal",
        "parameters": {
            "W_hours": sc.W_hours,
            "R_km": sc.R_km,
            "L_depth": sc.L_depth,
            "T_archive_hours": sc.T_archive_hours,
        },
        "zones": [z.to_dict() for z in sc.zones],
        "stations": [s.to_dict() for s in sc.stations.values()],
        "active_tree": _avl_to_dict(sc.avl),
        "bst": _bst_to_dict(sc.bst),
        "archived": [e.to_dict() for e in sc.archived.values()],
        "deleted_ids": sorted(sc.deleted_ids),
        "associations": [a.to_dict() for a in sc.associations.values()],
        "queue": {
            "reports": [r.to_dict() for r in sc.report_queue.get_all()],
            "total_enqueued": sc.report_queue.total_enqueued,
        },
        "metrics": metrics_to_dict(sc),
    }


def _avl_to_dict(avl: AVLTree) -> dict:
    """Store every node once with its links as event ids (None = empty link).

    Nodes are listed in preorder, so the file reads top-down like the tree.
    """
    nodes = []
    stack = [avl.root] if avl.root else []
    while stack:
        node = stack.pop()
        nodes.append({
            "event_id": node.event_id,
            "left": node.left.event_id if node.left else None,
            "right": node.right.event_id if node.right else None,
            "key": node.key.to_list(),
            "height": node.height,
            "balance_factor": node.balance_factor,
            "event": node.event.to_dict(),
        })
        # Right is pushed first so the left child is visited first.
        if node.right:
            stack.append(node.right)
        if node.left:
            stack.append(node.left)
    return {"root": avl.root.event_id if avl.root else None, "nodes": nodes}


def _bst_to_dict(bst: BSTTree) -> dict:
    """Same link format as the AVL; the BST only holds keys."""
    nodes = []
    stack = [bst.root] if bst.root else []
    while stack:
        node = stack.pop()
        nodes.append({
            "event_id": node.event_id,
            "left": node.left.event_id if node.left else None,
            "right": node.right.event_id if node.right else None,
            "key": node.key.to_list(),
        })
        if node.right:
            stack.append(node.right)
        if node.left:
            stack.append(node.left)
    return {"root": bst.root.event_id if bst.root else None, "nodes": nodes}


def metrics_to_dict(sc) -> dict:
    metrics = {name: getattr(sc, attr) for attr, name in _SCENARIO_METRICS.items()}
    metrics["rotations"] = {name: getattr(sc.avl, attr)
                            for attr, name in _ROTATION_METRICS.items()}
    return metrics


# =====================================================================
# dict -> Scenario
# =====================================================================

def apply_state(sc, data: dict) -> None:
    """Replace the scenario state with `data`, or raise StateError and keep it intact."""
    built = _build_state(data)
    for attr, value in built.items():
        setattr(sc, attr, value)


def _build_state(data: dict) -> dict:
    """Build every structure in local variables; nothing touches the live scenario."""
    problems: list[str] = []
    try:
        if data.get("schema_version") != SCHEMA_VERSION:
            raise StateError([f"Unsupported schema_version: {data.get('schema_version')!r} "
                              f"(expected {SCHEMA_VERSION})"])

        zones = [Zone.from_dict(z) for z in data["zones"]]
        stations = {s["station_id"]: Station.from_dict(s) for s in data["stations"]}

        avl_data = data["active_tree"]
        event_index = {}
        for node_data in avl_data["nodes"]:
            event = SeismicEvent.from_dict(node_data["event"], zones)
            if event.event_id != node_data["event_id"]:
                problems.append(f"Node {node_data['event_id']} holds event {event.event_id}")
            if event.event_id in event_index:
                problems.append(f"Event {event.event_id} appears twice in the active tree")
            event.status = EventStatus.ACTIVE
            event_index[event.event_id] = event

        archived = {}
        for event_data in data["archived"]:
            event = SeismicEvent.from_dict(event_data, zones)
            if event.event_id in event_index or event.event_id in archived:
                problems.append(f"Event {event.event_id} is duplicated between active and archived")
            event.status = EventStatus.ARCHIVED
            archived[event.event_id] = event

        deleted_ids = set(data["deleted_ids"])
        for event_id in deleted_ids & (event_index.keys() | archived.keys()):
            problems.append(f"Deleted id {event_id} is also active or archived")

        avl = _avl_from_dict(avl_data, event_index, problems)
        avl.stress_mode = data["mode"] == "stress"
        rotations = data["metrics"]["rotations"]
        for attr, name in _ROTATION_METRICS.items():
            setattr(avl, attr, int(rotations[name]))

        bst = _bst_from_dict(data["bst"], problems)

        associations = {}
        for assoc_data in data["associations"]:
            assoc = Association.from_dict(assoc_data)
            associations[assoc.event_id] = assoc

        queue = ReportQueue()
        for report_data in data["queue"]["reports"]:
            queue.enqueue(Report.from_dict(report_data))
        queue.total_enqueued = int(data["queue"]["total_enqueued"])

        params = data["parameters"]
        built = {
            "zones": zones,
            "stations": stations,
            "avl": avl,
            "bst": bst,
            "event_index": event_index,
            "archived": archived,
            "deleted_ids": deleted_ids,
            "associations": associations,
            "report_queue": queue,
            "clock": parse_time(data["clock"]),
            "W_hours": float(params["W_hours"]),
            "R_km": float(params["R_km"]),
            "L_depth": int(params["L_depth"]),
            "T_archive_hours": float(params["T_archive_hours"]),
        }
        metrics = data["metrics"]
        for attr, name in _SCENARIO_METRICS.items():
            built[attr] = int(metrics[name])
    except StateError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        problems.append(f"Malformed state: {type(exc).__name__}: {exc}")

    if problems:
        raise StateError(problems)
    return built


def _link_nodes(tree_data: dict, nodes: dict, problems: list[str]):
    """Connect nodes by id and return the root.

    Checks that every link points to a known node, that no node has two
    parents (which also rules out cycles) and that every node is reachable
    from the root. Deeper checks (global order, heights, balance) belong to
    the load validation of Section 12.
    """
    parent_of: dict[int, int] = {}
    for node_data in tree_data["nodes"]:
        node = nodes[node_data["event_id"]]
        for side in ("left", "right"):
            child_id = node_data[side]
            if child_id is None:
                continue
            if child_id not in nodes:
                problems.append(f"Node {node.event_id} links {side} to unknown id {child_id}")
                continue
            if child_id in parent_of or child_id == tree_data["root"]:
                problems.append(f"Node {child_id} has more than one position in the tree")
                continue
            parent_of[child_id] = node.event_id
            setattr(node, side, nodes[child_id])

    root_id = tree_data["root"]
    if root_id is None:
        if nodes:
            problems.append("Tree has nodes but no root")
        return None
    if root_id not in nodes:
        problems.append(f"Root id {root_id} is not a node of the tree")
        return None

    # With one parent per node and the root parentless, the part reachable from
    # the root is a tree, so this walk ends. A cycle is never reachable from
    # the root and shows up as unreachable nodes.
    reached = set()
    stack = [nodes[root_id]]
    while stack:
        node = stack.pop()
        reached.add(node.event_id)
        stack.extend(child for child in (node.left, node.right) if child)
    for event_id in sorted(set(nodes) - reached):
        problems.append(f"Node {event_id} is not reachable from the root")
    return nodes[root_id]


def _avl_from_dict(tree_data: dict, event_index: dict, problems: list[str]) -> AVLTree:
    """Rebuild the AVL from its links; each node references the event object itself."""
    nodes: dict[int, AVLNode] = {}
    for node_data in tree_data["nodes"]:
        event_id = node_data["event_id"]
        node = AVLNode(event_index[event_id])
        node.height = int(node_data["height"])
        nodes[event_id] = node

    avl = AVLTree()
    avl.root = _link_nodes(tree_data, nodes, problems)
    avl.size = len(nodes)
    return avl


def _bst_from_dict(tree_data: dict, problems: list[str]) -> BSTTree:
    nodes: dict[int, BSTNode] = {}
    for node_data in tree_data["nodes"]:
        key = TreeKey.from_list(node_data["key"])
        if key.event_id != node_data["event_id"]:
            problems.append(f"BST node {node_data['event_id']} holds key {key}")
        if node_data["event_id"] in nodes:
            problems.append(f"Event {node_data['event_id']} appears twice in the BST")
        nodes[node_data["event_id"]] = BSTNode(key)

    bst = BSTTree()
    bst.root = _link_nodes(tree_data, nodes, problems)
    bst.size = len(nodes)
    return bst
